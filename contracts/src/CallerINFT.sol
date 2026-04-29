// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/extensions/AccessControlEnumerable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";
import "./interfaces/IERC7857.sol";
import "./interfaces/IERC7857Metadata.sol";
import "./interfaces/IERC7857DataVerifier.sol";

/// @title CallerINFT
/// @notice ERC-7857 compliant agent NFT for Cymatic caller identity.
///         Each phone caller gets exactly one token with encrypted metadata
///         backed by cryptographic proofs and 0G Storage.
contract CallerINFT is AccessControlEnumerable, IERC7857, IERC7857Metadata {
    using Strings for uint256;

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
        require(verifierAddr != address(0), "Zero verifier address");
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
        require(newVerifier != address(0), "Zero address");
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
        require(dataDescriptions.length == proofs.length, "Length mismatch");
        if (to == address(0)) {
            to = msg.sender;
        }

        PreimageProofOutput[] memory proofOutputs = verifier.verifyPreimage(proofs);
        bytes32[] memory dataHashes = new bytes32[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            require(proofOutputs[i].isValid, "Invalid preimage proof");
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
        require(token.owner == msg.sender, "Not owner");

        PreimageProofOutput[] memory proofOutputs = verifier.verifyPreimage(proofs);
        bytes32[] memory newDataHashes = new bytes32[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            require(proofOutputs[i].isValid, "Invalid preimage proof");
            newDataHashes[i] = proofOutputs[i].dataHash;
        }

        bytes32[] memory oldDataHashes = token.dataHashes;
        token.dataHashes = newDataHashes;

        emit Updated(tokenId, oldDataHashes, newDataHashes);
    }

    function transfer(address to, uint256 tokenId, bytes[] calldata proofs) public virtual {
        require(to != address(0), "Zero address");
        require(_tokens[tokenId].owner == msg.sender, "Not owner");

        TransferValidityProofOutput[] memory proofOutputs = verifier.verifyTransferValidity(proofs);
        bytes16[] memory sealedKeys = new bytes16[](proofOutputs.length);
        bytes32[] memory newDataHashes = new bytes32[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            require(proofOutputs[i].isValid, "Invalid transfer validity proof");
            require(proofOutputs[i].receiver == to, "Receiver mismatch");
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
        require(to != address(0), "Zero address");
        require(_tokens[tokenId].owner == from, "Not owner");
        require(
            _tokens[tokenId].approvedUser == msg.sender || _tokens[tokenId].owner == msg.sender
                || _operatorApprovals[from][msg.sender],
            "Not approved"
        );

        TransferValidityProofOutput[] memory proofOutputs = verifier.verifyTransferValidity(proofs);
        bytes16[] memory sealedKeys = new bytes16[](proofOutputs.length);
        bytes32[] memory newDataHashes = new bytes32[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            require(proofOutputs[i].isValid, "Invalid transfer validity proof");
            require(proofOutputs[i].receiver == to, "Receiver mismatch");
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
        require(to != address(0), "Zero address");
        require(_tokens[tokenId].owner == msg.sender, "Not owner");

        TransferValidityProofOutput[] memory proofOutputs = verifier.verifyTransferValidity(proofs);
        bytes32[] memory newDataHashes = new bytes32[](proofOutputs.length);
        bytes16[] memory sealedKeys = new bytes16[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            require(proofOutputs[i].isValid, "Invalid transfer validity proof");
            require(proofOutputs[i].receiver == to, "Receiver mismatch");
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
        require(to != address(0), "Zero address");
        require(_tokens[tokenId].owner == from, "Not owner");
        require(
            _tokens[tokenId].approvedUser == msg.sender || _tokens[tokenId].owner == msg.sender
                || _operatorApprovals[from][msg.sender],
            "Not approved"
        );

        TransferValidityProofOutput[] memory proofOutputs = verifier.verifyTransferValidity(proofs);
        bytes32[] memory newDataHashes = new bytes32[](proofOutputs.length);
        bytes16[] memory sealedKeys = new bytes16[](proofOutputs.length);

        for (uint256 i = 0; i < proofOutputs.length; i++) {
            require(proofOutputs[i].isValid, "Invalid transfer validity proof");
            require(proofOutputs[i].receiver == to, "Receiver mismatch");
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
        require(_tokens[tokenId].owner == msg.sender, "Not owner");
        _tokens[tokenId].authorizedUsers.push(user);
        emit Authorization(msg.sender, user, tokenId);
    }

    // ─ Approval functions ─

    function approve(address to, uint256 tokenId) public virtual {
        require(_tokens[tokenId].owner == msg.sender, "Not owner");
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
        require(token.owner != address(0), "Token not exist");
        return token.owner;
    }

    function authorizedUsersOf(uint256 tokenId) public view virtual returns (address[] memory) {
        TokenData storage token = _tokens[tokenId];
        require(token.owner != address(0), "Token not exist");
        return token.authorizedUsers;
    }

    function dataHashesOf(uint256 tokenId) public view virtual returns (bytes32[] memory) {
        TokenData storage token = _tokens[tokenId];
        require(token.owner != address(0), "Token not exist");
        return token.dataHashes;
    }

    function dataDescriptionsOf(uint256 tokenId)
        public
        view
        virtual
        returns (string[] memory)
    {
        TokenData storage token = _tokens[tokenId];
        require(token.owner != address(0), "Token not exist");
        return token.dataDescriptions;
    }

    function tokenURI(uint256 tokenId) public view virtual returns (string memory) {
        require(_exists(tokenId), "Token not exist");
        return string(
            abi.encodePacked('{"chainURL":"', chainURL, '","indexerURL":"', indexerURL, '"}')
        );
    }

    function _exists(uint256 tokenId) internal view returns (bool) {
        return _tokens[tokenId].owner != address(0);
    }

    string public constant VERSION = "1.0.0";
}
