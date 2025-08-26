from grafi.common.models.function_spec import FunctionSpec, ParametersSchema, ParameterSchema

def create_mcp_function_specs():
    """Create function specifications for MCP tools that the ActionExecutionNode can use."""

    generate_erc20_spec = FunctionSpec(
        name="generate_erc20_contract",
        description="Generate an ERC20 token contract with advanced features",
        parameters=ParametersSchema(
            properties={
                "contract_name": ParameterSchema(type="string", description="Name of the contract class (PascalCase)"),
                "token_name": ParameterSchema(type="string", description="Human readable token name"),
                "token_symbol": ParameterSchema(type="string", description="Token symbol (uppercase)"),
                "initial_supply": ParameterSchema(type="integer", description="Initial token supply"),
                "decimals": ParameterSchema(type="integer", description="Token decimals (default: 18)"),
                "mintable": ParameterSchema(type="boolean", description="Enable minting functionality"),
                "burnable": ParameterSchema(type="boolean", description="Enable burning functionality"),
                "pausable": ParameterSchema(type="boolean", description="Enable pausing functionality"),
                "permit": ParameterSchema(type="boolean", description="Enable EIP-2612 gasless approvals"),
                "ownable": ParameterSchema(type="boolean", description="Enable ownership functionality"),
                "capped": ParameterSchema(type="boolean", description="Enable supply cap"),
                "max_supply": ParameterSchema(type="integer", description="Maximum supply if capped")
            },
            required=["contract_name", "token_name", "token_symbol"]
        )
    )
    
    generate_erc721_spec = FunctionSpec(
        name="generate_erc721_contract",
        description="Generate an ERC721 NFT contract with advanced features",
        parameters=ParametersSchema(
            properties={
                "contract_name": ParameterSchema(type="string", description="Name of the contract class"),
                "token_name": ParameterSchema(type="string", description="NFT collection name"),
                "token_symbol": ParameterSchema(type="string", description="NFT collection symbol"),
                "base_uri": ParameterSchema(type="string", description="Base URI for metadata"),
                "mintable": ParameterSchema(type="boolean", description="Enable minting functionality"),
                "burnable": ParameterSchema(type="boolean", description="Enable burning functionality"),
                "enumerable": ParameterSchema(type="boolean", description="Enable enumerable extension"),
                "uri_storage": ParameterSchema(type="boolean", description="Enable URI storage extension"),
                "ownable": ParameterSchema(type="boolean", description="Enable ownership functionality"),
                "royalty": ParameterSchema(type="boolean", description="Enable EIP-2981 royalties"),
                "royalty_percentage": ParameterSchema(type="integer", description="Royalty percentage in basis points"),
                "max_supply": ParameterSchema(type="integer", description="Maximum NFT supply")
            },
            required=["contract_name", "token_name", "token_symbol"]
        )
    )

    compile_contract_spec = FunctionSpec(
        name="compile_contract",
        description="Compile Solidity code and return compilation ID",
        parameters=ParametersSchema(
            properties={
                "solidity_code": ParameterSchema(type="string", description="The Solidity source code to compile")
            },
            required=["solidity_code"]
        )
    )
    
    deploy_contract_spec = FunctionSpec(
        name="deploy_contract",
        description="Deploy compiled contract to blockchain network using server wallet (legacy method)",
        parameters=ParametersSchema(
            properties={
                "compilation_id": ParameterSchema(type="string", description="The compilation ID from compile_contract"),
                "initial_owner": ParameterSchema(type="string", description="Initial owner address (optional, defaults to server wallet address)"),
                "gas_limit": ParameterSchema(type="integer", description="Gas limit for deployment (optional, default: 2000000)"),
                "gas_price_gwei": ParameterSchema(type="integer", description="Gas price in Gwei (optional, default: 10)")
            },
            required=["compilation_id"]
        )
    )

    prepare_deployment_transaction_spec = FunctionSpec(
        name="prepare_deployment_transaction",
        description="Prepare deployment transaction for user wallet signing (preferred method)",
        parameters=ParametersSchema(
            properties={
                "compilation_id": ParameterSchema(type="string", description="The compilation ID from compile_contract"),
                "user_wallet_address": ParameterSchema(type="string", description="User's wallet address that will sign and pay for the deployment"),
                "gas_limit": ParameterSchema(type="integer", description="Gas limit for deployment (optional, default: 2000000)"),
                "gas_price_gwei": ParameterSchema(type="integer", description="Gas price in Gwei (optional, default: 10)")
            },
            required=["compilation_id", "user_wallet_address"]
        )
    )

    broadcast_signed_transaction_spec = FunctionSpec(
        name="broadcast_signed_transaction",
        description="Broadcast user's signed transaction to complete contract deployment",
        parameters=ParametersSchema(
            properties={
                "signed_transaction_hex": ParameterSchema(type="string", description="The signed transaction data from user's wallet in hex format")
            },
            required=["signed_transaction_hex"]
        )
    )

    get_abi_spec = FunctionSpec(
        name="get_abi",
        description="Get contract ABI using compilation ID",
        parameters=ParametersSchema(
            properties={
                "compilation_id": ParameterSchema(type="string", description="The compilation ID")
            },
            required=["compilation_id"]
        )
    )

    get_bytecode_spec = FunctionSpec(
        name="get_bytecode", 
        description="Get contract bytecode using compilation ID",
        parameters=ParametersSchema(
            properties={
                "compilation_id": ParameterSchema(type="string", description="The compilation ID")
            },
            required=["compilation_id"]
        )
    )

    return [
        generate_erc20_spec,
        generate_erc721_spec,
        compile_contract_spec,
        deploy_contract_spec,
        prepare_deployment_transaction_spec,
        broadcast_signed_transaction_spec,
        get_abi_spec,
        get_bytecode_spec
    ]
