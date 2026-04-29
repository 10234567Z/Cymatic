// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./interfaces/IERC7857DataVerifier.sol";

/// @notice Mock verifier for testing ERC-7857 functionality
contract MockVerifier is IERC7857DataVerifier {
    /// @notice Always returns valid preimage proofs with the data hash of the proof itself
    function verifyPreimage(bytes[] calldata _proofs)
        external
        pure
        returns (PreimageProofOutput[] memory)
    {
        PreimageProofOutput[] memory outputs = new PreimageProofOutput[](_proofs.length);
        for (uint256 i = 0; i < _proofs.length; i++) {
            outputs[i] = PreimageProofOutput({
                isValid: true,
                dataHash: keccak256(_proofs[i])
            });
        }
        return outputs;
    }

    /// @notice Always returns valid transfer proofs with derived sealed key and receiver
    /// @dev For testing: receiver is encoded as the first 20 bytes of the proof (in abi.encodePacked format)
    function verifyTransferValidity(bytes[] calldata _proofs)
        external
        pure
        returns (TransferValidityProofOutput[] memory)
    {
        TransferValidityProofOutput[] memory outputs = new TransferValidityProofOutput[](_proofs.length);
        for (uint256 i = 0; i < _proofs.length; i++) {
            bytes32 oldHash = keccak256(abi.encodePacked("old_", _proofs[i]));
            bytes32 newHash = keccak256(abi.encodePacked("new_", _proofs[i]));
            bytes16 sealedKey = bytes16(keccak256(_proofs[i]));
            
            // For testing, we'll use a predictable receiver or default to address(0) if proof is too short
            // In a real scenario, this would be verified against actual proof data
            address receiver = address(0);
            if (_proofs[i].length >= 20) {
                // Extract receiver from first 20 bytes of proof
                receiver = address(bytes20(_proofs[i][:20]));
            }

            outputs[i] = TransferValidityProofOutput({
                isValid: true,
                oldDataHash: oldHash,
                newDataHash: newHash,
                receiver: receiver,
                sealedKey: sealedKey
            });
        }
        return outputs;
    }
}
