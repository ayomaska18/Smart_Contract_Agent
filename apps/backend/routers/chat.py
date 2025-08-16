import uuid
import sys
import os

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from deps.assistant import get_assistant
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.models.message import Message
from memory.context import get_conversation_context

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
    # Get assistant from app state, but don't fail if it's not available
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
                # Create invoke context (similar to main.py)
                invoke_context = InvokeContext(
                    conversation_id=conversation_id,
                    invoke_id=uuid.uuid4().hex,
                    assistant_request_id=message_id,
                )

                # Get conversation history and add current message
                conversation_history = get_conversation_context(conversation_id)
                input_data = conversation_history + [Message(role="user", content=chat_request.message)]

                print(f"Backend API: Invoking ReAct agent with {len(input_data)} context messages")
                
                # Collect all responses from the assistant with timeout
                full_response = ""
                import asyncio
                
                try:
                    # Add 25 second timeout to prevent hanging
                    async with asyncio.timeout(25):
                        async for response in assistant.a_invoke(invoke_context, input_data):
                            for output in response:
                                if output.content:
                                    if full_response:
                                        full_response += "\n\n"
                                    full_response += output.content
                except asyncio.TimeoutError:
                    print("Backend API: ReAct agent timed out, using fallback")
                    raise Exception("ReAct agent timed out")

                print("Backend API: ReAct assistant response generated successfully")
                
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
                # Fall through to use response_text below
        
        return ChatResponse(
            success=True,
            data={
                "response": response_text,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "timestamp": datetime.now().isoformat(),
                "backend_mode": "mcp_integrated"
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