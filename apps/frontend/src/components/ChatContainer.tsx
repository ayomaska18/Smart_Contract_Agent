import React, { useState, useRef, useEffect } from 'react';
import { Message, ChatState } from '../types/Chat';
import { apiService } from '../services/api';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';
import ChatHeader from './ChatHeader';
import { AlertCircle } from 'lucide-react';
import { useIsClient } from '../hooks/useIsClient';
import './Chat.css';

const ChatContainer: React.FC = () => {
  const isClient = useIsClient();
  const [chatState, setChatState] = useState<ChatState>(() => ({
    messages: [],
    isLoading: false,
    conversationId: null,
  }));  
  
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatState.messages]);

  useEffect(() => {
    if (chatState.messages.length === 0) {
      const welcomeMessage: Message = {
        id: 'welcome',
        role: 'assistant',
        content: 'Hello! I\'m your Smart Contract Assistant. I can help you:\n\n• Generate ERC20 and ERC721 contracts\n• Compile Solidity code\n• Deploy contracts to testnets\n• Interact with deployed contracts\n\nWhat would you like to create today?',
        timestamp: new Date(),
      };
      
      setChatState(prev => ({
        ...prev,
        messages: [welcomeMessage],
      }));
    }
  }, [chatState.messages.length]);

  const generateMessageId = () => {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
  };

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    const userMessage: Message = {
      id: generateMessageId(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };

    setChatState(prev => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isLoading: true,
    }));

    setError(null);

    try {
      const assistantMessageId = generateMessageId();
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      };

      setChatState(prev => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      try {
        const currentConversationId = chatState.conversationId;
        console.log('Current chat state:', chatState);
        console.log('Sending message with conversation ID:', currentConversationId);

        const response = await apiService.sendMessageReal({
          message: content,
          conversationId: chatState.conversationId ?? undefined,
        });

        console.log('Full response structure:', JSON.stringify(response, null, 2));
        console.log('response.success:', response.success);
        console.log('response.data:', response.data);
        console.log('typeof response.data:', typeof response.data);
        
        if (response.success && response.data) {
          const backendConversationId = response.data.conversation_id;

          const newConversationId = currentConversationId || backendConversationId;
          console.log('Response conversation ID:', backendConversationId);
          console.log('Current conversation ID:', currentConversationId);
          console.log('New conversation ID:', newConversationId);
          
          setChatState(prev => {
            console.log('Previous state conversation ID:', prev.conversationId);
            return {
              ...prev,
              conversationId: newConversationId,
              messages: prev.messages.map(msg => 
                msg.id === assistantMessageId 
                  ? { ...msg, content: response.data!.response, isStreaming: false }
                  : msg
              ),
            };
          });
        } else {
          throw new Error(response.error || 'Failed to get response');
        }
      } catch (apiError) {
        console.warn('API call failed, using simulation:', apiError);

        let fullResponse = '';
        for await (const chunk of apiService.simulateStreamingResponse(content)) {
          const newResponse = fullResponse + (fullResponse ? '\n\n' : '') + chunk;
          fullResponse = newResponse;
          
          setChatState(prev => ({
            ...prev,
            conversationId: prev.conversationId, 
            messages: prev.messages.map(msg => 
              msg.id === assistantMessageId 
                ? { ...msg, content: newResponse }
                : msg
            ),
          }));

          await new Promise(resolve => setTimeout(resolve, 100));
        }
      }

      setChatState(prev => ({
        ...prev,
        messages: prev.messages.map(msg => 
          msg.id === assistantMessageId 
            ? { ...msg, isStreaming: false }
            : msg
        ),
        isLoading: false,
      }));

    } catch (err) {
      console.error('Error sending message:', err);
      setError('Failed to send message. Please try again.');
      
      setChatState(prev => ({
        ...prev,
        isLoading: false,
      }));
    }
  };

  const handleNewChat = () => {
    setChatState({
      messages: [],
      isLoading: false,
      conversationId: null, 
    });
    setError(null);
  };

  return (
    <div className="chat-container">
      <ChatHeader 
        onNewChat={handleNewChat}
        conversationId={chatState.conversationId}
      />
      
      {/* Error Banner */}
      {error && (
        <div className="error-banner">
          <div className="error-content">
            <div className="error-message">
              <AlertCircle size={20} style={{ marginRight: '8px' }} />
              <span>{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="error-close"
            >
              ×
            </button>
          </div>
        </div>
      )}
      
      {/* Messages Area */}
      <div className="messages-area">
        <div className="messages-container">
          {chatState.messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
      
      {/* Input Area */}
      <div className="input-area">
        <div className="input-container">
          <ChatInput
            onSendMessage={handleSendMessage}
            isLoading={chatState.isLoading}
            disabled={!!error}
          />
        </div>
      </div>
    </div>
  );
};

export default ChatContainer;