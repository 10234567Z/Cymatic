// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {Script, console} from "forge-std/Script.sol";
import {MockOracle} from "../src/MockOracle.sol";
import {CallerINFT} from "../src/CallerINFT.sol";

/// @notice Deploy MockOracle + CallerINFT to 0G Galileo testnet.
///
/// Usage:
///   forge script script/DeployCallerINFT.s.sol:DeployCallerINFT \
///     --rpc-url og_testnet \
///     --broadcast \
///     --private-key $DEPLOYER_PRIVATE_KEY
///
/// The deployer wallet becomes the contract owner (platform key).
/// Save the printed addresses to backend/.env:
///   CALLER_INFT_ADDRESS=<CallerINFT>
///   MOCK_ORACLE_ADDRESS=<MockOracle>
contract DeployCallerINFT is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        vm.startBroadcast(deployerKey);

        MockOracle oracle = new MockOracle();
        console.log("MockOracle deployed:", address(oracle));

        CallerINFT inft = new CallerINFT(address(oracle));
        console.log("CallerINFT deployed:", address(inft));

        vm.stopBroadcast();
    }
}
