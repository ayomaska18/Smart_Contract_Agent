"""
True ReAct Agent Implementation for Smart Contract Development

This implements the proper ReAct pattern with explicit reasoning nodes,
based on the working react_test.py architecture but with added sophistication
for handling complex smart contract tasks like NFT creation.
"""

import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional, Dict, List
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

import sys
import os

# Add path for backend modules
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

# Add path for MCP server modules  
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

# Prompt for the approval request node
APPROVAL_REQUEST_PROMPT = """You are the Deployment Approval Request handler. You have access to MCP deployment functions.

Your job is to detect when users want to deploy contracts and call prepare_deployment_transaction.

When you receive messages, look for:
- User requests to deploy contracts (e.g., "deploy my contract", "deploy to testnet")
- References to contract deployments with wallet addresses

If you detect a deployment request:
1. Look for compilation_id from previous compilation in the conversation
2. Extract user_wallet_address from the request 
3. Call prepare_deployment_transaction function with these parameters
4. The result will automatically trigger the human approval workflow

If the message is NOT about deployment requests, just pass it through unchanged.

You have access to these deployment functions:
- prepare_deployment_transaction(compilation_id, user_wallet_address, gas_limit=2000000)"""

# Prompt for processing human approval responses  
APPROVAL_RESPONSE_PROMPT = """You are the Deployment Approval Response handler. You have access to MCP deployment functions.

Your job is to process human approval/rejection responses and handle the broadcast step.

When you receive human responses:

If the response contains "APPROVE" or "approved" AND includes signed_transaction_hex:
1. Extract the signed_transaction_hex from the response
2. Call broadcast_signed_transaction function with the signed transaction
3. Complete the deployment process

If the response contains "APPROVE" or "approved" but NO signed transaction:
- Respond with: "APPROVED: Deployment approved. Please sign the transaction in your wallet and provide the signed transaction hex."

If the response contains "REJECT" or "rejected":  
- Respond with: "REJECTED: Deployment cancelled by user request."

For any other response:
- Respond with: "UNCLEAR_RESPONSE: Please respond with either APPROVE or REJECT for the deployment."

You have access to these deployment functions:
- broadcast_signed_transaction(signed_transaction_hex)"""


# No custom node needed - InWorkflowInputTopic/OutputTopic handle human-in-the-loop directly

class TrueReActAssistant(Assistant):
    name: str = Field(default="TrueReActSmartContractAgent")
    type: str = Field(default="TrueReActAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    model: str = Field(default=lambda: os.getenv('OPENAI_MODEL', 'gpt-4'))
    function_call_tool: Optional[MCPTool] = Field(default=None)
    system_prompt: str = Field(default=REASONING_SYSTEM_PROMPT)
    function_specs: Optional[List[FunctionSpec]] = Field(default=None)

    @classmethod
    def builder(cls):
        return TrueReActAssistantBuilder(cls)

    def get_function_specs_from_mcp_tool(self) -> List[FunctionSpec]:
        """Extract function specs from the MCP tool."""
        if self.function_call_tool is None:
            raise ValueError("function_call_tool is required to extract function specs")
        return self.function_call_tool.function_specs

    def _construct_workflow(self):
        if self.function_call_tool is None:
            raise ValueError(
                "function_call_tool is required for TrueReActAssistant. "
                "Use TrueReActAssistant.builder().function_call_tool(...).build()"
            )

        # Input/Output topics
        user_input_topic = InputTopic(name="agent_input_topic")
        final_output_topic = OutputTopic(
            name="agent_output_topic",
            condition=lambda msgs: any("FINAL_ANSWER:" in str(msg.content) for msg in msgs if msg.content)
        )

        # Standard workflow topics
        reasoning_output_topic = Topic(
            name="reasoning_output_topic",
            condition=lambda msgs: any("ACTION_NEEDED:" in str(msg.content) for msg in msgs if msg.content)
        )
        
        tool_call_topic = Topic(
            name="mcp_tool_call_topic",
            condition=lambda msgs: msgs[-1].tool_calls is not None
        )
        
        tool_result_topic = Topic(name="function_result_topic")

        approval_output_topic = InWorkflowOutputTopic(
            name="deployment_approval_output",
            paired_in_workflow_input_topic_name="deployment_approval_input"
        )
        
        approval_input_topic = InWorkflowInputTopic(
            name="deployment_approval_input", 
            paired_in_workflow_output_topic_name="deployment_approval_output"
        )

        approved_deployment_topic = Topic(
            name="approved_deployment_topic",
            condition=lambda msgs: any("APPROVED" in str(msg.content) or "approved" in str(msg.content).lower() for msg in msgs if msg.content)
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
                .build()
            )
            .publish_to(reasoning_output_topic)
            .publish_to(final_output_topic)
            .build()
        )

        action_execution_tool = (
            OpenAITool.builder()
            .name("ActionExecutionLLM")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(ACTION_EXECUTION_PROMPT)
            .build()
        )
        
        # Use function specs from either provided specs or extract from MCP tool
        function_specs = self.function_specs or self.get_function_specs_from_mcp_tool()
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
        
        # Human Approval Request Node - publishes to InWorkflowOutputTopic when deployment ready
        approval_request_node = (
            Node.builder()
            .name("ApprovalRequestNode")
            .type("ApprovalRequestNode")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(tool_result_topic) 
                .build()
            )
            .tool(
                OpenAITool.builder()
                .name("ApprovalRequestLLM")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(APPROVAL_REQUEST_PROMPT)
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
                .subscribed_to(approval_input_topic)  # Listen for human responses
                .build()
            )
            .tool(
                OpenAITool.builder()
                .name("ApprovalResponseLLM")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(APPROVAL_RESPONSE_PROMPT)
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(approved_deployment_topic)  # Continue workflow after approval
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

    def function_specs(self, function_specs: List[FunctionSpec]):
        self.kwargs["function_specs"] = function_specs
        return self

    def system_prompt(self, system_prompt: str):
        self.kwargs["system_prompt"] = system_prompt
        return self
