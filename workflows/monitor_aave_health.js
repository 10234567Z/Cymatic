async function actionStep(input) {
  "use step";
  
  const { chainId, walletAddress, healthThreshold } = input;
  
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
  const threshold = healthThreshold || 1.5;
  
  if (!poolAddress || !rpcUrl) {
    return { 
      error: `Unsupported chain: ${chainId}`, 
      monitoring: false,
      healthFactor: null
    };
  }
  
  try {
    // Get current health factor
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
        monitoring: false,
        healthFactor: null
      };
    }
    
    const result = data.result;
    const healthFactorRaw = BigInt("0x" + result.slice(258, 322));
    const healthFactorDecimal = Number(healthFactorRaw) / 1e18;
    
    const isAtRisk = healthFactorDecimal < threshold;
    
    return {
      monitoring: true,
      healthFactor: parseFloat(healthFactorDecimal.toFixed(2)),
      threshold: threshold,
      isAtRisk: isAtRisk,
      alertNeeded: isAtRisk,
      message: isAtRisk 
        ? `⚠️ Health factor ${healthFactorDecimal.toFixed(2)} below threshold ${threshold}` 
        : `✅ Health factor ${healthFactorDecimal.toFixed(2)} is healthy`
    };
    
  } catch (error) {
    return { 
      error: error.message, 
      monitoring: false,
      healthFactor: null
    };
  }
}
