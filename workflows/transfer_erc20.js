async function actionStep(input) {
  "use step";
  
  const { chainId, toAddress, tokenAddress, amount, walletId } = input;
  
  // Use Turnkey MPC wallet integration to sign and send transaction
  // This is a stub - actual signing happens via KeeperHub's Turnkey plugin
  
  try {
    // Build ERC20 transfer call
    // transfer(address to, uint256 amount)
    // Selector: 0xa9059cbb
    const selector = "0xa9059cbb";
    const paddedTo = toAddress.slice(2).padStart(64, "0");
    const paddedAmount = BigInt(amount).toString(16).padStart(64, "0");
    const callData = selector + paddedTo + paddedAmount;
    
    return {
      txHash: null,
      status: "pending",
      message: "Transfer initiated - use Turnkey wallet integration to sign",
      callData: callData,
      to: tokenAddress,
      value: "0"
    };
    
  } catch (error) {
    return { 
      error: error.message, 
      txHash: null,
      status: "error"
    };
  }
}
