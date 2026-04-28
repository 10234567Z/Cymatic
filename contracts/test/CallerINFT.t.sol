// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {Test} from "forge-std/Test.sol";
import {CallerINFT} from "../src/CallerINFT.sol";
import {MockOracle} from "../src/MockOracle.sol";

contract CallerINFTTest is Test {
    CallerINFT public inft;
    MockOracle public oracle;

    address owner = address(this);
    address alice = makeAddr("alice");
    address bob = makeAddr("bob");
    address agent = makeAddr("agent");

    string constant CALLER_ID = "+14155552671";
    string constant CALLER_ID_2 = "+14155559999";
    string constant ENCRYPTED_URI = "0g://testnet/encrypted-profile-abc123";
    bytes32 constant METADATA_HASH = keccak256("initial-profile-data");

    function setUp() public {
        oracle = new MockOracle();
        inft = new CallerINFT(address(oracle));
    }

    // ── registerCaller ───────────────────────────────────────────────────────

    function test_RegisterCaller_MintsToken() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        assertEq(tokenId, 1);
        assertEq(inft.ownerOf(1), alice);
    }

    function test_RegisterCaller_SetsMetadata() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        assertEq(inft.getEncryptedURI(tokenId), ENCRYPTED_URI);
        assertEq(inft.getMetadataHash(tokenId), METADATA_HASH);
    }

    function test_RegisterCaller_TracksCallerId() public {
        inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        assertTrue(inft.isRegistered(CALLER_ID));
        assertEq(inft.getTokenId(CALLER_ID), 1);
    }

    function test_RegisterCaller_EmitsCallerRegistered() public {
        vm.expectEmit(false, true, false, true);
        emit CallerINFT.CallerRegistered(CALLER_ID, alice, 1);
        inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
    }

    function test_RegisterCaller_Reverts_DuplicateCaller() public {
        inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        vm.expectRevert("CallerINFT: caller already registered");
        inft.registerCaller(bob, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
    }

    function test_RegisterCaller_Reverts_ZeroAddress() public {
        vm.expectRevert("CallerINFT: zero address");
        inft.registerCaller(address(0), CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
    }

    function test_RegisterCaller_Reverts_NotOwner() public {
        vm.prank(alice);
        vm.expectRevert();
        inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
    }

    function test_RegisterCaller_MultipleCallers_IncrementTokenIds() public {
        uint256 id1 = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        uint256 id2 = inft.registerCaller(bob, CALLER_ID_2, ENCRYPTED_URI, METADATA_HASH);
        assertEq(id1, 1);
        assertEq(id2, 2);
    }

    // ── updateMetadata ───────────────────────────────────────────────────────

    function test_UpdateMetadata_ByTokenOwner() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        bytes32 newHash = keccak256("updated-profile");
        string memory newURI = "0g://testnet/updated-abc456";

        vm.prank(alice);
        inft.updateMetadata(tokenId, newURI, newHash);

        assertEq(inft.getEncryptedURI(tokenId), newURI);
        assertEq(inft.getMetadataHash(tokenId), newHash);
    }

    function test_UpdateMetadata_ByPlatformOwner() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        bytes32 newHash = keccak256("platform-updated");
        inft.updateMetadata(tokenId, "0g://testnet/platform-update", newHash);
        assertEq(inft.getMetadataHash(tokenId), newHash);
    }

    function test_UpdateMetadata_EmitsEvent() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        bytes32 newHash = keccak256("updated");
        vm.expectEmit(true, false, false, true);
        emit CallerINFT.MetadataUpdated(tokenId, newHash);
        inft.updateMetadata(tokenId, ENCRYPTED_URI, newHash);
    }

    function test_UpdateMetadata_Reverts_Unauthorized() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        vm.prank(bob);
        vm.expectRevert("CallerINFT: not authorized");
        inft.updateMetadata(tokenId, ENCRYPTED_URI, METADATA_HASH);
    }

    // ── secureTransfer ───────────────────────────────────────────────────────

    function test_SecureTransfer_ChangesOwner() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        bytes memory sealedKey = abi.encodePacked(keccak256("sealed-for-bob"));
        bytes memory proof = bytes("valid-proof");

        vm.prank(alice);
        inft.approve(address(this), tokenId);
        inft.secureTransfer(alice, bob, tokenId, sealedKey, proof);

        assertEq(inft.ownerOf(tokenId), bob);
    }

    function test_SecureTransfer_UpdatesMetadataHash() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        bytes memory sealedKey = abi.encodePacked(keccak256("new-sealed-key"));
        bytes memory proof = bytes("valid-proof");

        vm.prank(alice);
        inft.approve(address(this), tokenId);
        inft.secureTransfer(alice, bob, tokenId, sealedKey, proof);

        assertEq(inft.getMetadataHash(tokenId), keccak256(sealedKey));
    }

    function test_SecureTransfer_Reverts_NotOwner() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        bytes memory sealedKey = bytes("key");
        bytes memory proof = bytes("proof");

        vm.expectRevert("CallerINFT: not owner");
        inft.secureTransfer(bob, alice, tokenId, sealedKey, proof);
    }

    // ── authorizeUsage ───────────────────────────────────────────────────────

    function test_AuthorizeUsage_GrantsPermissions() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        bytes memory perms = abi.encode("read", "inference");

        vm.prank(alice);
        inft.authorizeUsage(tokenId, agent, perms);

        assertTrue(inft.isAuthorized(tokenId, agent));
        assertEq(inft.getPermissions(tokenId, agent), perms);
    }

    function test_AuthorizeUsage_EmitsEvent() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        vm.prank(alice);
        vm.expectEmit(true, true, false, false);
        emit CallerINFT.UsageAuthorized(tokenId, agent);
        inft.authorizeUsage(tokenId, agent, bytes("perms"));
    }

    function test_AuthorizeUsage_Reverts_NotOwner() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        vm.prank(bob);
        vm.expectRevert("CallerINFT: not owner");
        inft.authorizeUsage(tokenId, agent, bytes("perms"));
    }

    function test_IsAuthorized_ReturnsFalse_WhenNotGranted() public {
        uint256 tokenId = inft.registerCaller(alice, CALLER_ID, ENCRYPTED_URI, METADATA_HASH);
        assertFalse(inft.isAuthorized(tokenId, agent));
    }

    // ── oracle update ────────────────────────────────────────────────────────

    function test_SetOracle_UpdatesOracle() public {
        address newOracle = makeAddr("newOracle");
        inft.setOracle(newOracle);
        assertEq(inft.oracle(), newOracle);
    }

    function test_SetOracle_EmitsEvent() public {
        address newOracle = makeAddr("newOracle");
        vm.expectEmit(false, false, false, true);
        emit CallerINFT.OracleUpdated(address(oracle), newOracle);
        inft.setOracle(newOracle);
    }

    function test_SetOracle_Reverts_NotOwner() public {
        vm.prank(alice);
        vm.expectRevert();
        inft.setOracle(makeAddr("x"));
    }

    // ── view helpers ─────────────────────────────────────────────────────────

    function test_GetTokenId_Reverts_NotRegistered() public {
        vm.expectRevert("CallerINFT: caller not registered");
        inft.getTokenId("+10000000000");
    }

    function test_IsRegistered_ReturnsFalse_BeforeRegistration() public view {
        assertFalse(inft.isRegistered(CALLER_ID));
    }
}
