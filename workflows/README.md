# KeeperHub Workflow Code Files

These are the custom JavaScript action code for each workflow. Copy and paste them into the KeeperHub UI to create workflows.

## Setup Instructions

1. Go to [KeeperHub](https://app.keeperhub.com)
2. Create 4 new workflows (one for each file below)
3. For each workflow:
   - Add a **Trigger** node (manual or webhook)
   - Add an **Action** node with type: `custom/js`
   - Copy the entire code from the corresponding `.js` file below
   - Paste it into the action node's code editor
   - Connect trigger → action with an edge
   - Deploy

## Workflows

### 1. check_token_balance.js
**Purpose:** Check ERC20 token balance at an address

**Inputs:**
```json
{
  "chainId": 8453,
  "address": "0x...",
  "tokenAddress": "0x..."
}
```

**Output:**
```json
{
  "balance": {
    "balanceRaw": "1000000000",
    "balance": "1000.000000",
    "decimals": 6,
    "symbol": "USDC"
  }
}
```

**Supported Chains:**
- 1 (Ethereum)
- 8453 (Base)
- 42161 (Arbitrum)
- 137 (Polygon)

---

### 2. check_aave_health.js
**Purpose:** Check Aave protocol health factor for a wallet

**Inputs:**
```json
{
  "chainId": 1,
  "walletAddress": "0x..."
}
```

**Output:**
```json
{
  "healthFactor": 2.5,
  "suppliedValueUsd": 10000.0,
  "borrowedValueUsd": 4000.0,
  "liquidationRisk": "LOW"
}
```

**Supported Chains:**
- 1 (Ethereum)
- 42161 (Arbitrum)

---

### 3. monitor_aave_health.js
**Purpose:** Monitor Aave health factor with alerts when below threshold

**Inputs:**
```json
{
  "chainId": 1,
  "walletAddress": "0x...",
  "healthThreshold": 1.5
}
```

**Output:**
```json
{
  "monitoring": true,
  "healthFactor": 1.8,
  "threshold": 1.5,
  "isAtRisk": false,
  "alertNeeded": false,
  "message": "✅ Health factor 1.80 is healthy"
}
```

---

### 4. transfer_erc20.js
**Purpose:** Transfer ERC20 tokens using Turnkey MPC wallet

**Inputs:**
```json
{
  "chainId": 8453,
  "toAddress": "0x...",
  "tokenAddress": "0x...",
  "amount": "1000000",
  "walletId": "..."
}
```

**Output:**
```json
{
  "txHash": "0x...",
  "status": "pending",
  "callData": "0xa9059cbb...",
  "to": "0x...",
  "value": "0"
}
```

**Note:** Requires Turnkey MPC integration in KeeperHub

---

## Testing

Once deployed, test each workflow:

```bash
# Check token balance
curl -X POST https://app.keeperhub.com/api/workflow/{workflow-id}/execute \
  -H "Authorization: Bearer $KEEPERHUB_API_KEY" \
  -d '{
    "chainId": 8453,
    "address": "0x646...",
    "tokenAddress": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
  }'
```

## Troubleshooting

- **RPC rate limits:** The code uses public RPC endpoints. For production, use your own endpoints.
- **ABI parsing errors:** Custom JS actions don't parse ABIs; they call RPC directly.
- **Aave contracts:** Pool addresses are hardcoded for Ethereum and Arbitrum. Add more if needed.
