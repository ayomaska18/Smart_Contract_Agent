// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
{% if mintable or ownable %}import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";{% endif %}
{% if burnable %}import {ERC20Burnable} from "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";{% endif %}

contract {{ CONTRACT_NAME }} is ERC20{% if burnable %}, ERC20Burnable{% endif %}{% if ownable %}, Ownable{% endif %} {
    constructor(
        {% if ownable %}address initialOwner{% endif %}
    )
        ERC20("{{ TOKEN_NAME }}", "{{ TOKEN_SYMBOL }}")
        {% if ownable %}Ownable(initialOwner){% endif %}
    {}

    {% if mintable %}
    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }
    {% endif %}
}
