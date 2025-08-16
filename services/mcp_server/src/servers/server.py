import asyncio
import requests
import os
import json
import solcx
import uuid
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from fastmcp import FastMCP, Client, Context
from jinja2 import Environment, FileSystemLoader
from solcx import install_solc, set_solc_version
from web3 import Web3
from fastmcp.server.middleware import Middleware, MiddlewareContext

class LoggingMiddleware(Middleware):
    """Middleware that logs all MCP operations."""
    
    async def on_message(self, context: MiddlewareContext, call_next):
        """Called for all MCP messages."""
        print(f"Processing {context.method} from {context.source}")
        
        result = await call_next(context)
        
        print(f"Completed {context.method}")
        return result

load_dotenv()

private_key = os.getenv('metamask_private_key')
ethereum_sepolia_rpc = os.getenv('ethereum_sepolia_rpc')
wallet_address = os.getenv('wallet_address')

solcx.install_solc('0.8.27')
solcx.set_solc_version('0.8.27')

compilation_cache = {}

mcp = FastMCP(name="crypto_mcp", log_level="DEBUG")
mcp.add_middleware(LoggingMiddleware())

@mcp.tool(
    name="generate_erc20_contract",
    description="Generate an ERC20 token contract with advanced features"
)
async def generate_erc20_contract(
        contract_name: str = "MyToken", 
        token_name: str = "MyToken", 
        token_symbol: str = "MTK",
        initial_supply: int = 0,
        decimals: int = 18,
        mintable: bool = False,
        burnable: bool = False,
        pausable: bool = False,
        permit: bool = False,
        ownable: bool = False,
        capped: bool = False,
        max_supply: int = 0
    ) -> dict:
    
    # Auto-enable ownable for features that require it
    if mintable or pausable or capped:
        ownable = True

    env = Environment(loader=FileSystemLoader("/app/src"))
    template = env.get_template("contracts/erc20.sol")
    solidity_code = template.render(
        CONTRACT_NAME=contract_name,
        TOKEN_NAME=token_name,
        TOKEN_SYMBOL=token_symbol,
        INITIAL_SUPPLY=initial_supply,
        DECIMALS=decimals,
        mintable=mintable,
        burnable=burnable,
        pausable=pausable,
        permit=permit,
        ownable=ownable,
        capped=capped,
        max_supply=max_supply
    )

    return {
        "solidity_code": solidity_code,
        "contract_type": "ERC20",
        "features": {
            "mintable": mintable,
            "burnable": burnable, 
            "pausable": pausable,
            "permit": permit,
            "ownable": ownable,
            "capped": capped
        }
    }

# Keep the old method for backward compatibility
@mcp.tool(
    name="generate_contract",
    description="Generate an ERC20 contract with custom name and symbol (legacy method)"
)
async def generate_contract(
        contract_name: str = "MyToken", 
        token_name: str = "MyToken", 
        token_symbol: str = "MTK",
        mintable: bool = False,
        ownable: bool = False
    ) -> dict:
    
    return await generate_erc20_contract(
        contract_name=contract_name,
        token_name=token_name,
        token_symbol=token_symbol,
        mintable=mintable,
        ownable=ownable
    )

@mcp.tool(
    name="generate_erc721_contract",
    description="Generate an ERC721 NFT contract with advanced features"
)
async def generate_erc721_contract(
        contract_name: str = "MyNFT",
        token_name: str = "My NFT Collection", 
        token_symbol: str = "MNFT",
        base_uri: str = "",
        mintable: bool = True,
        burnable: bool = False,
        enumerable: bool = False,
        uri_storage: bool = False,
        ownable: bool = True,
        royalty: bool = False,
        royalty_percentage: int = 250,  # 2.5% in basis points
        max_supply: int = 0  # 0 = unlimited
    ) -> dict:

    env = Environment(loader=FileSystemLoader("/app/src"))
    template = env.get_template("contracts/erc721.sol")
    solidity_code = template.render(
        CONTRACT_NAME=contract_name,
        TOKEN_NAME=token_name,
        TOKEN_SYMBOL=token_symbol,
        base_uri=base_uri,
        mintable=mintable,
        burnable=burnable,
        enumerable=enumerable,
        uri_storage=uri_storage,
        ownable=ownable,
        royalty=royalty,
        royalty_percentage=royalty_percentage,
        max_supply=max_supply
    )

    return {
        "solidity_code": solidity_code,
        "contract_type": "ERC721",
        "features": {
            "mintable": mintable,
            "burnable": burnable,
            "enumerable": enumerable,
            "uri_storage": uri_storage,
            "ownable": ownable,
            "royalty": royalty,
            "max_supply": max_supply
        }
    }

@mcp.tool(
    name="compile_contract",
    description="Compile Solidity code and return compilation ID"
)
async def compile_contract(solidity_code: str) -> dict:
    try:
        print('here is the solidity code ', solidity_code)
        compiled = solcx.compile_source(
            solidity_code,
            output_values=["abi", "bin"],
            import_remappings=["@openzeppelin=node_modules/@openzeppelin"],
            allow_paths="."
        )

        _, contract_data = next(iter(compiled.items()))
        abi = contract_data['abi']
        bytecode = contract_data['bin']
        
        compilation_id = str(uuid.uuid4())
        compilation_cache[compilation_id] = {
            "abi": abi,
            "bytecode": bytecode,
            "source_code": solidity_code
        }

        return {
            "compilation_id": compilation_id,
            "success": True,
            "message": "Contract compiled successfully. Use get_abi and get_bytecode tools to retrieve data."
        }
    except Exception as e:
        return {
            "compilation_id": None,
            "success": False,
            "message": f"Compilation failed: {str(e)}"
        }

@mcp.tool(
    name="get_abi",
    description="Get contract ABI using compilation ID"
)
async def get_abi(compilation_id: str) -> dict:
    if compilation_id not in compilation_cache:
        return {
            "abi": None,
            "success": False,
            "message": "Invalid compilation ID"
        }
    
    return {
        "abi": compilation_cache[compilation_id]["abi"],
        "success": True,
        "message": "ABI retrieved successfully"
    }

@mcp.tool(
    name="get_bytecode",
    description="Get contract bytecode using compilation ID"
)
async def get_bytecode(compilation_id: str) -> dict:
    if compilation_id not in compilation_cache:
        return {
            "bytecode": None,
            "success": False,
            "message": "Invalid compilation ID"
        }
    
    return {
        "bytecode": compilation_cache[compilation_id]["bytecode"],
        "success": True,
        "message": "Bytecode retrieved successfully"
    }

@mcp.tool(
    name="deploy_contract",
    description="Deploy compiled contract to Ethereum network using compilation ID"
)
async def deploy_contract(compilation_id: str, initial_owner: str = wallet_address, gas_limit: int = 2000000, gas_price_gwei: int = 10) -> dict:
    if compilation_id not in compilation_cache:
        return {
            "contract_address": None,
            "transaction_hash": None,
            "success": False,
            "message": "Invalid compilation ID"
        }
    
    try:
        # Check environment variables first
        if not private_key:
            return {
                "contract_address": None,
                "transaction_hash": None,
                "success": False,
                "message": "Private key not configured in environment variables"
            }
        
        if not ethereum_sepolia_rpc:
            return {
                "contract_address": None,
                "transaction_hash": None,
                "success": False,
                "message": "Ethereum RPC URL not configured in environment variables"
            }
        
        abi = compilation_cache[compilation_id]["abi"]
        bytecode = compilation_cache[compilation_id]["bytecode"]

        print("contract abi", abi)
        
        print(f"[DEBUG] Attempting to connect to RPC: {ethereum_sepolia_rpc}")
        w3 = Web3(Web3.HTTPProvider(ethereum_sepolia_rpc))
        
        try:
            # Test connection with more detailed error info
            is_connected = w3.is_connected()
            print(f"[DEBUG] Connection status: {is_connected}")
            
            if is_connected:
                latest_block = w3.eth.block_number
                print(f"[DEBUG] Latest block number: {latest_block}")
            else:
                # Try to get more specific error info
                try:
                    w3.eth.block_number
                except Exception as conn_error:
                    print(f"[DEBUG] Connection error details: {conn_error}")
                    return {
                        "contract_address": None,
                        "transaction_hash": None,
                        "success": False,
                        "message": f"Failed to connect to Ethereum network: {str(conn_error)}"
                    }
                
                return {
                    "contract_address": None,
                    "transaction_hash": None,
                    "success": False,
                    "message": "Failed to connect to Ethereum network"
                }
        except Exception as e:
            print(f"[DEBUG] Connection exception: {e}")
            return {
                "contract_address": None,
                "transaction_hash": None,
                "success": False,
                "message": f"Network connection error: {str(e)}"
            }
        
        account = w3.eth.account.from_key(private_key).address
        nonce = w3.eth.get_transaction_count(account)

        # Use deployer address as initial owner if not specified
        if initial_owner is None:
            initial_owner = account

        # Ensure address is in proper checksum format
        initial_owner = w3.to_checksum_address(initial_owner)

        erc20_token = w3.eth.contract(abi=abi, bytecode=bytecode)
        
        # Check if constructor requires parameters by examining ABI
        constructor_inputs = []
        for item in abi:
            if item.get('type') == 'constructor':
                constructor_inputs = item.get('inputs', [])
                break
        
        print("Constructor Inputs:", constructor_inputs)
        
        # Build constructor arguments based on ABI
        constructor_args = []
        if constructor_inputs:
            # For ownable contracts, we expect exactly one address parameter
            if len(constructor_inputs) == 1 and constructor_inputs[0]['type'] == 'address':
                constructor_args.append(initial_owner)
            else:
                # Fallback to name-based detection
                for input_param in constructor_inputs:
                    param_name = input_param['name'].lower()
                    if 'owner' in param_name or 'initial' in param_name:
                        constructor_args.append(initial_owner)

        print(f"[DEBUG] constructor_inputs: {constructor_inputs}")
        print(f"[DEBUG] constructor_args: {constructor_args}")
        print(f"[DEBUG] initial_owner: {initial_owner}")
        
        transaction = erc20_token.constructor(*constructor_args).build_transaction({
            'from': account,
            'nonce': nonce,
            'gas': gas_limit,
            'gasPrice': w3.to_wei(gas_price_gwei, 'gwei')
        })
        
        signed = w3.eth.account.sign_transaction(transaction, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        # Verify owner was set correctly (if contract has owner function)
        deployed_contract = w3.eth.contract(address=receipt.contractAddress, abi=abi)
        actual_owner = None
        try:
            if hasattr(deployed_contract.functions, 'owner'):
                actual_owner = deployed_contract.functions.owner().call()
                print(f"[DEBUG] Deployed contract owner: {actual_owner}")
        except Exception as e:
            print(f"[DEBUG] Could not read owner: {e}")
        
        return {
            "contract_address": receipt.contractAddress,
            "transaction_hash": tx_hash.hex(),
            "success": True,
            "message": "Contract deployed successfully",
            "gas_used": receipt.gasUsed,
            "block_number": receipt.blockNumber,
            "constructor_args": constructor_args,
            "initial_owner_used": initial_owner,
            "actual_owner": actual_owner
        }
        
    except Exception as e:
        return {
            "contract_address": None,
            "transaction_hash": None,
            "success": False,
            "message": f"Deployment failed: {str(e)}"
        }

if __name__ == '__main__':
    mcp.run(transport="http", host="0.0.0.0", port=8081)