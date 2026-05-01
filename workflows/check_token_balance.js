async function actionStep(input) {
  "use step";
  
  const { chainId, address, tokenAddress } = input;
  
  const rpcUrls = {
    1: "https://cloudflare-eth.com",
    8453: "https://mainnet.base.org",
    84532: "https://sepolia.base.org",
    42161: "https://arb1.arbitrum.io/rpc",
    137: "https://polygon-rpc.com",
  };
  
  const rpcUrl = rpcUrls[chainId];
  if (!rpcUrl) {
    return { error: `Unsupported chain: ${chainId}`, balance: null, symbol: null, decimals: null };
  }
  
  try {
    // ERC20 balanceOf(address) call
    // Selector: 0x70a08231
    const selector = "0x70a08231";
    const paddedAddress = address.slice(2).padStart(64, "0");
    const callData = selector + paddedAddress;
    
    const response = await fetch(rpcUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "eth_call",
        params: [{
          to: tokenAddress,
          data: callData
        }, "latest"]
      })
    });
    
    const result = await response.json();
    if (result.error) {
      return { error: result.error.message, balance: null, symbol: null, decimals: null };
    }
    
    const balanceRaw = BigInt(result.result);
    
    // Get token decimals
    const decimalsSelector = "0x313ce567";
    const decimalsResponse = await fetch(rpcUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 2,
        method: "eth_call",
        params: [{
          to: tokenAddress,
          data: decimalsSelector
        }, "latest"]
      })
    });
    
    const decimalsResult = await decimalsResponse.json();
    const decimals = parseInt(decimalsResult.result, 16);
    
    // Get token symbol
    const symbolSelector = "0x95d89b41";
    const symbolResponse = await fetch(rpcUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 3,
        method: "eth_call",
        params: [{
          to: tokenAddress,
          data: symbolSelector
        }, "latest"]
      })
    });
    
    const symbolResult = await symbolResponse.json();
    // Decode symbol from bytes32
    const symbolHex = symbolResult.result;
    const symbolString = Buffer.from(symbolHex.slice(2), "hex")
      .toString("utf8")
      .replace(/\0/g, "")
      .trim();
    
    const divisor = BigInt(10) ** BigInt(decimals);
    const formattedBalance = (Number(balanceRaw) / Number(divisor)).toFixed(decimals);
    
    return {
      balance: {
        balanceRaw: balanceRaw.toString(),
        balance: formattedBalance,
        decimals: decimals,
        symbol: symbolString
      }
    };
  } catch (error) {
    return { error: error.message, balance: null, symbol: null, decimals: null };
  }
}
