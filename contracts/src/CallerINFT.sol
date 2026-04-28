// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @notice Minimal oracle interface for ERC-7857 proof verification.
interface IOracle {
    function verifyProof(bytes calldata proof) external view returns (bool);
}

/// @title CallerINFT
/// @notice ERC-7857-aligned INFT for caller identity on the Cymatic platform.
///         Each phone caller gets exactly one token. The encrypted URI points to
///         caller profile metadata (preferences, history) stored on 0G Storage.
///         Metadata hash commits to the current encrypted payload.
contract CallerINFT is ERC721, Ownable, ReentrancyGuard {
    // ── State ────────────────────────────────────────────────────────────────

    /// @dev Encrypted 0G Storage URI per token.
    mapping(uint256 => string) private _encryptedURIs;

    /// @dev Committed hash of the encrypted metadata per token.
    mapping(uint256 => bytes32) private _metadataHashes;

    /// @dev Authorizations: tokenId → executor → permissions blob.
    mapping(uint256 => mapping(address => bytes)) private _authorizations;

    /// @dev Caller identifier (e.g. E.164 phone number) → tokenId.
    mapping(string => uint256) private _callerTokenIds;

    /// @dev Whether a given caller has a token.
    mapping(string => bool) private _callerRegistered;

    /// @dev Oracle that verifies re-encryption proofs on transfers.
    address public oracle;

    uint256 private _nextTokenId = 1;

    // ── Events ───────────────────────────────────────────────────────────────

    event CallerRegistered(string indexed callerId, address indexed to, uint256 tokenId);
    event MetadataUpdated(uint256 indexed tokenId, bytes32 newHash);
    event UsageAuthorized(uint256 indexed tokenId, address indexed executor);
    event OracleUpdated(address oldOracle, address newOracle);

    // ── Constructor ──────────────────────────────────────────────────────────

    constructor(address _oracle) ERC721("Cymatic Caller Identity", "CAID") Ownable(msg.sender) {
        oracle = _oracle;
    }

    // ── Admin ────────────────────────────────────────────────────────────────

    function setOracle(address newOracle) external onlyOwner {
        emit OracleUpdated(oracle, newOracle);
        oracle = newOracle;
    }

    // ── Minting ──────────────────────────────────────────────────────────────

    /// @notice Register a new caller and mint their identity INFT.
    ///         Only the platform owner (backend deployer key) can call this.
    /// @param to           Wallet to receive the token (can be the platform wallet initially).
    /// @param callerId     Unique caller identifier, e.g. "+14155552671".
    /// @param encryptedURI 0G Storage URI of the AES-256-GCM encrypted profile.
    /// @param metadataHash keccak256 of the encrypted payload for on-chain commitment.
    function registerCaller(
        address to,
        string calldata callerId,
        string calldata encryptedURI,
        bytes32 metadataHash
    ) external onlyOwner returns (uint256 tokenId) {
        require(!_callerRegistered[callerId], "CallerINFT: caller already registered");
        require(to != address(0), "CallerINFT: zero address");

        tokenId = _nextTokenId++;
        _safeMint(to, tokenId);
        _encryptedURIs[tokenId] = encryptedURI;
        _metadataHashes[tokenId] = metadataHash;
        _callerTokenIds[callerId] = tokenId;
        _callerRegistered[callerId] = true;

        emit CallerRegistered(callerId, to, tokenId);
    }

    // ── Metadata update ──────────────────────────────────────────────────────

    /// @notice Update caller profile after a call (new encrypted URI + hash).
    ///         Only the token owner or platform owner can update.
    function updateMetadata(
        uint256 tokenId,
        string calldata newEncryptedURI,
        bytes32 newMetadataHash
    ) external {
        require(
            ownerOf(tokenId) == msg.sender || owner() == msg.sender,
            "CallerINFT: not authorized"
        );
        _encryptedURIs[tokenId] = newEncryptedURI;
        _metadataHashes[tokenId] = newMetadataHash;
        emit MetadataUpdated(tokenId, newMetadataHash);
    }

    // ── ERC-7857 transfer with re-encryption ────────────────────────────────

    /// @notice Transfer token to a new owner with oracle-verified re-encrypted metadata.
    /// @param from      Current owner.
    /// @param to        New owner.
    /// @param tokenId   Token to transfer.
    /// @param sealedKey New encryption key sealed for the recipient's public key.
    /// @param proof     Oracle proof attesting the re-encryption was correct.
    function secureTransfer(
        address from,
        address to,
        uint256 tokenId,
        bytes calldata sealedKey,
        bytes calldata proof
    ) external nonReentrant {
        require(ownerOf(tokenId) == from, "CallerINFT: not owner");
        require(to != address(0), "CallerINFT: zero address");
        require(IOracle(oracle).verifyProof(proof), "CallerINFT: invalid oracle proof");

        // Commit new metadata hash derived from the sealed key.
        bytes32 newHash = keccak256(sealedKey);
        _metadataHashes[tokenId] = newHash;

        // If proof carries a new encrypted URI (length > 32), extract it.
        if (proof.length > 32) {
            _encryptedURIs[tokenId] = string(proof[32:]);
        }

        _transfer(from, to, tokenId);
        emit MetadataUpdated(tokenId, newHash);
    }

    // ── Authorized usage (AIaaS / agent delegation) ──────────────────────────

    /// @notice Grant an executor (e.g. the platform agent) permission to use this INFT.
    /// @param tokenId     The caller's token.
    /// @param executor    Address to authorise (e.g. platform agent contract or wallet).
    /// @param permissions ABI-encoded permissions blob (checked off-chain by the executor).
    function authorizeUsage(
        uint256 tokenId,
        address executor,
        bytes calldata permissions
    ) external {
        require(ownerOf(tokenId) == msg.sender, "CallerINFT: not owner");
        _authorizations[tokenId][executor] = permissions;
        emit UsageAuthorized(tokenId, executor);
    }

    /// @notice Check whether an executor is authorised for a token.
    function isAuthorized(uint256 tokenId, address executor) external view returns (bool) {
        return _authorizations[tokenId][executor].length > 0;
    }

    // ── Views ────────────────────────────────────────────────────────────────

    function getTokenId(string calldata callerId) external view returns (uint256) {
        require(_callerRegistered[callerId], "CallerINFT: caller not registered");
        return _callerTokenIds[callerId];
    }

    function isRegistered(string calldata callerId) external view returns (bool) {
        return _callerRegistered[callerId];
    }

    function getEncryptedURI(uint256 tokenId) external view returns (string memory) {
        return _encryptedURIs[tokenId];
    }

    function getMetadataHash(uint256 tokenId) external view returns (bytes32) {
        return _metadataHashes[tokenId];
    }

    function getPermissions(uint256 tokenId, address executor) external view returns (bytes memory) {
        return _authorizations[tokenId][executor];
    }
}
