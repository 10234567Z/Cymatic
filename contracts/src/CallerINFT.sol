// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "./interfaces/IERC7857.sol";
import "./interfaces/IERC7857Metadata.sol";
import "./interfaces/IERC7857DataVerifier.sol";

/// @title CallerINFT
/// @notice ERC-7857 compliant agent NFT for Cymatic caller identity.
///         Each phone caller gets exactly one token with encrypted metadata
///         backed by cryptographic proofs and 0G Storage.
contract CallerINFT is AccessControl, IERC7857, IERC7857Metadata {
    error ZeroVerifierAddress();
    error ZeroAddress();
    error LengthMismatch();
    error InvalidPreimageProof();
    error InvalidTransferValidityProof();
    error ReceiverMismatch();
    error NotOwner();
    error NotApproved();
    error TokenNotExist();

    struct TokenData {
        address owner;
        string[] dataDescriptions;
        bytes32[] dataHashes;
        address[] authorizedUsers;
        address approvedUser;
    }

    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    mapping(uint256 => TokenData) private _tokens;
    mapping(address => mapping(address => bool)) private _operatorApprovals;
    uint256 private _nextTokenId = 1;

    string public tokenName;
    string public tokenSymbol;
    string public chainURL;
    string public indexerURL;
    IERC7857DataVerifier public verifier;

    // ─ Constructor ─

    constructor(
        string memory name_,
        string memory symbol_,
        address verifierAddr,
        string memory chainURL_,
        string memory indexerURL_
    ) {
        if (verifierAddr == address(0)) revert ZeroVerifierAddress();
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);

        tokenName = name_;
        tokenSymbol = symbol_;
        chainURL = chainURL_;
        indexerURL = indexerURL_;
        verifier = IERC7857DataVerifier(verifierAddr);
    }

    // ─ Basic getters ─

    function name() public view virtual returns (string memory) {
        return tokenName;
    }

    function symbol() public view virtual returns (string memory) {
        return tokenSymbol;
    }

    // ─ Admin functions ─

    function updateVerifier(address newVerifier) public virtual onlyRole(ADMIN_ROLE) {
        if (newVerifier == address(0)) revert ZeroAddress();
        verifier = IERC7857DataVerifier(newVerifier);
    }

    function updateURLs(string memory newChainURL, string memory newIndexerURL)
        public
        virtual
        onlyRole(ADMIN_ROLE)
    {
        chainURL = newChainURL;
        indexerURL = newIndexerURL;
    }

    // ─ Core ERC-7857 functions ─

    function mint(bytes[] calldata proofs, string[] calldata dataDescriptions, address to)
        public
        payable
        virtual
        returns (uint256 tokenId)
    {
        if (dataDescriptions.length != proofs.length) revert LengthMismatch();
        if (to == address(0)) {
            to = msg.sender;
        }

        PreimageProofOutput[] memory proofOutputs = verifier.verifyPreimage(proofs);
        bytes32[] memory dataHashes = new bytes32[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            if (!proofOutputs[i].isValid) revert InvalidPreimageProof();
            dataHashes[i] = proofOutputs[i].dataHash;
        }

        tokenId = _nextTokenId++;
        _tokens[tokenId] = TokenData({
            owner: to,
            dataHashes: dataHashes,
            dataDescriptions: dataDescriptions,
            authorizedUsers: new address[](0),
            approvedUser: address(0)
        });

        emit Minted(tokenId, msg.sender, to, dataHashes, dataDescriptions);
    }

    function update(uint256 tokenId, bytes[] calldata proofs) public virtual {
        TokenData storage token = _tokens[tokenId];
        if (token.owner != msg.sender) revert NotOwner();

        PreimageProofOutput[] memory proofOutputs = verifier.verifyPreimage(proofs);
        bytes32[] memory newDataHashes = new bytes32[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            if (!proofOutputs[i].isValid) revert InvalidPreimageProof();
            newDataHashes[i] = proofOutputs[i].dataHash;
        }

        bytes32[] memory oldDataHashes = token.dataHashes;
        token.dataHashes = newDataHashes;

        emit Updated(tokenId, oldDataHashes, newDataHashes);
    }

    function transfer(address to, uint256 tokenId, bytes[] calldata proofs) public virtual {
        if (to == address(0)) revert ZeroAddress();
        if (_tokens[tokenId].owner != msg.sender) revert NotOwner();

        TransferValidityProofOutput[] memory proofOutputs = verifier.verifyTransferValidity(proofs);
        bytes16[] memory sealedKeys = new bytes16[](proofOutputs.length);
        bytes32[] memory newDataHashes = new bytes32[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            if (!proofOutputs[i].isValid) revert InvalidTransferValidityProof();
            if (proofOutputs[i].receiver != to) revert ReceiverMismatch();
            sealedKeys[i] = proofOutputs[i].sealedKey;
            newDataHashes[i] = proofOutputs[i].newDataHash;
        }

        _tokens[tokenId].owner = to;
        _tokens[tokenId].dataHashes = newDataHashes;

        emit Transferred(tokenId, msg.sender, to);
        emit PublishedSealedKey(to, tokenId, sealedKeys);
    }

    function transferFrom(address from, address to, uint256 tokenId, bytes[] calldata proofs)
        public
        virtual
    {
        if (to == address(0)) revert ZeroAddress();
        if (_tokens[tokenId].owner != from) revert NotOwner();
        if (!(
            _tokens[tokenId].approvedUser == msg.sender || _tokens[tokenId].owner == msg.sender
                || _operatorApprovals[from][msg.sender]
        )) revert NotApproved();

        TransferValidityProofOutput[] memory proofOutputs = verifier.verifyTransferValidity(proofs);
        bytes16[] memory sealedKeys = new bytes16[](proofOutputs.length);
        bytes32[] memory newDataHashes = new bytes32[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            if (!proofOutputs[i].isValid) revert InvalidTransferValidityProof();
            if (proofOutputs[i].receiver != to) revert ReceiverMismatch();
            sealedKeys[i] = proofOutputs[i].sealedKey;
            newDataHashes[i] = proofOutputs[i].newDataHash;
        }

        _tokens[tokenId].owner = to;
        _tokens[tokenId].dataHashes = newDataHashes;

        emit Transferred(tokenId, from, to);
        emit PublishedSealedKey(to, tokenId, sealedKeys);
    }

    function clone(address to, uint256 tokenId, bytes[] calldata proofs)
        public
        virtual
        returns (uint256)
    {
        if (to == address(0)) revert ZeroAddress();
        if (_tokens[tokenId].owner != msg.sender) revert NotOwner();

        TransferValidityProofOutput[] memory proofOutputs = verifier.verifyTransferValidity(proofs);
        bytes32[] memory newDataHashes = new bytes32[](proofOutputs.length);
        bytes16[] memory sealedKeys = new bytes16[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            if (!proofOutputs[i].isValid) revert InvalidTransferValidityProof();
            if (proofOutputs[i].receiver != to) revert ReceiverMismatch();
            sealedKeys[i] = proofOutputs[i].sealedKey;
            newDataHashes[i] = proofOutputs[i].newDataHash;
        }

        uint256 newTokenId = _nextTokenId++;
        _tokens[newTokenId] = TokenData({
            owner: to,
            dataHashes: newDataHashes,
            dataDescriptions: _tokens[tokenId].dataDescriptions,
            authorizedUsers: new address[](0),
            approvedUser: address(0)
        });

        emit Cloned(tokenId, newTokenId, msg.sender, to);
        emit PublishedSealedKey(to, newTokenId, sealedKeys);
        return newTokenId;
    }

    function cloneFrom(address from, address to, uint256 tokenId, bytes[] calldata proofs)
        public
        virtual
        returns (uint256)
    {
        if (to == address(0)) revert ZeroAddress();
        if (_tokens[tokenId].owner != from) revert NotOwner();
        if (!(
            _tokens[tokenId].approvedUser == msg.sender || _tokens[tokenId].owner == msg.sender
                || _operatorApprovals[from][msg.sender]
        )) revert NotApproved();

        TransferValidityProofOutput[] memory proofOutputs = verifier.verifyTransferValidity(proofs);
        bytes32[] memory newDataHashes = new bytes32[](proofOutputs.length);
        bytes16[] memory sealedKeys = new bytes16[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            if (!proofOutputs[i].isValid) revert InvalidTransferValidityProof();
            if (proofOutputs[i].receiver != to) revert ReceiverMismatch();
            sealedKeys[i] = proofOutputs[i].sealedKey;
            newDataHashes[i] = proofOutputs[i].newDataHash;
        }

        uint256 newTokenId = _nextTokenId++;
        _tokens[newTokenId] = TokenData({
            owner: to,
            dataHashes: newDataHashes,
            dataDescriptions: _tokens[tokenId].dataDescriptions,
            authorizedUsers: new address[](0),
            approvedUser: address(0)
        });

        emit Cloned(tokenId, newTokenId, msg.sender, to);
        emit PublishedSealedKey(to, newTokenId, sealedKeys);
        return newTokenId;
    }

    function authorizeUsage(uint256 tokenId, address user) public virtual {
        if (_tokens[tokenId].owner != msg.sender) revert NotOwner();
        _tokens[tokenId].authorizedUsers.push(user);
        emit Authorization(msg.sender, user, tokenId);
    }

    // ─ Approval functions ─

    function approve(address to, uint256 tokenId) public virtual {
        if (_tokens[tokenId].owner != msg.sender) revert NotOwner();
        _tokens[tokenId].approvedUser = to;
        emit Approval(msg.sender, to, tokenId);
    }

    function setApprovalForAll(address to, bool approved) public virtual {
        _operatorApprovals[msg.sender][to] = approved;
        emit ApprovalForAll(msg.sender, to, approved);
    }

    function getApproved(uint256 tokenId) public view virtual returns (address operator) {
        return _tokens[tokenId].approvedUser;
    }

    function isApprovedForAll(address owner, address operator)
        public
        view
        virtual
        returns (bool)
    {
        return _operatorApprovals[owner][operator];
    }

    // ─ Views ─

    function ownerOf(uint256 tokenId) public view virtual returns (address) {
        TokenData storage token = _tokens[tokenId];
        if (token.owner == address(0)) revert TokenNotExist();
        return token.owner;
    }

    function authorizedUsersOf(uint256 tokenId) public view virtual returns (address[] memory) {
        TokenData storage token = _tokens[tokenId];
        if (token.owner == address(0)) revert TokenNotExist();
        return token.authorizedUsers;
    }

    function dataHashesOf(uint256 tokenId) public view virtual returns (bytes32[] memory) {
        TokenData storage token = _tokens[tokenId];
        if (token.owner == address(0)) revert TokenNotExist();
        return token.dataHashes;
    }

    function dataDescriptionsOf(uint256 tokenId)
        public
        view
        virtual
        returns (string[] memory)
    {
        TokenData storage token = _tokens[tokenId];
        if (token.owner == address(0)) revert TokenNotExist();
        return token.dataDescriptions;
    }

    function tokenURI(uint256 tokenId) public view virtual returns (string memory) {
        if (!_exists(tokenId)) revert TokenNotExist();
        return string(
            abi.encodePacked('{"chainURL":"', chainURL, '","indexerURL":"', indexerURL, '"}')
        );
    }

    function _exists(uint256 tokenId) internal view returns (bool) {
        return _tokens[tokenId].owner != address(0);
    }

    string public constant VERSION = "1.0.0";
}
