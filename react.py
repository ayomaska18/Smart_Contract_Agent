import asyncio
import os
import uuid
from dotenv import load_dotenv
from grafi.common.containers.container import container
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.models.mcp_connections import StreamableHttpConnection
from grafi.common.models.message import Message
from grafi.tools.function_calls.impl.mcp_tool import MCPTool
from grafi.agents.react_agent import ReActAgent
from pydantic import Field
from typing import Optional, Self

load_dotenv()

CONVERSATION_ID = uuid.uuid4().hex
event_store = container.event_store

api_key = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
mcp_server_url = os.getenv('mcp_server_url')

class SmartContractAssistant(ReActAgent):
    mcp_server_url: str = Field(default=mcp_server_url)

    async def _build_with_mcp(self):
        """Build the assistant with MCP server integration using official method"""
        try:
            # Give server time to start up
            await asyncio.sleep(2)
            mcp_config = {
                "smart-contract-server": StreamableHttpConnection({
                    "url": self.mcp_server_url,
                    "transport": "http",
                })
            }
            mcp_tool = await MCPTool.builder().connections(mcp_config).a_build()

            assistant = (
                ReActAgent.builder()
                .api_key(self.api_key)
                .model(self.model)
                .function_call_tool(mcp_tool)
                .system_prompt(
                    "You are a smart contract assistant that can generate, compile, and deploy smart contracts. "
                    "Use the available MCP tools based on what the user requests:\n\n"
                    "- If user wants to GENERATE a contract: call generate_contract\n"
                    "- If user wants to COMPILE: call compile_contract (needs solidity_code)\n" 
                    "- If user wants to DEPLOY: call deploy_contract (needs compilation_id)\n"
                    "- If user wants full deployment: do generate → compile → deploy sequence\n\n"
                    "Only do what the user specifically asks for. Don't assume they want the full sequence unless explicitly requested.\n"
                    "Ask for missing required parameters if needed.\n\n"
                    "Available functions: generate_contract, compile_contract, deploy_contract"
                )
                .build()
            )

            self.workflow = assistant.workflow
            return True

        except Exception as e:
            print(f"Warning: Could not connect to MCP server at {self.mcp_server_url}: {e}")
            return False

    def get_input(self, question: str, invoke_context: Optional[InvokeContext] = None) -> tuple[list[Message], InvokeContext]:
        # maintain the workflow state
        if invoke_context is None:
            print("Creating new InvokeContext with default conversation id for SmartContractAssistant")
            invoke_context = InvokeContext(
                user_id=uuid.uuid4().hex,
                conversation_id=CONVERSATION_ID,
                invoke_id=uuid.uuid4().hex,
                assistant_request_id=uuid.uuid4().hex,
            )

        input_data = [
            Message(
                role="user",
                content=question,
            )
        ]

        return input_data, invoke_context

    async def a_run(self, question: str, invoke_context: Optional[InvokeContext] = None) -> str:
        mcp_connected = await self._build_with_mcp()
        if not mcp_connected:
            print("Running without MCP server integration")

        input_data, invoke_context = self.get_input(question, invoke_context)
        
        results = []
        async for output in super().a_invoke(invoke_context, input_data):
            results.append(output)

        if results and len(results) > 0:
            last_result = results[-1]

            if isinstance(last_result, list) and len(last_result) > 0:
                content = last_result[-1].content
            elif hasattr(last_result, 'content'):
                content = last_result.content
            else:
                content = str(last_result)
                
            if isinstance(content, str):
                return content
            elif content is not None:
                return str(content)

        return "No response generated"

    def run(self, question: str, invoke_context: Optional[InvokeContext] = None) -> str:
        """Run the assistant with a question and return the response."""
        return asyncio.run(self.a_run(question, invoke_context))

async def main():
    assistant = SmartContractAssistant(
        api_key=api_key,
        model=OPENAI_MODEL,
        mcp_server_url=mcp_server_url
    )

    print("=== Smart Contract Assistant - Official MCP Integration ===")
    print()

    # # Test with generate only
    # print("=== Test 1: Generate Only ===")
    # user_input = "Generate an ERC20 token with contract name Hello and symbol HELLO that is mintable and ownable"
    # result = await assistant.a_run(user_input)
    # print("Assistant Response:", result)
    # print()

    # # Test with full deployment
    # print("=== Test 2: Full Deployment ===")
    # user_input3 = "Generate, compile and deploy an ERC20 token with contract name Test and symbol TEST that is mintable and ownable"
    # result3 = await assistant.a_run(user_input3)
    # print("Assistant Response:", result3)

    # Test with incomplete information
    print("=== Test 3: Full Deployment with missing information ===")
    user_input3 = "Generate, compile and deploy an ERC20 token"
    result3 = await assistant.a_run(user_input3)
    print("Assistant Response:", result3)


# Global assistant instance required by grafi-dev
assistant = SmartContractAssistant(
    api_key=api_key,
    model=OPENAI_MODEL,
    mcp_server_url=mcp_server_url
)

if __name__ == "__main__":
    asyncio.run(main())