// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {MockVerifier} from "../src/MockVerifier.sol";
import {CallerINFT} from "../src/CallerINFT.sol";

/// @notice Deploy MockVerifier + CallerINFT to 0G Galileo testnet.
///
/// Usage:
///   forge script script/DeployCallerINFT.s.sol:DeployCallerINFT \
///     --rpc-url og_testnet \
///     --broadcast \
///     --private-key $DEPLOYER_PRIVATE_KEY
///
/// The deployer wallet becomes the contract admin.
/// Save the printed addresses to backend/.env:
///   CALLER_INFT_ADDRESS=<CallerINFT>
contract DeployCallerINFT is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        vm.startBroadcast(deployerKey);

        // Deploy verifier
        MockVerifier verifier = new MockVerifier();
        console.log("MockVerifier deployed:", address(verifier));

        // Deploy CallerINFT with constructor initialization
        CallerINFT inft = new CallerINFT(
            "Cymatic Caller Identity",
            "CAID",
            address(verifier),
            "https://0g.ai",
            "https://indexer.0g.ai"
        );
        console.log("CallerINFT deployed:", address(inft));

        vm.stopBroadcast();
    }
}
