# Smart Contract Assistant

An AI-powered smart contract development platform that combines a Next.js frontend, FastAPI backend, and MCP (Model Context Protocol) server for intelligent blockchain development assistance.

## Architecture

The application follows a modern 3-tier architecture:

```
Frontend (Next.js) → Backend API (FastAPI) → MCP Server (FastMCP)
   
```

### Components

- **Frontend**: Next.js React application with real-time chat interface
- **Backend**: FastAPI server with ReAct agent integration
- **MCP Server**: Smart contract tools and blockchain utilities
- **Database**: PostgreSQL for event sourcing and conversation history
- **Framework**: Built on Grafi - an event-driven AI agent framework

## Features

-  **AI-Powered Contract Generation**: Create ERC20 & ERC721 tokens with natural language
-  **Smart Contract Compilation**: Automated Solidity compilation and validation  
-  **Blockchain Deployment**: Deploy contracts to Ethereum testnets
-  **Interactive Chat Interface**: Conversational AI with persistent context
-  **ReAct Agent**: Advanced reasoning with THOUGHT → ACTION → ANSWER flow
-  **Event Sourcing**: Complete audit trail and state recovery
-  **Docker Containerized**: Easy deployment and development

##  Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for local development)
- Python 3.13+ (for local development)

### 1. Clone Repository

```bash
git clone https://github.com/ayomaska18/Smart_Contract_Agent.git
cd Smart_Contract_Agent
```

### 2. Environment Setup

Copy and configure environment variables:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# AI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
OPENAI_SYSTEM_MESSAGE="You are a helpful AI assistant specialized in smart contract development."

# Blockchain Configuration  
METAMASK_PRIVATE_KEY=your_metamask_private_key_here
ETHEREUM_SEPOLIA_RPC=https://eth-sepolia.g.alchemy.com/v2/your_project_id
WALLET_ADDRESS=0xYourWalletAddressHere

# Service URLs
MCP_SERVER_URL=http://mcp_server:8081/mcp/
NEXT_PUBLIC_API_URL=http://localhost:8000
BACKEND_API_URL=http://backend:8000

# Database Configuration
POSTGRES_DB=grafi_test_db
POSTGRES_USER=testing
POSTGRES_PASSWORD=testing
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Admin Configuration
pg_admin_email=admin@admin.com
pg_admin_password=admin
```

### 3. Start Application

```bash
# Start all services
docker-compose up --build

# Or run in background
docker-compose up --build -d
```

### 4. Access Services

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MCP Server**: http://localhost:8081/mcp/
- **pgAdmin**: http://localhost:5050

##  Development

### Local Development Setup

1. **Install Python Dependencies**:
   ```bash
   pip install uv
   uv sync
   ```

2. **Install Node Dependencies**:
   ```bash
   npm install
   cd apps/frontend && npm install
   ```

3. **Run Services Individually**:
   ```bash
   # Backend (in terminal 1)
   cd apps/backend
   uv run python api_server.py
   
   # Frontend (in terminal 2) 
   cd apps/frontend
   npm run dev
   
   # MCP Server (in terminal 3)
   cd services/mcp_server
   uv run src/servers/server.py
   ```

### Code Quality

```bash
# Linting
ruff check .

# Type checking  
mypy .

# Formatting
ruff format .

# Tests
pytest
```

## 📁 Project Structure

```
├── apps/
│   ├── backend/           # FastAPI backend
│   │   ├── routers/       # API endpoints
│   │   ├── agents/        # ReAct agent implementation
│   │   └── memory/        # Conversation context
│   └── frontend/          # Next.js frontend
│       ├── src/components/# React components
│       ├── src/services/ # API client
│       └── src/types/    # TypeScript definitions
├── services/
│   └── mcp_server/       # Smart contract MCP server
│       ├── src/tools/    # Blockchain tools
│       └── src/contracts/# Solidity templates
├── docker/               # Docker configurations
└── docker-compose.yaml  # Service orchestration
```

##  Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for AI responses | `sk-proj-...` |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o` |
| `METAMASK_PRIVATE_KEY` | Wallet private key for deployments | `0x...` |
| `ETHEREUM_SEPOLIA_RPC` | Ethereum testnet RPC URL | `https://eth-sepolia.g.alchemy.com/v2/...` |
| `WALLET_ADDRESS` | Deployment wallet address | `0x...` |

### Docker Services

- **postgres**: PostgreSQL database
- **pgadmin**: Database administration interface
- **mcp_server**: Smart contract tools server
- **backend**: FastAPI application server
- **frontend**: Next.js web application

##  Usage Examples

### Creating an ERC20 Token

```
User: Create an ERC20 token called "MyToken" with symbol "MTK"

AI Assistant:
THOUGHT: User wants to create an ERC20 token. I need to use the MCP server to generate the contract.

ACTION: generate_erc20_contract
- Name: MyToken  
- Symbol: MTK
- Initial Supply: 1,000,000 tokens

FINAL_ANSWER: I've created an ERC20 token contract for you!

// ERC20 Token Contract Generated
contract MyToken is ERC20 {
    constructor() ERC20("MyToken", "MTK") {
        _mint(msg.sender, 1000000 * 10**decimals());
    }
}

The contract has been generated and compiled successfully. Would you like me to deploy it to testnet?
```

### Deploying a Contract

```
User: Deploy the MyToken contract to Sepolia testnet

AI Assistant: 
THOUGHT: User wants to deploy the contract. I'll use the deployment tool with the configured wallet.

ACTION: deploy_contract
- Network: Sepolia
- Contract: MyToken.sol  
- Wallet: 0x8e8aA0a...

FINAL_ANSWER: ✅ Contract deployed successfully!

📋 **Deployment Details:**
- **Contract Address**: `0x742d35Cc7abC5A2C7B8C1C3d3F0F8E2B91d4b3eF`
- **Transaction Hash**: `0x5f9ea17d5b5f4e8c7a2c3b8e9f0a1d2c4e6f8a9b`
- **Network**: Sepolia Testnet
- **Gas Used**: 847,392
- **Deployer**: `0x8e8aA0a4312178E04553da4aF68Ec376c673d86E`

🔗 **View on Etherscan**: https://sepolia.etherscan.io/address/0x742d35Cc7abC5A2C7B8C1C3d3F0F8E2B91d4b3eF
```

## 🙏 Acknowledgments

- **Graphite Framework**: Event-driven AI agent architecture
- **FastMCP**: Model Context Protocol implementation
- **OpenAI**: GPT models for AI responses
- **OpenZeppelin**: Smart contract templates
- **Next.js**: React framework for frontend
- **FastAPI**: Python web framework for backend

