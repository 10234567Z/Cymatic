# Cymatic — AI Agent Over Phone Call (No Internet Required)

> Call an AI agent from any phone. No smartphone needed. No internet. No app. Just your regular phone recharge.
> Multi-agent architecture where specialized AI agents collaborate peer-to-peer over AXL and execute on-chain via KeeperHub.

---

## The Idea

A user dials a phone number from **any phone** (feature phone, landline, smartphone — doesn't matter). They talk to a **network of specialized AI agents** that can:
- Answer questions (via a Reasoning Agent)
- Execute on-chain transactions — DeFi, payments, treasury ops (via an Execution Agent using KeeperHub)
- Monitor blockchain state and report back via voice (via a Monitoring Agent)
- All agents communicate peer-to-peer over AXL with zero central coordinator

The user needs **zero internet**. The only cost is their existing phone plan (voice calls are essentially unlimited/dirt cheap nowadays).

---

## Architecture — Multi-Agent System Over AXL Mesh

The key insight: **each capability is a separate AI agent running on its own AXL node**. They discover each other via the AXL mesh and communicate via MCP services — no central orchestrator needed.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER'S PHONE                                │
│                    (Any phone, no internet)                         │
│                    Dials: +91-XXXX-XXXXXX                          │
│                                          ▲ SMS Receipt             │
│                                          │ (Twilio SMS API)        │
│                    e.g: "Cymatic Receipt: │ 50 USDC sent. Tx: 0x..."│
└──────────────────────────┬───────────────┼─────────────────────────┘
                           │ Voice Call    │ SMS Back-Channel
                           │ (GSM/PSTN)    │ (160-char text receipt)
                           ▼               │
┌──────────────────────────────────────────┴──────────────────────────┐
│                    TELEPHONY GATEWAY                                 │
│         Twilio / Exotel                                             │
│         • WebSocket audio streaming (inbound voice → server)       │
│         • Twilio SMS API (outbound text receipts → phone)          │
│         Cost: ~$0.01-0.02/min voice + ~$0.0075/SMS (platform pays) │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ WebSocket (audio stream)
                           ▼

═══════════════════════  AXL P2P MESH NETWORK  ═══════════════════════
║  All agents run as separate AXL nodes with their own identity keys  ║
║  Communication: encrypted, decentralized, no central coordinator    ║
║  Protocol: MCP services over AXL for structured request/response    ║
══════════════════════════════════════════════════════════════════════

     AXL Node 1                AXL Node 2                AXL Node 3
  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
  │  VOICE AGENT │◄──AXL──►│REASONING AGENT│◄──AXL──►│EXECUTION AGENT│
  │              │  (MCP)   │              │  (MCP)   │              │
  │ MCP Services:│          │ MCP Services:│          │ MCP Services:│
  │ • transcribe │          │ • interpret  │          │ • execute_tx │
  │ • synthesize │          │ • plan_action│          │ • check_bal  │
  │ • stream_audio│         │ • format_resp│          │ • get_health │
  │ • send_sms   │          │              │          │ • swap_tokens│
  │              │          │ Handles:     │          │              │
  │ Handles:     │          │ - LLM calls  │          │ Handles:     │
  │ - Telephony  │          │   to 0G      │          │ - KeeperHub  │
  │   WebSocket  │          │ - Intent     │          │   MCP/REST   │
  │ - STT via 0G │          │   extraction │          │ - Wallet ops │
  │ - TTS via 0G │          │ - Context    │          │ - DeFi plugin│
  │ - SMS via    │          │   management │          │   execution  │
  │   Twilio API │          │              │          │              │
  └──────┬───────┘          └──────────────┘          └──────┬───────┘
         │                                                    │
         ▼                                                    ▼
  ┌──────────────┐                                   ┌───────────────┐
  │  0G COMPUTE  │                                   │   KEEPERHUB   │
  │              │                                   │               │
  │ • Whisper STT│                                   │ • MCP Server  │
  │ • LLM infer. │                                   │ • Turnkey     │
  │ • TTS synth. │                                   │   Wallet      │
  │ • 0G Storage │                                   │ • 20+ DeFi   │
  │ • DA Layer   │                                   │   Plugins     │
  └──────────────┘                                   │ • Gas mgmt   │
                                                     │ • Multi-chain │
                                                     └───────────────┘

                           AXL Node 4 (optional)
                        ┌──────────────────┐
                        │ MONITORING AGENT │
                        │                  │
                        │ MCP Services:    │
                        │ • watch_position │
                        │ • check_alerts   │
                        │ • health_report  │
                        │                  │
                        │ Proactively      │
                        │ monitors on-chain│
                        │ state, broadcasts│
                        │ alerts via AXL   │
                        └──────────────────┘
```

---

## How AXL Is Used (Deep Integration)

### Each Agent = Separate AXL Node

Every agent runs its own AXL binary with a unique ed25519 identity key. They connect to the same AXL mesh via public bootstrap peers.

### Each Agent Exposes MCP Services Over AXL

Agents expose their capabilities as **MCP services** registered with their local AXL MCP router. Other agents call them over the mesh using the peer's public key + service name.

```python
# Voice Agent registers its services with its local MCP router
requests.post("http://127.0.0.1:9003/register", json={
    "service": "voice",
    "endpoint": "http://127.0.0.1:7100/mcp"
})

# Reasoning Agent calls Voice Agent's "voice" service over AXL mesh
curl -X POST http://127.0.0.1:9012/mcp/{voice_agent_pubkey}/voice \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {
      "name": "synthesize",
      "arguments": {"text": "Your balance is 500 USDC", "language": "en"}
    }
  }'
```

### Agent Discovery via AXL Topology

Agents find each other automatically via AXL's mesh routing. No DNS, no service registry:

```python
# Any agent can query the mesh topology
resp = requests.get("http://127.0.0.1:9002/topology")
peers = resp.json()  # shows all reachable nodes

# Then discover what services a peer offers
resp = requests.post(f"http://127.0.0.1:9002/mcp/{peer_id}/execution",
    json={"jsonrpc": "2.0", "method": "tools/list", "id": 1, "params": {}})
```

### AXL Communication Patterns Used

| Pattern | Where Used |
|---------|-----------|
| **MCP Services** (request/response) | Voice Agent ↔ Reasoning Agent (send transcript, get response). Reasoning Agent ↔ Execution Agent (request tx, get result). |
| **Send/Recv** (fire-and-forget) | Monitoring Agent broadcasts alerts to all peers when health factor drops. Voice Agent streams interim "thinking..." signals. |
| **A2A** (agent-to-agent) | Agents advertise skills via `/.well-known/agent.json`. External agents can discover and interact with the Cymatic network. |

---

## Detailed Flow — First Time Caller (Zero-Friction Auto-Onboarding)

**The user NEVER downloads an app, visits a website, or writes down a seed phrase. The onboarding happens entirely through conversation.**

```
1. User dials Cymatic for the first time from their Nokia.
2. VOICE AGENT detects the Caller ID (+91-XXXX...) has no associated account.
3. VOICE AGENT → TTS: "Welcome to Cymatic. I see you're a new user. I'm setting up your secure vault now. Please enter a PIN on your keypad to secure it, then press hash."
4. User presses their PIN on the phone keypad (DTMF). Silent, never spoken aloud.
5. REASONING AGENT hashes the DTMF PIN.
6. EXECUTION AGENT calls KeeperHub API to dynamically provision a new Turnkey MPC wallet.
7. EXECUTION AGENT mints a "Digital Twin" Voice Agent iNFT (ERC-7857) on the **0G Chain** representing the caller.
8. Cymatic maps the Caller ID + Hashed PIN to the new Turnkey address and stores initial encrypted context in **0G Storage** (KV format).
9. VOICE AGENT → TTS: "Your vault is ready. To add money, simply send UPI to 'cymatic@bank' from this number, or visit your local M-Pesa agent. You can also receive transfers from abroad directly to this phone number."
```
*(The user never hears the words "crypto", "blockchain", "seed phrase", or "wallet".)*

---

## How the Wallet Gets Funded (The Fiat On-Ramp for the Unbanked)

An empty wallet is useless. If the user doesn't have internet, they can't use Binance or Coinbase to buy crypto. Here is how physical cash in a village becomes USDC on Base:

1. **Mobile Money & UPI (Local Fiat On-Ramp):** 
   - Feature phone users already use local mobile money systems (M-Pesa via SMS USSD in Africa, UPI via `*99#` USSD in India).
   - The user transfers local fiat (e.g., ₹500 via UPI or 500 KES via M-Pesa) to Cymatic's official merchant account.
   - Using APIs like Kotani Pay, Fonbnk, or Onmeta, Cymatic automatically detects the inbound fiat linked to their Caller ID, converts it to USDC, and drops it into their new Turnkey MPC wallet via KeeperHub.

2. **Cross-Border Remittances (Family Abroad):**
   - Because Cymatic maps a standard phone number (`+91-9876543210`) to an Ethereum address (`0xabc...`), family members working abroad can use a standard Web3 wallet (or Coinbase) to send USDC directly to the user's phone number alias using off-chain resolution.
   - **The UX:** The user's Nokia rings. *"Hello, you just received 50 US Dollars from your son. Would you like to earn 6% interest on this, or withdraw it to your local bank account?"*
   - The user says *"Withdraw 20 dollars to my bank"*, the Execution Agent swaps USDC → Fiat via the API and drops it back into their UPI/M-Pesa account instantly.

---

## Detailed Flow — User Calls to Check Aave Position

```
1. User dials Cymatic number from a basic phone
2. Telephony gateway answers, streams audio via WebSocket

3. VOICE AGENT (AXL Node 1):
   - Receives audio stream from telephony
   - Sends audio to 0G Compute → Whisper STT → "What's my Aave health factor on Arbitrum?"
   - Calls Reasoning Agent via AXL MCP:
     POST /mcp/{reasoning_pubkey}/reason
     { method: "tools/call", params: { name: "interpret", 
       arguments: { text: "What's my Aave health factor on Arbitrum?", caller_id: "+91xxx" } } }

4. REASONING AGENT (AXL Node 2):
   - Receives transcript via AXL MCP
   - Runs LLM on 0G Compute → extracts intent: check_aave_health(chain=arbitrum)
   - Calls Execution Agent via AXL MCP:
     POST /mcp/{execution_pubkey}/execution
     { method: "tools/call", params: { name: "check_health",
       arguments: { protocol: "aave-v3", chain: "42161", user: "0x..." } } }

5. EXECUTION AGENT (AXL Node 3):
   - Receives intent via AXL MCP
   - Calls KeeperHub MCP server → triggers "check-aave-health" workflow
   - KeeperHub reads on-chain state via Aave V3 plugin
   - Returns via AXL: { healthFactor: 1.82, supplied: "5000 USDC", borrowed: "2500 USDC" }

6. REASONING AGENT:
   - Formats response: "Your Aave health factor on Arbitrum is 1.82.
     You have 5000 USDC supplied and 2500 USDC borrowed."
   - Sends back to Voice Agent via AXL MCP

7. VOICE AGENT:
   - Sends text to 0G Compute → TTS → audio
   - Streams audio back through telephony → user hears it
   - **SMS Fallback:** Sends an SMS via Twilio: *"Cymatic Alert: Aave Health Factor 1.82. Supplied: 5000 USDC. Borrowed: 2500 USDC."* (Gives a visual paper-trail to a screenless phone).
```

**Every step between agents goes through AXL mesh — encrypted, P2P, no central broker.**

---

## Detailed Flow — User Executes a Transaction

```
1. User says: "Send 50 USDC to vitalik.eth on Base"

2. VOICE AGENT → (AXL MCP) → REASONING AGENT
   Transcript: "Send 50 USDC to vitalik.eth on Base"

3. REASONING AGENT:
   - LLM detects high-risk action (token transfer)
   - LLM detects high-risk action (token transfer)
   - Sends back to Voice Agent via AXL: "Confirm needed"
   - Response: "You want to send 50 USDC to vitalik.eth on Base.
     Please enter your PIN on your keypad to confirm, then press hash."

4. VOICE AGENT → TTS → user hears confirmation prompt
   User enters PIN silently via DTMF keypad (never spoken aloud)
   Voice Agent verifies PIN hash locally

5. REASONING AGENT → (AXL MCP) → EXECUTION AGENT
   { name: "transfer_token",
     arguments: { token: "USDC", amount: "50", to: "vitalik.eth", chain: "8453" } }

6. EXECUTION AGENT:
   - Calls KeeperHub MCP server:
     execute_workflow → "transfer-erc20" workflow
   - KeeperHub: resolves ENS, estimates gas, signs via Turnkey wallet, submits tx
   - Handles retries with exponential backoff if needed
   - Returns: { txHash: "0xabc...", status: "confirmed" }

7. Result flows back: EXECUTION → (AXL) → REASONING → (AXL) → VOICE → TTS → user
   "Done. 50 USDC sent to vitalik.eth on Base. Transaction hash starts with 0xabc."

8. SMS PAPER TRAIL: Voice Agent triggers Twilio SMS API
   - User receives an SMS text: *"Cymatic Receipt: 50.0 USDC sent to vitalik.eth. Tx Hash: 0xabc..."*
   - This provides a persistent visual record on a feature phone without needing an app.
```

---

## How KeeperHub Is Used (Deep Integration)

### What KeeperHub Workflows Actually Are

KeeperHub workflows are **not Python scripts**. They are visual node/edge graphs defined as JSON and managed through KeeperHub's platform:

- **Workflow format**: JSON nodes + edges (created in the visual builder, exported/imported as JSON, or programmatically created via API/MCP).
- **Custom logic inside a workflow**: JavaScript (KeeperHub's Code plugin runs JS in a `node:vm` sandbox — no Python, no `require`).
- **Python**: that's your agent code living in `platform_agents/`. It calls the KeeperHub MCP/API to create, trigger, and monitor workflows. The workflows themselves live on KeeperHub's platform.

Example workflow node structure (what you POST to the API / what MCP creates):
```json
{
  "id": "transfer-1",
  "type": "action",
  "data": {
    "label": "Transfer USDC",
    "type": "action",
    "config": {
      "actionType": "web3/transfer-token",
      "network": "8453",
      "toAddress": "{{Trigger.to}}",
      "tokenAddress": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      "amount": "{{Trigger.amount}}",
      "walletId": "{{env.TURNKEY_WALLET_ID}}"
    },
    "status": "idle"
  }
}
```

### MCP Server Integration

KeeperHub MCP is not a vibe-coding helper — it is a full operations interface exposing 19 tools covering CRUD and execution for your deployed workflows. The Execution Agent connects to it with an org-scoped API key and calls it like an internal RPC:

```python
# platform_agents/execution_agent/main.py
# This is YOUR agent code (Python), running off-chain.
# It calls KeeperHub MCP to manage/run workflows that live on KeeperHub's platform.

KEEPERHUB_MCP = "https://app.keeperhub.com/mcp"
KEEPERHUB_KEY = "kh_your_org_key"  # org-scoped, kh_ prefix

# When another Cymatic agent calls via AXL, the Execution Agent proxies to KeeperHub:
async def handle_execute_tx(params):
    # 1. Find or create a pre-built workflow (created once, reused)
    workflows = keeperhub_mcp.list_workflows()  # browse YOUR deployed workflows
    wf = next((w for w in workflows if w["name"] == "transfer-erc20"), None)

    if not wf:
        # ai_generate_workflow creates a workflow on KeeperHub's platform
        wf = keeperhub_mcp.ai_generate_workflow(
            prompt=f"Transfer {params['amount']} {params['token']} to {params['to']} on chain {params['chain']}"
        )

    # 2. Execute workflow
    execution = keeperhub_mcp.execute_workflow(workflow_id=wf["id"])

    # 3. Poll status
    status = keeperhub_mcp.get_execution_status(execution_id=execution["id"])

    # 4. Get logs with tx hash
    logs = keeperhub_mcp.get_execution_logs(execution_id=execution["id"])

    return logs
```

### Pre-built Workflow Templates

Deploy KeeperHub workflow templates for common DeFi operations:

| Workflow | KeeperHub Actions Used | Trigger |
|----------|----------------------|---------|
| `check-balance` | `web3/check-balance`, `web3/check-token-balance` | AXL MCP call |
| `transfer-erc20` | `web3/transfer-token` (requires `walletId`) | AXL MCP call |
| `check-aave-health` | Aave V3 plugin read operations | AXL MCP call |
| `swap-tokens` | Uniswap / CoW Swap plugin | AXL MCP call |
| `compound-rewards` | Spark/Aave plugin claim + supply | AXL MCP call |
| `monitor-vault` | `web3/read-contract` + Condition node + Telegram notification | Schedule (every 5 min) |

### Wallet Security (The "No-Wallet" Wallet)

- The user **NEVER** creates a wallet out-of-band, downloads an app, or sees a seed phrase. If they have to touch a website, we've failed.
- **Fully Automatic Provisioning:** On their first phone call, Cymatic uses the user's Caller ID to dynamically provision a KeeperHub **Turnkey MPC wallet** via the Execution Agent.
- **Authentication:** Two-factor — same model every bank phone line uses, but on-chain:
  - **Factor 1 — Caller ID:** Carrier-verified at the telecom layer. Identifies which account and iNFT this session belongs to. Not used as a security control alone — just identity lookup.
  - **Factor 2 — DTMF PIN:** User enters their PIN silently on the phone keypad (touch-tones). Never spoken aloud, never in the audio stream, not susceptible to ambient eavesdropping or voice recognition misparse. Twilio captures the DTMF digits server-side; only the bcrypt hash is stored in 0G Storage KV. Works on every phone on earth including feature phones with no internet.
  - **Safety net — transaction limits:** Single-call transfer cap (e.g. $50) as a last-resort control. Draining a wallet requires multiple authenticated calls, each independently logged to 0G Storage.
- **Non-custodial:** Keys stay in Turnkey's secure enclaves. Cymatic does not hold the private keys, but the user controls them purely via verified voice commands.
- Perfect for phone-based auth where MetaMask or hardware wallets are impossible.

### Web3 Action Reference Used

```
Read (no wallet):
  web3/check-balance       → network, address
  web3/check-token-balance → network, address, tokenAddress
  web3/read-contract       → network, contractAddress, functionName

Write (requires wallet):
  web3/transfer-funds      → network, toAddress, amount, walletId
  web3/transfer-token      → network, toAddress, tokenAddress, amount, walletId
  web3/write-contract      → network, contractAddress, functionName, walletId

Chains: "1" (ETH), "8453" (Base), "42161" (Arbitrum), "137" (Polygon), "11155111" (Sepolia)
```

---

## Deployment Model — What Runs Where

Cymatic does **not** deploy agent processes directly on 0G Chain. 0G is infrastructure consumed by agents, not a hosting platform for long-running server processes. The split is:

| Layer | What Runs There | What Cymatic Puts There |
|---|---|---|
| **0G Chain** | Smart contracts, on-chain state, settlements | iNFT identity contracts (ERC-7857), user-to-wallet mapping, token transfers |
| **0G Compute** | Decentralized GPU inference marketplace (API calls, pay-per-use) | Whisper STT, TTS synthesis, LLM (Reasoning Agent) inference — billed per call |
| **0G Storage** | Decentralized key-value + append-only log storage | KV: phone number → wallet/iNFT mapping; Log: conversation history, execution audit trail |
| **0G DA** | Data availability layer | Scalable audit trail for A2A messages and on-chain KeeperHub transactions |
| **KeeperHub** | Managed workflow execution platform (hosted, not self-run) | Pre-built DeFi workflows (check-aave-health, transfer-erc20, etc.) deployed as KeeperHub workflows |
| **AXL Mesh** | P2P encrypted transport layer | Each agent runs as a separate AXL node; A2A calls are MCP over AXL |
| **Off-chain servers** | Conventional containers / VPS / K8s — what your agents **actually run on** | Voice Agent, Reasoning Agent, Execution Agent, Monitoring Agent processes |

Agents are regular Python services. They are off-chain processes that call into the above infrastructure layers. 0G Chain does not host agent processes — it is a settlement and identity layer.

## How 0G Is Used

| 0G Component | How Cymatic Uses It |
|---|---|
| **Compute Network** | Inference API consumed by agents (pay-per-use). Voice Agent calls it for Whisper STT + TTS. Reasoning Agent calls it for LLM inference. This is a marketplace for GPU compute — 0G Compute does **not** host or run the agents themselves. |
| **Storage (KV + Log)** | Real-time state (KV) maps phone numbers to wallet addresses / iNFTs. Append-only Logs store historical conversation context so memory persists across calls over years. |
| **Data Availability** | Infinitely scalable audit trail. Every Agent-to-Agent AXL message and on-chain KeeperHub transaction is published for transparency and dispute resolution. |
| **0G Chain (iNFTs)** | Phone numbers are mapped to their very own "Digital Twin" Voice Agent, minted as an **iNFT (ERC-7857)**. This gives the user total ownership of their AI brain and data, abstractly linked to their phone number. iNFT is for identity only — general Cymatic agent logic does not deploy on-chain. |
| **Service Marketplace** | Cymatic Voice + Reasoning agents are listed as services. Other builders can build Web2 API extensions on top of our swarm primitive. |

---

### The Incentive Flywheel
```
1. More offline users make calls 
   ➔ 2. More TVL in Turnkey wallets / more swap volume 
   ➔ 3. Protocol generates more yield/fees 
   ➔ 4. Protocol auto-buys $DIAL 
   ➔ 5. $DIAL price appreciates 
   ➔ 6. More node operators stake $DIAL to run AXL agents 
   ➔ 7. Voice/LLM latency drops and accuracy increases 
   ➔ 8. Better UX attracts more offline users.
```

---
