import uuid
import sys
import os
import asyncio
import re
import json

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from deps.assistant import get_assistant
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.models.message import Message
from grafi.common.events.topic_events.publish_to_topic_event import PublishToTopicEvent
from memory.context import get_conversation_context

from routers.approval import approval_requests

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

@router.post("/", response_model=ChatResponse)
async def chat_endpoint(chat_request: ChatRequest, assistant = Depends(get_assistant)):
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        conversation_id = chat_request.conversation_id or uuid.uuid4().hex
        message_id = uuid.uuid4().hex
        
        print(f"Backend API: Processing message: {chat_request.message[:50]}...")

        # Define fallback response first
        response_text = f"""Hello! I'm your **Backend API** Smart Contract Assistant.

🏗️ **Architecture**: Separated 3-component system
• 📱 Frontend (Next.js) → 🔧 Backend API (FastAPI) → 🛠️ MCP Server (FastMCP)
🔧 **Status**: Running on http://localhost:8000  
📡 **MCP Server**: http://localhost:8081/mcp/
🤖 **ReAct Agent**: {"Connected" if assistant else "Fallback Mode"}

I specialize in smart contract development and can help you with:
• **ERC20 & ERC721** token generation
• **Smart contract** compilation and deployment  
• **Blockchain** interactions and testing
• **Solidity** code analysis and optimization

Try asking me to create an ERC20 token to see the full ReAct + MCP integration in action!

What would you like to build today?"""

        # Use the ReAct assistant if available
        if assistant:
            print("Backend API: Using ReAct assistant with MCP tools")
            
            try:
                invoke_context = InvokeContext(
                    conversation_id=conversation_id,
                    invoke_id=uuid.uuid4().hex,
                    assistant_request_id=message_id,
                )
                
                # get context
                conversation_history = get_conversation_context(conversation_id)

                # print(conversation_history)

                input_data = conversation_history + [Message(role="user", content=chat_request.message)]

                print("input_data", input_data)

                input_event = PublishToTopicEvent(
                    invoke_context=invoke_context,
                    publisher_name="chat_api",
                    publisher_type="api",
                    topic_name="agent_input_topic",
                    data=input_data,
                    consumed_events=[]
                )

                full_response = ""

                try:
                    response_count = 0
                    async for response_event in assistant.a_invoke(input_event):
                        response_count += 1
                        
                        if hasattr(response_event, 'data'):
                            if response_event.data:
                                for message in response_event.data:
                                    print(f"Debug: MESSAGE TYPE: {type(message)}")
                                    print(f"Debug: MESSAGE ATTRIBUTES: {[attr for attr in dir(message) if not attr.startswith('_')]}")
                                
                                if hasattr(message, 'content') and message.content:
                                    print(f"Debug: NODE OUTPUT (from {response_event.topic_name}): {str(message.content)}")
                                    print(f"Debug: Contains FINAL_ANSWER: {'FINAL_ANSWER:' in str(message.content)}")
                                    print(f"Debug: Contains ACTION_NEEDED: {'ACTION_NEEDED:' in str(message.content)}")
                                    if full_response:
                                        full_response += "\n\n"
                                    full_response += str(message.content)
                                elif hasattr(message, 'tool_calls') and message.tool_calls:
                                    print(f"Debug: NODE OUTPUT (tool calls from {response_event.topic_name}): {message.tool_calls}")
                                    print(f"Debug: Tool call details: {[(tc.function.name, tc.function.arguments) for tc in message.tool_calls]}")
                                    if full_response:
                                        full_response += "\n\n"
                                    full_response += f"Tool calls: {[tc.function.name for tc in message.tool_calls]}"
                                else:
                                    print(f"Debug: Message has no content or tool calls (from {response_event.topic_name}): {message}")
                                    print(f"Debug: Message dict: {message.__dict__ if hasattr(message, '__dict__') else 'No __dict__'}")
                        else:
                            print(f"Debug: Response event has no data: {response_event}")
                    
                    print(f"Debug: Total responses received: {response_count}")
                    print(f"Debug: Full response: {full_response}")
                    
                except asyncio.TimeoutError:
                    print("Backend API: ReAct agent timed out, using fallback")
                    raise Exception("ReAct agent timed out")
                except Exception as e:
                    print(f"Debug: Error in assistant invocation: {e}")
                    print(f"Debug: Error type: {type(e)}")
                    raise

                print("Backend API: ReAct assistant response generated successfully")

                # Check if this is a deployment preparation response that should trigger approval
                print(f"Debug: Checking approval trigger conditions...")
                print(f"Debug: full_response exists: {bool(full_response)}")
                if full_response:
                    print(f"Debug: full_response content: {full_response[:200]}...")
                    prepared_check = "prepared your contract deployment" in full_response.lower()
                    approval_check = "approval request" in full_response.lower()
                    print(f"Debug: prepared_check: {prepared_check}")
                    print(f"Debug: approval_check: {approval_check}")
                    print(f"Debug: will trigger: {prepared_check or approval_check}")

                # check if message include deployment
                if full_response and ("prepared your contract deployment" in full_response.lower() or 
                                    "approval request" in full_response.lower()):
                    # Create an approval request for the frontend to pick up
                    approval_id = f"chat_approval_{uuid.uuid4().hex}"

                    transaction_data = {
                        "to": None,  # Contract deployment
                        "data": None,  # Will be extracted from MCP response
                        "gas": 2000000, # gas price TO BE FIXED
                        "gasPrice": "10000000000", # gas price TO BE FIXED
                        "chainId": 11155111,
                        "value": "0"
                    }

                    try:
                        transaction_pattern = r'"transaction":\s*{[^}]+}'
                        match = re.search(transaction_pattern, full_response)
                        if match:
                            transaction_json_str = match.group(0)
                            transaction_obj = json.loads("{" + transaction_json_str + "}")
                            if "transaction" in transaction_obj:
                                tx_data = transaction_obj["transaction"]
                                transaction_data.update({
                                    "data": tx_data.get("data"),
                                    "gas": tx_data.get("gas", 2000000),
                                    "gasPrice": tx_data.get("gasPrice", "10000000000"),
                                    "chainId": tx_data.get("chainId", 11155111),
                                    "value": tx_data.get("value", "0")
                                })
                                print(f"Extracted real transaction data from response")
                    except Exception as extract_error:
                        print(f"Could not extract transaction data, using defaults: {extract_error}")
                    
                    approval_request_data = {
                        "approval_id": approval_id,
                        "transaction_data": transaction_data,
                        "timestamp": datetime.now(),
                        "message": f"Contract deployment approval required. {full_response[:200]}...",
                        "processed": False
                    }
                    
                    approval_requests[approval_id] = approval_request_data
                    print(f"Created approval request for deployment: {approval_id}")
                    print(f"Total approval requests now: {len(approval_requests)}")
                
                return ChatResponse(
                    success=True,
                    data={
                        "response": full_response,
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "timestamp": datetime.now().isoformat(),
                        "backend_mode": "react_assistant_with_mcp"
                    }
                )
                
            except Exception as react_error:
                print(f"Backend API: ReAct assistant failed: {react_error}, falling back to default response")
        
        return ChatResponse(
            success=True,
            data={
                "response": response_text,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "timestamp": datetime.now().isoformat(),
                "backend_mode": "react_assistant_with_mcp"
            }
        )
        
    except Exception as e:
        print(f"Backend API: Error processing chat request: {e}")
        return ChatResponse(
            success=False,
            error=str(e)
        )

@router.get("/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    """Get conversation history for a specific conversation"""
    try:
        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages": [],
            "note": "Simple agent mode - history tracking not implemented yet"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/new")
async def new_conversation():
    """Start a new conversation and return a conversation ID"""
    try:
        conversation_id = uuid.uuid4().hex
        return {
            "success": True,
            "conversationId": conversation_id,
            "message": "New conversation started"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}