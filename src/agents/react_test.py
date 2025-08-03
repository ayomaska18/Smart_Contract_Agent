import os
import uuid
import asyncio
import sys
import os
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
    db_url="postgresql+psycopg2://testing:testing@localhost:5432/grafi_test_db"
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

def get_conversation_context(conversation_id: str) -> list[Message]:
    """
    Retrieve conversation messages from event store for context.
    Removes duplicates and filters incomplete tool call sequences.
    """
    events = event_store.get_conversation_events(conversation_id)
    messages = []
    
    for event in events:
        if hasattr(event, 'data'):
            if isinstance(event.data, list):
                # Handle list of messages
                for item in event.data:
                    if isinstance(item, Message):
                        messages.append(item)
            elif isinstance(event.data, Message):
                # Handle single message
                messages.append(event.data)
    
    # Sort messages by timestamp to maintain order
    messages.sort(key=lambda m: m.timestamp if hasattr(m, 'timestamp') else 0)
    
    # Remove duplicate messages (same message_id and timestamp)
    seen_messages = set()
    deduped_messages = []
    for msg in messages:
        # Create unique key from message_id and timestamp
        key = (msg.message_id, msg.timestamp, msg.role, msg.content)
        if key not in seen_messages:
            seen_messages.add(key)
            deduped_messages.append(msg)
    
    print(f"DEBUG: After deduplication: {len(deduped_messages)} messages (was {len(messages)})")
    
    return deduped_messages

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

async def run_interactive_mode():
    print("=== Smart Contract Assistant - Interactive Mode ===")
    print("Type 'quit' or 'exit' to stop")
    print("Type 'new' to start a new conversation")
    print("Type 'history' to see conversation history")
    print("="*50)

    try:
        assistant = await create_assistant()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return
    
    conversation_id = uuid.uuid4().hex
    print(f"Started conversation: {conversation_id[:8]}...")
    print()
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['quit', 'exit']:
                print("Goodbye!")
                break
            
            if user_input.lower() == 'new':
                conversation_id = uuid.uuid4().hex
                print(f"Started new conversation: {conversation_id[:8]}...")
                continue
            
            if user_input.lower() == 'history':
                history = get_conversation_context(conversation_id)
                print(f"Conversation history ({len(history)} messages):")
                for i, msg in enumerate(history[-10:], 1): 
                    role = msg.role.capitalize()
                    content = msg.content[:100] + "..." if msg.content and len(msg.content) > 100 else msg.content
                    print(f"  {i}. {role}: {content}")
                continue
            
            if not user_input:
                continue
            
            invoke_context = InvokeContext(
                conversation_id=conversation_id,  
                invoke_id=uuid.uuid4().hex,
                assistant_request_id=uuid.uuid4().hex,
            )
            
            conversation_history = get_conversation_context(conversation_id)
            
            print(f"\nDEBUG: Conversation history ({len(conversation_history)} messages):")
            for i, msg in enumerate(conversation_history[-10:], 1): 
                role = msg.role
                has_tool_calls = "tool_calls" if msg.tool_calls else "no_calls"
                tool_call_id = f"tool_call_id:{msg.tool_call_id}" if msg.tool_call_id else "no_id"
                content_preview = (msg.content[:50] + "...") if msg.content else "None"
                print(f"  {i}. {role} | {has_tool_calls} | {tool_call_id} | {content_preview}")
            
            input_data = conversation_history + [Message(role="user", content=user_input)]
            
            print(f"\nSending {len(input_data)} messages to assistant...")
            
            print("Assistant: ", end="", flush=True)
            response_parts = []
            
            async for response in assistant.a_invoke(invoke_context, input_data):
                for output in response:
                    if output.content:
                        response_parts.append(output.content)
                        print(output.content)
            
            if not response_parts:
                print("No response generated.")
            
            print()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

async def main():
    await run_interactive_mode()
            
if __name__ == "__main__":
    asyncio.run(main())
