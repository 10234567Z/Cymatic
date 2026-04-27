async function actionStep(input) {
  "use step";
  
  const { chainId, walletAddress } = input;
  
  const poolAddresses = {
    1: "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",    // Ethereum
    42161: "0x794a61358D6845594F94dc1DB02A252b5b4814aD"  // Arbitrum
  };
  
  const rpcUrls = {
    1: "https://eth.rpc.com",
    42161: "https://arb-rpc.arbitrum.io/public"
  };
  
  const poolAddress = poolAddresses[chainId];
  const rpcUrl = rpcUrls[chainId];
  
  if (!poolAddress || !rpcUrl) {
    return { 
      error: `Unsupported chain: ${chainId}`, 
      healthFactor: null, 
      suppliedValueUsd: null, 
      borrowedValueUsd: null 
    };
  }
  
  try {
    // Aave V3 IPool.getUserAccountData(address user)
    // Selector: 0xbf92857c
    const selector = "0xbf92857c";
    const paddedAddress = walletAddress.slice(2).padStart(64, "0");
    const callData = selector + paddedAddress;
    
    const response = await fetch(rpcUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "eth_call",
        params: [{
          to: poolAddress,
          data: callData
        }, "latest"]
      })
    });
    
    const data = await response.json();
    
    if (data.error) {
      return { 
        error: data.error.message, 
        healthFactor: null, 
        suppliedValueUsd: null, 
        borrowedValueUsd: null 
      };
    }
    
    const result = data.result;
    
    // Decode getUserAccountData return values
    // Returns: (totalCollateralBase, totalDebtBase, availableBorrowsBase, currentLiquidationThreshold, ltv, healthFactor)
    // Each is uint256 = 32 bytes
    const totalCollateralBase = BigInt("0x" + result.slice(2, 66));
    const totalDebtBase = BigInt("0x" + result.slice(66, 130));
    const healthFactorRaw = BigInt("0x" + result.slice(258, 322)); // 6th value at offset 258
    
    // Convert to decimal (Aave uses 18 decimals for base values)
    const healthFactorDecimal = Number(healthFactorRaw) / 1e18;
    const suppliedDecimal = Number(totalCollateralBase) / 1e8;
    const borrowedDecimal = Number(totalDebtBase) / 1e8;
    
    return {
      healthFactor: parseFloat(healthFactorDecimal.toFixed(2)),
      suppliedValueUsd: parseFloat(suppliedDecimal.toFixed(2)),
      borrowedValueUsd: parseFloat(borrowedDecimal.toFixed(2)),
      liquidationRisk: healthFactorDecimal < 1.5 ? "HIGH" : healthFactorDecimal < 2.0 ? "MEDIUM" : "LOW"
    };
    
  } catch (error) {
    return { 
      error: error.message, 
      healthFactor: null, 
      suppliedValueUsd: null, 
      borrowedValueUsd: null 
    };
  }
}
