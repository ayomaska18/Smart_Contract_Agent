from grafi.common.models.message import Message
from grafi.common.containers.container import container
import json

def extract_and_dedupe_messages(events) -> list[Message]:
    messages = []
    
    for event in events:
        if hasattr(event, 'input_data'):
            if isinstance(event.input_data, list):
                for item in event.input_data:
                    # Handle ConsumeFromTopicEvent
                    if hasattr(item, 'data') and isinstance(item.data, list):
                        for msg in item.data:
                            if isinstance(msg, Message):
                                messages.append(msg)
                    elif isinstance(item, Message):
                        messages.append(item)
            elif isinstance(event.input_data, Message):
                messages.append(event.input_data)
        
        # Extract from output_data
        if hasattr(event, 'output_data'):
            if isinstance(event.output_data, list):
                for item in event.output_data:
                    if isinstance(item, Message):
                        messages.append(item)
            elif isinstance(event.output_data, Message):
                messages.append(event.output_data)
        
        # Extract from data attribute
        if hasattr(event, 'data'):
            if isinstance(event.data, list):
                for item in event.data:
                    if isinstance(item, Message):
                        messages.append(item)
            elif isinstance(event.data, Message):
                messages.append(event.data)
    
    # Sort by timestamp
    messages.sort(key=lambda m: m.timestamp if hasattr(m, 'timestamp') else 0)
    
    # Deduplicate messages
    seen_messages = set()
    deduped_messages = []
    for msg in messages:
        key = (msg.message_id, msg.timestamp, msg.role, msg.content[:100] if msg.content else None)
        if key not in seen_messages:
            seen_messages.add(key)
            deduped_messages.append(msg)
    
    return deduped_messages

def get_conversation_context(conversation_id: str) -> list[Message]:
    event_store = container.event_store
    events = event_store.get_conversation_events(conversation_id)
    
    # Extract and deduplicate messages
    messages = extract_and_dedupe_messages(events)
    
    # Build conversation flow
    conversation_flow = []
    pending_tool_call = None
    latest_tool_results = {}  # Store latest successful tool results
    
    for msg in messages:
        if msg.role == "user":
            conversation_flow.append(msg)
            
        elif msg.role == "assistant" and msg.content and not msg.tool_calls:
            # This is a final response - include it
            conversation_flow.append(msg)
            pending_tool_call = None
            
        elif msg.role == "assistant" and msg.tool_calls:
            # Track what action was attempted
            tool_names = [tc.function.name for tc in msg.tool_calls if tc.function]
            if tool_names:
                pending_tool_call = tool_names[0]
            
        elif msg.role == "tool" and msg.content:
            # Tool response received
            tool_name = pending_tool_call or "unknown_tool"
            
            try:
                # Try to parse tool response
                tool_response = json.loads(msg.content)
                
                if tool_response.get("success", True):  # Assume success if no success field
                    # Store the latest successful result for this tool
                    latest_tool_results[tool_name] = msg.content
                    
                    # Create context-aware summary
                    if tool_name == "generate_erc20_contract" and "solidity_code" in tool_response:
                        # Extract contract parameters for deployment context
                        contract_name = tool_response.get("contract_name", "Unknown")
                        token_name = tool_response.get("token_name", "Unknown")
                        token_symbol = tool_response.get("token_symbol", "UNK")
                        initial_supply = tool_response.get("initial_supply", 0)
                        
                        summary_msg = Message(
                            role="assistant",
                            content=f"Successfully generated ERC20 contract '{contract_name}' ({token_name}, symbol: {token_symbol}, initial_supply: {initial_supply}). Contract code ready. MUST OUTPUT FINAL_ANSWER with the Solidity code now."
                        )
                    elif tool_name == "compile_contract":
                        if tool_response.get("compilation_id"):
                            compilation_id = tool_response['compilation_id']
                            summary_msg = Message(
                                role="assistant",
                                content=f"Successfully compiled contract. Compilation ID: {compilation_id}. Ready for deployment. MUST OUTPUT FINAL_ANSWER with compilation success and next steps."
                            )
                        else:
                            summary_msg = Message(
                                role="assistant",
                                content=f"Compilation failed: {tool_response.get('message', 'Unknown error')}. MUST OUTPUT FINAL_ANSWER with error details."
                            )
                    elif tool_name == "prepare_deployment_transaction":
                        if tool_response.get("success", False) and tool_response.get("transaction"):
                            summary_msg = Message(
                                role="assistant",
                                content=f"Deployment transaction prepared successfully. Transaction data ready for user signing. MUST OUTPUT FINAL_ANSWER with transaction details now."
                            )
                        else:
                            error_msg = tool_response.get("message", "Unknown preparation error")
                            summary_msg = Message(
                                role="assistant",
                                content=f"Transaction preparation failed: {error_msg}"
                            )
                    elif tool_name == "broadcast_signed_transaction":
                        if tool_response.get("success", False):
                            contract_address = tool_response.get("contract_address", "N/A")
                            tx_hash = tool_response.get("transaction_hash", "N/A")
                            summary_msg = Message(
                                role="assistant",
                                content=f"Successfully broadcast deployment transaction. Contract address: {contract_address} (tx: {tx_hash})"
                            )
                        else:
                            error_msg = tool_response.get("message", "Unknown broadcast error")
                            summary_msg = Message(
                                role="assistant",
                                content=f"Transaction broadcast failed: {error_msg}"
                            )
                    elif tool_name == "deploy_contract":
                        if tool_response.get("success", False) and tool_response.get("contract_address"):
                            contract_address = tool_response["contract_address"]
                            tx_hash = tool_response.get("transaction_hash", "N/A")
                            summary_msg = Message(
                                role="assistant",
                                content=f"Successfully deployed contract at address: {contract_address} (tx: {tx_hash})"
                            )
                        else:
                            error_msg = tool_response.get("message", "Unknown deployment error")
                            summary_msg = Message(
                                role="assistant",
                                content=f"Deployment failed: {error_msg}"
                            )
                    elif tool_name == "generate_erc721_contract" and "solidity_code" in tool_response:
                        # Extract NFT parameters
                        contract_name = tool_response.get("contract_name", "Unknown")
                        token_name = tool_response.get("token_name", "Unknown")
                        token_symbol = tool_response.get("token_symbol", "UNK")
                        
                        summary_msg = Message(
                            role="assistant",
                            content=f"Successfully generated ERC721 contract '{contract_name}' ({token_name}, symbol: {token_symbol}). NFT contract code ready. MUST OUTPUT FINAL_ANSWER with the Solidity code now."
                        )
                    else:
                        summary_msg = Message(
                            role="assistant",
                            content=f"Successfully completed: {tool_name}. MUST OUTPUT FINAL_ANSWER with results now."
                        )
                    
                    conversation_flow.append(summary_msg)
                else:
                    # Tool failed
                    error_msg = tool_response.get("message", "Unknown error")
                    failure_msg = Message(
                        role="assistant",
                        content=f"Action failed ({tool_name}): {error_msg}"
                    )
                    conversation_flow.append(failure_msg)
                    
            except (json.JSONDecodeError, AttributeError):
                # Fallback for non-JSON responses
                summary_msg = Message(
                    role="assistant",
                    content=f"Completed action: {tool_name}"
                )
                conversation_flow.append(summary_msg)
            
            pending_tool_call = None
    
    # Handle any pending failed actions
    if pending_tool_call:
        failure_msg = Message(
            role="assistant", 
            content=f"Previous action ({pending_tool_call}) encountered an issue."
        )
        conversation_flow.append(failure_msg)
    
    # Add context about available tool results
    if latest_tool_results:
        context_items = []
        deployment_params = {}
        
        for tool, result in latest_tool_results.items():
            if tool == "generate_erc20_contract":
                try:
                    parsed = json.loads(result)
                    if "solidity_code" in parsed:
                        # Extract deployment parameters
                        deployment_params = {
                            "token_name": parsed.get("token_name", "Unknown"),
                            "token_symbol": parsed.get("token_symbol", "UNK"), 
                            "initial_supply": parsed.get("initial_supply", 0)
                        }
                        context_items.append("ERC20 contract code is available for compilation")
                except:
                    pass
            elif tool == "compile_contract":
                try:
                    parsed = json.loads(result)
                    if parsed.get("compilation_id"):
                        compilation_id = parsed['compilation_id']
                        context_items.append(f"Compiled contract ready for deployment (ID: {compilation_id})")
                except:
                    pass
        
        if context_items:
            availability_text = f"Available: {', '.join(context_items)}"
            
            # Add deployment parameter context if available
            if deployment_params and any(deployment_params.values()):
                param_text = f"Deployment parameters: initial_supply={deployment_params.get('initial_supply', 0)} for {deployment_params.get('token_name', 'token')}"
                availability_text += f". {param_text}"
            
            context_msg = Message(
                role="assistant",
                content=availability_text
            )
            conversation_flow.insert(-1, context_msg)
    
    # Keep recent context
    final_context = conversation_flow[-10:]
    
    # FALLBACK: If context seems incomplete, include some raw tool data
    # This helps ActionExecutionNode find actual data for compilation
    if len(final_context) < 3:  # Very little context
        # Add some recent tool messages for ActionExecutionNode
        recent_tool_messages = []
        for msg in messages[-20:]:  # Check last 20 messages
            if msg.role == "tool" and msg.content:
                # Add tool messages that contain useful data
                try:
                    tool_data = json.loads(msg.content)
                    if "solidity_code" in tool_data:
                        # This is useful for compilation
                        recent_tool_messages.append(msg)
                except:
                    pass
        
        # Add the most recent useful tool message
        if recent_tool_messages:
            final_context.append(recent_tool_messages[-1])
    
    return final_context