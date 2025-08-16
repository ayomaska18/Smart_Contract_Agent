import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ChatRequest {
  message: string;
  conversationId?: string;
}

export interface ChatResponse {
  success: boolean;
  data?: {
    backend_mode: string;
    conversation_id: string;
    message_id: string;
    response: string;
    timestamp: string;
  };
  error?: string;
}

class ApiService {
  private axiosInstance;

  constructor() {
    this.axiosInstance = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    try {
      const backendRequest = {
        message: request.message,
        conversation_id: request.conversationId
      };

      const response = await this.axiosInstance.post('/api/chat/', backendRequest);
      console.log("response.data from assistant:", response.data)

      return response.data as ChatResponse;

    } catch (error: any) {
      console.error('Backend API Error:', error);
      
      if (error.response) {
        const errorMessage = error.response.data?.error || error.message || 'Backend server error';
        console.error('Backend responded with error:', error.response.status, errorMessage);
        return {
          success: false,
          error: `Backend Error: ${errorMessage}`
        };
      }
      
      if (error.request) {
        console.error('Cannot reach backend server at:', API_BASE_URL);
        return {
          success: false,
          error: 'Cannot connect to backend server. Please ensure the backend is running on port 8000.'
        };
      }
      
      return {
        success: false,
        error: 'An unexpected error occurred while connecting to the backend'
      };
    }
  }

  async sendMessageReal(request: ChatRequest): Promise<ChatResponse> {
    return this.sendMessage(request);
  }

  async startNewConversation(): Promise<{ conversationId: string }> {
    try {
      const response = await this.axiosInstance.post('/api/chat/new');
      return response.data as { conversationId: string };
    } catch (error) {
      console.error('Error starting new conversation:', error);
      throw error;
    }
  }

  async *simulateStreamingResponse(message: string): AsyncGenerator<string, void, unknown> {
    yield "THOUGHT: Backend connection failed, running in frontend fallback mode...";
    await this.delay(1000);
    
    if (message.toLowerCase().includes('contract') || message.toLowerCase().includes('erc20') || message.toLowerCase().includes('erc721')) {
      yield "ACTION_NEEDED: simulate_contract_generation";
      await this.delay(1500);
      yield `FINAL_ANSWER: ⚠️ **Backend Disconnected - Frontend Fallback Mode**

I'm running in simulation mode because the backend server isn't available.

🏗️ **Expected Architecture**: 
Frontend → Backend API (port 8000) → ReAct Agent → MCP Server (port 8081)

📍 **Current Status**: Frontend Only (simulation mode)

Here's what I would help you with when the backend is connected:
• **Full ReAct reasoning** with THOUGHT → ACTION → ANSWER flow
• **Real ERC20/ERC721 generation** via MCP tools  
• **Smart contract compilation** and deployment
• **Blockchain interactions** and testing

Please ensure the backend server is running on port 8000 to access the full Smart Contract Assistant capabilities!`;
    } else {
      yield `FINAL_ANSWER: Hello! I'm your Smart Contract Assistant (frontend fallback mode).

⚠️ **Backend Connection Issue**: Cannot reach backend server
🔧 **Expected Backend**: http://localhost:8000
🏗️ **Full Architecture**: Frontend + Backend API + ReAct Agent + MCP Server

When properly connected, I can help you with:
• **ERC20 & ERC721** contract generation with full reasoning
• **Smart contract** compilation and deployment  
• **Blockchain** interactions and testing
• **Multi-step workflows** with conversation memory

Please start the backend server to access the complete functionality!`;
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export const apiService = new ApiService();