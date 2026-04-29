// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

import "./IERC7857DataVerifier.sol";

interface IERC7857 {
    /// @dev Emitted when a new functional NFT is minted
    event Minted(
        uint256 indexed _tokenId,
        address indexed _creator,
        address indexed _owner,
        bytes32[] _dataHashes,
        string[] _dataDescriptions
    );

    /// @dev Emitted when a user is authorized to use the data
    event Authorization(address indexed _from, address indexed _to, uint256 indexed _tokenId);

    /// @dev Emitted when data is transferred with ownership
    event Transferred(uint256 indexed _tokenId, address indexed _from, address indexed _to);

    /// @dev Emitted when data is cloned
    event Cloned(uint256 indexed _tokenId, uint256 indexed _newTokenId, address _from, address _to);

    /// @dev Emitted when a sealed key is published
    event PublishedSealedKey(address indexed _to, uint256 indexed _tokenId, bytes16[] _sealedKeys);

    /// @dev Emitted when token data is updated
    event Updated(uint256 indexed _tokenId, bytes32[] _oldDataHashes, bytes32[] _newDataHashes);

    /// @dev Emitted when approval is granted
    event Approval(address indexed _from, address indexed _to, uint256 indexed _tokenId);

    /// @dev Emitted when approval for all is set
    event ApprovalForAll(address indexed _owner, address indexed _operator, bool _approved);

    /// @notice The verifier interface that this NFT uses
    function verifier() external view returns (IERC7857DataVerifier);

    /// @notice Mint new functional NFT with functional data ownership proof
    /// @param _proofs Proof of data ownership
    /// @param _dataDescriptions Descriptions of the data
    /// @param _to The address to mint the token for
    /// @return _tokenId The ID of the newly minted token
    function mint(
        bytes[] calldata _proofs,
        string[] calldata _dataDescriptions,
        address _to
    ) external payable returns (uint256 _tokenId);

    /// @notice Update token data with proofs
    /// @param _tokenId Token to update
    /// @param _proofs Proofs of new data ownership
    function update(uint256 _tokenId, bytes[] calldata _proofs) external;

    /// @notice Transfer data with ownership
    /// @param _to Address to transfer data to
    /// @param _tokenId The token to transfer
    /// @param _proofs Proofs of data available for recipient
    function transfer(address _to, uint256 _tokenId, bytes[] calldata _proofs) external;

    /// @notice Transfer from another owner with approval
    /// @param _from The current owner
    /// @param _to Address to transfer data to
    /// @param _tokenId The token to transfer
    /// @param _proofs Proofs of data available for recipient
    function transferFrom(
        address _from,
        address _to,
        uint256 _tokenId,
        bytes[] calldata _proofs
    ) external;

    /// @notice Clone data to a new owner
    /// @param _to Address to clone data to
    /// @param _tokenId The token to clone
    /// @param _proofs Proofs of data available for recipient
    /// @return _newTokenId The ID of the newly cloned token
    function clone(
        address _to,
        uint256 _tokenId,
        bytes[] calldata _proofs
    ) external returns (uint256 _newTokenId);

    /// @notice Clone data from another owner with approval
    /// @param _from The current owner
    /// @param _to Address to clone data to
    /// @param _tokenId The token to clone
    /// @param _proofs Proofs of data available for recipient
    /// @return _newTokenId The ID of the newly cloned token
    function cloneFrom(
        address _from,
        address _to,
        uint256 _tokenId,
        bytes[] calldata _proofs
    ) external returns (uint256 _newTokenId);

    /// @notice Add authorized user
    /// @param _tokenId The token
    /// @param _user The user to authorize
    function authorizeUsage(uint256 _tokenId, address _user) external;

    /// @notice Get token owner
    /// @param _tokenId The token identifier
    /// @return The current owner of the token
    function ownerOf(uint256 _tokenId) external view returns (address);

    /// @notice Get the authorized users of a token
    /// @param _tokenId The token identifier
    /// @return The current authorized users of the token
    function authorizedUsersOf(uint256 _tokenId) external view returns (address[] memory);

    /// @notice Approve a user for a specific token
    /// @param _to Address to approve
    /// @param _tokenId The token to approve for
    function approve(address _to, uint256 _tokenId) external;

    /// @notice Approve an operator for all tokens
    /// @param _to Address to approve
    /// @param _approved Whether to approve or revoke
    function setApprovalForAll(address _to, bool _approved) external;

    /// @notice Get approved address for a token
    /// @param _tokenId The token identifier
    /// @return The approved address
    function getApproved(uint256 _tokenId) external view returns (address);

    /// @notice Check if an operator is approved for all tokens
    /// @param _owner The owner address
    /// @param _operator The operator address
    /// @return Whether the operator is approved for all
    function isApprovedForAll(address _owner, address _operator) external view returns (bool);
}
