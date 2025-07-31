import os
import uuid
import asyncio
from typing import AsyncGenerator
from typing import Optional, Self, Dict
from dotenv import load_dotenv

from loguru import logger
from openinference.semconv.trace import OpenInferenceSpanKindValues
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
from grafi.tools.function_calls.function_call_tool import FunctionCallTool
from grafi.tools.function_calls.impl.google_search_tool import GoogleSearchTool
from grafi.tools.llms.impl.openai_tool import OpenAITool
from grafi.workflows.impl.event_driven_workflow import EventDrivenWorkflow
from grafi.common.models.mcp_connections import StreamableHttpConnection
from grafi.tools.function_calls.impl.mcp_tool import MCPTool
from grafi.common.containers.container import container
from grafi.common.event_stores.event_store_postgres import EventStorePostgres

load_dotenv()

openai_model = os.getenv('OPENAI_MODEL')
mcp_server_url = os.getenv('mcp_server_url')

postgres_event_store = EventStorePostgres(
    db_url="postgresql://postgres:postgres@localhost:5432/grafi_test_db",
)

container.register_event_store(postgres_event_store)

event_store = container.event_store

AGENT_SYSTEM_MESSAGE = """
You are a helpful and knowledgeable agent. To achieve your goal of answering complex questions
correctly, you have access to the search tool.

To answer questions, you'll need to go through multiple steps involving step-by-step thinking and
selecting search tool if necessary.

Response in a concise and clear manner, ensuring that your answers are accurate and relevant to the user's query.
"""

CONVERSATION_ID = uuid.uuid4().hex

class SmartContractAssistant(Assistant):
    oi_span_type: OpenInferenceSpanKindValues = Field(
        default=OpenInferenceSpanKindValues.AGENT
    )
    name: str = Field(default="SmartContractAssistant")
    type: str = Field(default="SmartContractAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    system_prompt: Optional[str] = Field(default=AGENT_SYSTEM_MESSAGE)
    function_call_tool: FunctionCallTool = Field(
        default=GoogleSearchTool.builder()
        .name("GoogleSearchTool")
        .fixed_max_results(3)
        .build()
    )
    model: str = Field(default=lambda: os.getenv('OPENAI_MODEL'))

    @classmethod
    def builder(cls) -> "SmartContractAssistantBuilder":
        """Return a builder for Smart Contract Agent."""
        return SmartContractAssistantBuilder(cls)

    def _construct_workflow(self) -> "SmartContractAssistant":
        # topic will only publish if met the condition
        mcp_tool_call_topic = Topic(
            name="mcp_tool_call_topic",
            condition=lambda msgs: msgs[-1].tool_calls # gets the last message in the message history
            is not None,  # checks the message includes a function/tool call
        )
        
        mcp_server_response_topic = Topic(name="function_result_topic")

        agent_input_topic = InputTopic(name="agent_input_topic")

        agent_output_topic = OutputTopic(
            name="agent_output_topic",
            condition=lambda msgs: msgs[-1].content is not None
            and isinstance(msgs[-1].content, str)
            and msgs[-1].content.strip() != "",
        )

        llm_node = (
            Node.builder()
            .name("OpenAIInputNode")
            .type("OpenAIInputNode")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(agent_input_topic)
                .or_()
                .subscribed_to(mcp_server_response_topic)
                .build()
            )
            .tool(
                OpenAITool.builder()
                .name("UserInputLLM")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(self.system_prompt)
                .build()
            )
            .publish_to(mcp_tool_call_topic)
            .publish_to(agent_output_topic)
            .build()
        )

        # mcp node
        mcp_node = (
            Node.builder()
            .name("MCPServerQuery")
            .type("MCPNode")
            .subscribe(SubscriptionBuilder().subscribed_to(mcp_tool_call_topic).build())
            .tool(self.function_call_tool)
            .publish_to(mcp_server_response_topic)
            .build()
        )

        # Create a workflow and add the nodes
        self.workflow = (
            EventDrivenWorkflow.builder()
            .name("function_call_workflow")
            .node(llm_node)
            .node(mcp_node)
            .build()
        )

        return self

    def get_input(
        self, question: str, invoke_context: Optional[InvokeContext] = None
    ) -> list[Message]:
        if invoke_context is None:
            logger.debug(
                "Creating new InvokeContext with default conversation id for Smart Contract Agent"
            )
            invoke_context = InvokeContext(
                conversation_id=CONVERSATION_ID,
                invoke_id=uuid.uuid4().hex,
                assistant_request_id=uuid.uuid4().hex,
            )

        # Prepare the input data
        input_data = [
            Message(
                role="user",
                content=question,
            )
        ]

        return input_data, invoke_context

    def run(self, question: str, invoke_context: Optional[InvokeContext] = None) -> str:
        input_data, invoke_context = self.get_input(question, invoke_context)

        output = super().invoke(invoke_context, input_data)

        return output[0].content

    async def a_run(
        self, question: str, invoke_context: Optional[InvokeContext] = None
    ) -> AsyncGenerator[Message, None]:
        input_data, invoke_context = self.get_input(question, invoke_context)

        async for output in super().a_invoke(invoke_context, input_data):
            for message in output:
                yield message


class SmartContractAssistantBuilder(AssistantBaseBuilder[SmartContractAssistant]):
    """Concrete builder for Smart Contract Agent."""

    def api_key(self, api_key: str) -> Self:
        self.kwargs["api_key"] = api_key
        return self

    def system_prompt(self, system_prompt: str) -> Self:
        self.kwargs["system_prompt"] = system_prompt
        return self

    def model(self, model: str) -> Self:
        self.kwargs["model"] = model
        return self
    
    def function_call_llm_system_message(
        self, function_call_llm_system_message: str
    ) -> Self:
        self.kwargs[
            "function_call_llm_system_message"
        ] = function_call_llm_system_message
        return self

    def function_call_tool(self, function_call_tool: FunctionCallTool) -> Self:
        self.kwargs["function_call_tool"] = function_call_tool
        return self

async def create_assistant():
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv('OPENAI_MODEL', "")
    function_call_llm_system_message = "You are a helpful assistant that can call functions to retrieve data from an mcp server"

    mcp_config: Dict[str, StreamableHttpConnection] = {
        "smart-contract-server": StreamableHttpConnection(
            url=mcp_server_url,
            transport="http"
        )
    }

    assistant =( SmartContractAssistant.builder()
        .name("MCPAssistant")
        .model(model)
        .api_key(api_key)
        .function_call_llm_system_message(function_call_llm_system_message)
        .function_call_tool(await MCPTool.builder().connections(mcp_config).a_build())
        .build()
    )
    return assistant

async def main():
    assistant = await create_assistant()

    invoke_context = InvokeContext(
        conversation_id=uuid.uuid4().hex,
        invoke_id=uuid.uuid4().hex,
        assistant_request_id=uuid.uuid4().hex,
    )

    question = "Can you give generate me a erc20 token with name test, and symbol TEST?"
    input_data = [Message(role="user", content=question)]

    async for response in assistant.a_invoke(invoke_context, input_data):
        print("Assistant output:")
        for output in response:
            print(output.content)
    
    events = event_store.get_conversation_events(invoke_context.conversation_id)

    print(f"Events for conversation {invoke_context.conversation_id}:")
    print(f"Events: {events} ")

    return assistant

if __name__ == "__main__":
    asyncio.run(main())
