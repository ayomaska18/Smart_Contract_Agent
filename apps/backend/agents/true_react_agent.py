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
from typing import Optional, Dict
from dotenv import load_dotenv
from pydantic import Field

from grafi.assistants.assistant import Assistant
from grafi.assistants.assistant_base import AssistantBaseBuilder
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.models.message import Message
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

# Add paths to find tools in new structure
import sys
import os

# Add path for backend modules
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

# Add path for MCP server modules  
services_path = os.path.join(backend_path, '..', '..', 'services', 'mcp_server', 'src')
services_path = os.path.abspath(services_path)
sys.path.append(services_path)

from grafi.common.models.function_spec import FunctionSpec, ParametersSchema, ParameterSchema

from grafi.tools.function_calls.function_call_tool import FunctionCallTool
from grafi.common.models.message import Message

class SimpleMockTool(FunctionCallTool):
    def __init__(self):
        super().__init__()
        self.name = "SimpleMockTool"
        self.type = "MockTool"

    def invoke(self, invoke_context, input_data):
        """Synchronous mock response"""
        output = []
        for message in input_data:
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    output.append(Message(
                        role="tool",
                        content=f'{{"result": "Mock response for {tool_call.function.name}", "success": true}}',
                        tool_call_id=tool_call.id
                    ))
        return output if output else input_data

def create_mcp_function_specs():
    """Create function specifications for MCP tools that the ActionExecutionNode can use."""

    generate_erc20_spec = FunctionSpec(
        name="generate_erc20_contract",
        description="Generate an ERC20 token contract with advanced features",
        parameters=ParametersSchema(
            properties={
                "contract_name": ParameterSchema(type="string", description="Name of the contract class (PascalCase)"),
                "token_name": ParameterSchema(type="string", description="Human readable token name"),
                "token_symbol": ParameterSchema(type="string", description="Token symbol (uppercase)"),
                "initial_supply": ParameterSchema(type="integer", description="Initial token supply"),
                "decimals": ParameterSchema(type="integer", description="Token decimals (default: 18)"),
                "mintable": ParameterSchema(type="boolean", description="Enable minting functionality"),
                "burnable": ParameterSchema(type="boolean", description="Enable burning functionality"),
                "pausable": ParameterSchema(type="boolean", description="Enable pausing functionality"),
                "permit": ParameterSchema(type="boolean", description="Enable EIP-2612 gasless approvals"),
                "ownable": ParameterSchema(type="boolean", description="Enable ownership functionality"),
                "capped": ParameterSchema(type="boolean", description="Enable supply cap"),
                "max_supply": ParameterSchema(type="integer", description="Maximum supply if capped")
            },
            required=["contract_name", "token_name", "token_symbol"]
        )
    )
    
    generate_erc721_spec = FunctionSpec(
        name="generate_erc721_contract",
        description="Generate an ERC721 NFT contract with advanced features",
        parameters=ParametersSchema(
            properties={
                "contract_name": ParameterSchema(type="string", description="Name of the contract class"),
                "token_name": ParameterSchema(type="string", description="NFT collection name"),
                "token_symbol": ParameterSchema(type="string", description="NFT collection symbol"),
                "base_uri": ParameterSchema(type="string", description="Base URI for metadata"),
                "mintable": ParameterSchema(type="boolean", description="Enable minting functionality"),
                "burnable": ParameterSchema(type="boolean", description="Enable burning functionality"),
                "enumerable": ParameterSchema(type="boolean", description="Enable enumerable extension"),
                "uri_storage": ParameterSchema(type="boolean", description="Enable URI storage extension"),
                "ownable": ParameterSchema(type="boolean", description="Enable ownership functionality"),
                "royalty": ParameterSchema(type="boolean", description="Enable EIP-2981 royalties"),
                "royalty_percentage": ParameterSchema(type="integer", description="Royalty percentage in basis points"),
                "max_supply": ParameterSchema(type="integer", description="Maximum NFT supply")
            },
            required=["contract_name", "token_name", "token_symbol"]
        )
    )

    compile_contract_spec = FunctionSpec(
        name="compile_contract",
        description="Compile Solidity code and return compilation ID",
        parameters=ParametersSchema(
            properties={
                "solidity_code": ParameterSchema(type="string", description="The Solidity source code to compile")
            },
            required=["solidity_code"]
        )
    )
    
    deploy_contract_spec = FunctionSpec(
        name="deploy_contract",
        description="Deploy compiled contract to blockchain network using default gas settings and wallet address",
        parameters=ParametersSchema(
            properties={
                "compilation_id": ParameterSchema(type="string", description="The compilation ID from compile_contract"),
                "initial_owner": ParameterSchema(type="string", description="Initial owner address (optional, defaults to wallet address)"),
                "gas_limit": ParameterSchema(type="integer", description="Gas limit for deployment (optional, default: 2000000)"),
                "gas_price_gwei": ParameterSchema(type="integer", description="Gas price in Gwei (optional, default: 10)")
            },
            required=["compilation_id"]
        )
    )

    get_abi_spec = FunctionSpec(
        name="get_abi",
        description="Get contract ABI using compilation ID",
        parameters=ParametersSchema(
            properties={
                "compilation_id": ParameterSchema(type="string", description="The compilation ID")
            },
            required=["compilation_id"]
        )
    )

    get_bytecode_spec = FunctionSpec(
        name="get_bytecode", 
        description="Get contract bytecode using compilation ID",
        parameters=ParametersSchema(
            properties={
                "compilation_id": ParameterSchema(type="string", description="The compilation ID")
            },
            required=["compilation_id"]
        )
    )

    return [
        generate_erc20_spec,
        generate_erc721_spec,
        compile_contract_spec,
        deploy_contract_spec,
        get_abi_spec,
        get_bytecode_spec
    ]

def load_prompt(file_path: str) -> str:
    """Load a prompt from a Markdown file."""
    return Path(file_path).read_text(encoding="utf-8")

load_dotenv()

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTION_EXECUTION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "action.md"))
REASONING_SYSTEM_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "reasoning.md"))

class TrueReActAssistant(Assistant):
    name: str = Field(default="TrueReActSmartContractAgent")
    type: str = Field(default="TrueReActAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    model: str = Field(default=lambda: os.getenv('OPENAI_MODEL', 'gpt-4'))
    function_call_tool: Optional[MCPTool] = Field(default=None)
    system_prompt: str = Field(default=REASONING_SYSTEM_PROMPT)

    @classmethod
    def builder(cls):
        return TrueReActAssistantBuilder(cls)

    def _construct_workflow(self):
        if self.function_call_tool is None:
            raise ValueError(
                "function_call_tool is required for TrueReActAssistant. "
                "Use TrueReActAssistant.builder().function_call_tool(...).build()"
            )

        user_input_topic = InputTopic(name="agent_input_topic")

        reasoning_output_topic = Topic(
            name="reasoning_output_topic",
            condition=lambda msgs: any("ACTION_NEEDED:" in str(msg.content) for msg in msgs if msg.content)
        )
        
        tool_call_topic = Topic(
            name="mcp_tool_call_topic",
            condition=lambda msgs: msgs[-1].tool_calls is not None
        )
        
        tool_result_topic = Topic(name="function_result_topic")
        
        final_output_topic = OutputTopic(
            name="agent_output_topic",
            condition=lambda msgs: any("FINAL_ANSWER:" in str(msg.content) for msg in msgs if msg.content)
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
        
        function_specs = create_mcp_function_specs()
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
        
        self.workflow = (
            EventDrivenWorkflow.builder()
            .name("true_react_smart_contract_workflow")
            .node(reasoning_node)
            .node(action_node)
            .node(tool_execution_node)
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

    def system_prompt(self, system_prompt: str):
        self.kwargs["system_prompt"] = system_prompt
        return self
