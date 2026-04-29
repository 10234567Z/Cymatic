// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {CallerINFT} from "../src/CallerINFT.sol";
import {MockVerifier} from "../src/MockVerifier.sol";

contract CallerINFTTest is Test {
    CallerINFT public inft;
    MockVerifier public verifier;

    address admin = address(this);
    address alice = makeAddr("alice");
    address bob = makeAddr("bob");
    address charlie = makeAddr("charlie");

    function setUp() public {
        verifier = new MockVerifier();
        inft = new CallerINFT("Cymatic Caller Identity", "CAID", address(verifier), "https://0g.ai", "https://indexer.0g.ai");
    }

    // ── mint ──────────────────────────────────────────────────────────────────

    function test_Mint_CreatesToken() public {
        bytes[] memory proofs = new bytes[](2);
        proofs[0] = abi.encodePacked("proof1");
        proofs[1] = abi.encodePacked("proof2");

        string[] memory descriptions = new string[](2);
        descriptions[0] = "profile";
        descriptions[1] = "history";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);
        assertEq(tokenId, 1);
        assertEq(inft.ownerOf(tokenId), alice);
    }

    function test_Mint_StoresDataHashes() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("data-proof");

        string[] memory descriptions = new string[](1);
        descriptions[0] = "caller-data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);
        bytes32[] memory hashes = inft.dataHashesOf(tokenId);
        assertEq(hashes.length, 1);
        assertEq(hashes[0], keccak256(abi.encodePacked("data-proof")));
    }

    function test_Mint_StoresDescriptions() public {
        bytes[] memory proofs = new bytes[](2);
        proofs[0] = abi.encodePacked("proof1");
        proofs[1] = abi.encodePacked("proof2");

        string[] memory descriptions = new string[](2);
        descriptions[0] = "profile";
        descriptions[1] = "metadata";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);
        string[] memory stored = inft.dataDescriptionsOf(tokenId);
        assertEq(stored.length, 2);
        assertEq(stored[0], "profile");
        assertEq(stored[1], "metadata");
    }

    function test_Mint_DefaultsMinterIfNoRecipient() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");

        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        vm.prank(alice);
        uint256 tokenId = inft.mint(proofs, descriptions, address(0));
        assertEq(inft.ownerOf(tokenId), alice);
    }

    function test_Mint_Reverts_LengthMismatch() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");

        string[] memory descriptions = new string[](2);
        descriptions[0] = "d1";
        descriptions[1] = "d2";

        vm.expectRevert(CallerINFT.LengthMismatch.selector);
        inft.mint(proofs, descriptions, alice);
    }

    // ── update ────────────────────────────────────────────────────────────────

    function test_Update_ChangesDataHashes() public {
        // Mint initial token
        bytes[] memory initProofs = new bytes[](1);
        initProofs[0] = abi.encodePacked("initial");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";
        uint256 tokenId = inft.mint(initProofs, descriptions, alice);

        // Update with new proofs
        bytes[] memory newProofs = new bytes[](1);
        newProofs[0] = abi.encodePacked("updated");

        vm.prank(alice);
        inft.update(tokenId, newProofs);

        bytes32[] memory hashes = inft.dataHashesOf(tokenId);
        assertEq(hashes[0], keccak256(abi.encodePacked("updated")));
    }

    function test_Update_Reverts_NotOwner() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        vm.prank(bob);
        vm.expectRevert(CallerINFT.NotOwner.selector);
        inft.update(tokenId, proofs);
    }

    // ── transfer ──────────────────────────────────────────────────────────────

    function test_Transfer_ChangesOwner() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        bytes[] memory transferProofs = new bytes[](1);
        transferProofs[0] = abi.encodePacked(bob);

        vm.prank(alice);
        inft.transfer(bob, tokenId, transferProofs);
        assertEq(inft.ownerOf(tokenId), bob);
    }

    function test_Transfer_Reverts_NotOwner() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        bytes[] memory transferProofs = new bytes[](1);
        transferProofs[0] = abi.encodePacked("transfer-proof");

        vm.prank(bob);
        vm.expectRevert(CallerINFT.NotOwner.selector);
        inft.transfer(bob, tokenId, transferProofs);
    }

    // ── transferFrom ──────────────────────────────────────────────────────────

    function test_TransferFrom_WithApproval() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        // Approve bob
        vm.prank(alice);
        inft.approve(bob, tokenId);

        bytes[] memory transferProofs = new bytes[](1);
        transferProofs[0] = abi.encodePacked(charlie);

        vm.prank(bob);
        inft.transferFrom(alice, charlie, tokenId, transferProofs);
        assertEq(inft.ownerOf(tokenId), charlie);
    }

    function test_TransferFrom_WithOperatorApproval() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        // Approve all
        vm.prank(alice);
        inft.setApprovalForAll(bob, true);

        bytes[] memory transferProofs = new bytes[](1);
        transferProofs[0] = abi.encodePacked(charlie);

        vm.prank(bob);
        inft.transferFrom(alice, charlie, tokenId, transferProofs);
        assertEq(inft.ownerOf(tokenId), charlie);
    }

    function test_TransferFrom_Reverts_NotApproved() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        bytes[] memory transferProofs = new bytes[](1);
        transferProofs[0] = abi.encodePacked("transfer-proof");

        vm.prank(bob);
        vm.expectRevert(CallerINFT.NotApproved.selector);
        inft.transferFrom(alice, charlie, tokenId, transferProofs);
    }

    // ── clone ─────────────────────────────────────────────────────────────────

    function test_Clone_CreatesNewToken() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        bytes[] memory cloneProofs = new bytes[](1);
        cloneProofs[0] = abi.encodePacked(bob);

        vm.prank(alice);
        uint256 newTokenId = inft.clone(bob, tokenId, cloneProofs);

        assertEq(newTokenId, 2);
        assertEq(inft.ownerOf(newTokenId), bob);
    }

    function test_Clone_CopiesDescriptions() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "original-data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        bytes[] memory cloneProofs = new bytes[](1);
        cloneProofs[0] = abi.encodePacked(bob);

        vm.prank(alice);
        uint256 newTokenId = inft.clone(bob, tokenId, cloneProofs);

        string[] memory newDescriptions = inft.dataDescriptionsOf(newTokenId);
        assertEq(newDescriptions[0], "original-data");
    }

    // ── authorize usage ───────────────────────────────────────────────────────

    function test_AuthorizeUsage_GrantsAccess() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        vm.prank(alice);
        inft.authorizeUsage(tokenId, charlie);

        address[] memory authorized = inft.authorizedUsersOf(tokenId);
        assertEq(authorized.length, 1);
        assertEq(authorized[0], charlie);
    }

    function test_AuthorizeUsage_Reverts_NotOwner() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        vm.prank(bob);
        vm.expectRevert(CallerINFT.NotOwner.selector);
        inft.authorizeUsage(tokenId, charlie);
    }

    // ── approval functions ────────────────────────────────────────────────────

    function test_Approve_SetsApproved() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);

        vm.prank(alice);
        inft.approve(bob, tokenId);

        assertEq(inft.getApproved(tokenId), bob);
    }

    function test_SetApprovalForAll_GrantsAllTokens() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        inft.mint(proofs, descriptions, alice);

        vm.prank(alice);
        inft.setApprovalForAll(bob, true);

        assertTrue(inft.isApprovedForAll(alice, bob));
    }

    function test_SetApprovalForAll_CanRevoke() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        inft.mint(proofs, descriptions, alice);

        vm.startPrank(alice);
        inft.setApprovalForAll(bob, true);
        assertTrue(inft.isApprovedForAll(alice, bob));
        inft.setApprovalForAll(bob, false);
        vm.stopPrank();

        assertFalse(inft.isApprovedForAll(alice, bob));
    }

    // ── admin functions ───────────────────────────────────────────────────────

    function test_UpdateURLs_ByAdmin() public {
        inft.updateURLs("https://new-chain.0g.ai", "https://new-indexer.0g.ai");
        // Verify by checking tokenURI output
    }

    function test_UpdateVerifier_ByAdmin() public {
        MockVerifier newVerifier = new MockVerifier();
        inft.updateVerifier(address(newVerifier));
        assertEq(address(inft.verifier()), address(newVerifier));
    }

    // ── edge cases ────────────────────────────────────────────────────────────

    function test_OwnerOf_Reverts_TokenNotExist() public {
        vm.expectRevert(CallerINFT.TokenNotExist.selector);
        inft.ownerOf(999);
    }

    function test_DataHashesOf_Reverts_TokenNotExist() public {
        vm.expectRevert(CallerINFT.TokenNotExist.selector);
        inft.dataHashesOf(999);
    }

    function test_TokenURI_Returns() public {
        bytes[] memory proofs = new bytes[](1);
        proofs[0] = abi.encodePacked("proof");
        string[] memory descriptions = new string[](1);
        descriptions[0] = "data";

        uint256 tokenId = inft.mint(proofs, descriptions, alice);
        string memory uri = inft.tokenURI(tokenId);
        assertTrue(bytes(uri).length > 0);
    }
}
