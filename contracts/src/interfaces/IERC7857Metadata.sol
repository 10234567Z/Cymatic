// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

interface IERC7857Metadata {
    /// @notice Get data hashes for a token
    /// @param _tokenId The token identifier
    /// @return Array of data hashes
    function dataHashesOf(uint256 _tokenId) external view returns (bytes32[] memory);

    /// @notice Get data descriptions for a token
    /// @param _tokenId The token identifier
    /// @return Array of data descriptions
    function dataDescriptionsOf(uint256 _tokenId) external view returns (string[] memory);

    /// @notice Get token URI
    /// @param _tokenId The token identifier
    /// @return The token URI
    function tokenURI(uint256 _tokenId) external view returns (string memory);
}
