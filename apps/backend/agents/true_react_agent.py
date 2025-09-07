"""
True ReAct Agent Implementation for Smart Contract Development

This implements the proper ReAct pattern with explicit reasoning nodes,
based on the working react_test.py architecture but with added sophistication
for handling complex smart contract tasks like NFT creation.
"""

import os
import sys

from pathlib import Path
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
from pydantic import Field

from grafi.assistants.assistant import Assistant
from grafi.assistants.assistant_base import AssistantBaseBuilder
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.topics.input_topic import InputTopic
from grafi.common.topics.output_topic import OutputTopic
from grafi.common.topics.subscription_builder import SubscriptionBuilder
from grafi.common.topics.topic import Topic
from grafi.nodes.node import Node
from grafi.tools.llms.impl.openai_tool import OpenAITool
from grafi.tools.function_calls.impl.mcp_tool import MCPTool
from grafi.workflows.impl.event_driven_workflow import EventDrivenWorkflow
from grafi.common.models.mcp_connections import StreamableHttpConnection
from grafi.common.containers.container import container
from grafi.tools.function_calls.function_call_tool import FunctionCallTool
from grafi.common.models.message import Message
from grafi.common.models.function_spec import FunctionSpec
from grafi.common.topics.in_workflow_input_topic import InWorkflowInputTopic
from grafi.common.topics.in_workflow_output_topic import InWorkflowOutputTopic
from tools.mock_tool import SimpleMockTool
from models.agent_responses import (
    ReasoningResponse, 
    ActionExecutionResponse, 
    DeploymentApprovalRequest, 
    ApprovalResponse,
    FinalAgentResponse
)


backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

services_path = os.path.join(backend_path, '..', '..', 'services', 'mcp_server', 'src')
services_path = os.path.abspath(services_path)
sys.path.append(services_path)

def load_prompt(file_path: str) -> str:
    """Load a prompt from a Markdown file."""
    return Path(file_path).read_text(encoding="utf-8")

load_dotenv()

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTION_EXECUTION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "action.md"))
REASONING_SYSTEM_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "reasoning.md"))
APPROVAL_REQUEST_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "approval_request.md"))
APPROVAL_RESPONSE_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "approval_response.md"))

class TrueReActAssistant(Assistant):
    name: str = Field(default="TrueReActSmartContractAgent")
    type: str = Field(default="TrueReActAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    model: str = Field(default=lambda: os.getenv('OPENAI_MODEL', 'gpt-4'))
    function_call_tool: Optional[MCPTool] = Field(default=None)
    system_prompt: str = Field(default=REASONING_SYSTEM_PROMPT)
    # function_specs: Optional[List[FunctionSpec]] = Field(default=None)

    @classmethod
    def builder(cls):
        return TrueReActAssistantBuilder(cls)

    # def get_function_specs_from_mcp_tool(self) -> List[FunctionSpec]:
    #     """Extract function specs from the MCP tool."""
    #     if self.function_call_tool is None:
    #         raise ValueError("function_call_tool is required to extract function specs")
    #     return self.function_call_tool.function_specs

    def _construct_workflow(self):
        if self.function_call_tool is None:
            raise ValueError(
                "function_call_tool is required for TrueReActAssistant. "
                "Use TrueReActAssistant.builder().function_call_tool(...).build()"
            )

        user_input_topic = InputTopic(name="agent_input_topic")

        final_output_topic = OutputTopic(
            name="agent_output_topic",
            condition=lambda msgs: any("FINAL_ANSWER:" in str(msg.content) for msg in msgs if msg.content)
        )

        reasoning_output_topic = Topic(
            name="reasoning_output_topic",
            condition=lambda msgs: any("ACTION_NEEDED:" in str(msg.content) for msg in msgs if msg.content)
        )
  

        tool_call_topic = Topic(
            name="mcp_tool_call_topic",
            condition=lambda msgs: msgs[-1].tool_calls is not None
        )
        
        tool_result_topic = Topic(name="function_result_topic")

        approval_input_topic = InWorkflowInputTopic(
            name = "deployment_approval_input"
        )

        approval_output_topic = InWorkflowOutputTopic(
            name= "deployment_approval_output", 
            paired_in_workflow_input_topic_name ="deployment_approval_input"
        )
        
        approved_deployment_topic = Topic(
            name="approved_deployment_topic",
            condition=lambda msgs: any("APPROVED" in str(msg.content) or "approved" in str(msg.content).lower() for msg in msgs if msg.content)
        )

        deployment_reasoning_topic = Topic(
            name="deployment_reasoning_topic",
            condition=lambda msgs: any(
                "ACTION_NEEDED:" in str(msg.content) and 
                ("deploy" in str(msg.content).lower() or "prepare_deployment_transaction" in str(msg.content).lower())
                for msg in msgs if msg.content
            )
        )

        reasoning_node = (
            Node.builder()
            .name("ReasoningNode")
            .type("ReasoningNode")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(user_input_topic)
                .or_()
                .subscribed_to(tool_result_topic)
                .or_()
                .subscribed_to(approved_deployment_topic) 
                .build()
            )
            .tool(
                OpenAITool.builder()
                .name("ReasoningLLM")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(self.system_prompt)
                .chat_params({
                    "response_format": ReasoningResponse
                })
                .build()
            )
            .publish_to(reasoning_output_topic)
            .publish_to(deployment_reasoning_topic)
            .publish_to(final_output_topic)
            .build()
        )

        action_execution_tool = (
            OpenAITool.builder()
            .name("ActionExecutionLLM")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(ACTION_EXECUTION_PROMPT)
            .chat_params({
                "response_format": ActionExecutionResponse
            })
            .build()
        )
        
        function_specs = self.function_call_tool.function_specs
        action_execution_tool.add_function_specs(function_specs)
        
        action_node = (
            Node.builder()
            .name("ActionExecutionNode")
            .type("ActionExecutionNode")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(reasoning_output_topic)
                .build()
            )
            .tool(action_execution_tool)
            .publish_to(tool_call_topic)
            .build()
        )
        
        tool_execution_node = (
            Node.builder()
            .name("MCPServerQuery")
            .type("MCPNode")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(tool_call_topic)
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(tool_result_topic)
            .build()
        )
        
        # Human Approval Request Node - only triggers on deployment
        approval_request_node = (
            Node.builder()
            .name("ApprovalRequestNode")
            .type("ApprovalRequestNode")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(deployment_reasoning_topic) 
                .build()
            )
            .tool(
                OpenAITool.builder()
                .name("ApprovalRequestLLM")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(APPROVAL_REQUEST_PROMPT)
                .chat_params({
                    "response_format": DeploymentApprovalRequest
                })
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(approval_output_topic)
            .build()
        )
        
        # Human Response Handler - processes responses from InWorkflowInputTopic
        approval_response_node = (
            Node.builder()
            .name("ApprovalResponseHandler")
            .type("ApprovalResponseNode")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(approval_input_topic) 
                .build()
            )
            .tool(
                OpenAITool.builder()
                .name("ApprovalResponseLLM")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(APPROVAL_RESPONSE_PROMPT)
                .chat_params({
                    "response_format": ApprovalResponse
                })
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(approved_deployment_topic) 
            .build()
        )
        
        self.workflow = (
            EventDrivenWorkflow.builder()
            .name("true_react_smart_contract_workflow")
            .node(reasoning_node)
            .node(action_node)
            .node(tool_execution_node)
            .node(approval_request_node)
            .node(approval_response_node)
            .build()
        )

        return self

class TrueReActAssistantBuilder(AssistantBaseBuilder):
    def api_key(self, api_key: str):
        self.kwargs["api_key"] = api_key
        return self

    def model(self, model: str):
        self.kwargs["model"] = model
        return self

    def function_call_tool(self, function_call_tool):
        self.kwargs["function_call_tool"] = function_call_tool
        return self

    # def function_specs(self, function_specs: List[FunctionSpec]):
    #     self.kwargs["function_specs"] = function_specs
    #     return self

    def system_prompt(self, system_prompt: str):
        self.kwargs["system_prompt"] = system_prompt
        return self
