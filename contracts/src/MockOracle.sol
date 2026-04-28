// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title MockOracle
/// @notice Test-only oracle that always approves proofs.
///         Replace with a real TEE/ZKP oracle before mainnet.
contract MockOracle {
    function verifyProof(bytes calldata /* proof */) external pure returns (bool) {
        return true;
    }
}
