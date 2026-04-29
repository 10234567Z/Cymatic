// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

struct PreimageProofOutput {
    bool isValid;
    bytes32 dataHash;
}

struct TransferValidityProofOutput {
    bool isValid;
    bytes32 oldDataHash;
    bytes32 newDataHash;
    address receiver;
    bytes16 sealedKey;
}

interface IERC7857DataVerifier {
    /// @notice Verify preimage proofs for data ownership
    /// @param _proofs Array of preimage proofs
    /// @return Array of proof outputs with validity and data hashes
    function verifyPreimage(bytes[] calldata _proofs)
        external
        view
        returns (PreimageProofOutput[] memory);

    /// @notice Verify transfer validity proofs
    /// @param _proofs Array of transfer validity proofs
    /// @return Array of proof outputs with validity and sealed keys
    function verifyTransferValidity(bytes[] calldata _proofs)
        external
        view
        returns (TransferValidityProofOutput[] memory);
}
