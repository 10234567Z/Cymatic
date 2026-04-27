from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request


CHAIN_KEYWORDS: dict[str, str] = {
    "ethereum": "1",
    "eth": "1",
    "mainnet": "1",
    "base": "8453",
    "arbitrum": "42161",
    "arb": "42161",
    "polygon": "137",
    "matic": "137",
    "sepolia": "11155111",
}


INTENT_RULES: dict[str, dict[str, Any]] = {
    "check_token_balance": {
        "keywords": ["balance", "token", "holdings", "how much", "usdc", "usdt"],
        "patterns": ["*balance*", "*token*"],
    },
    "transfer_erc20": {
        "keywords": ["transfer", "send", "pay", "move", "erc20"],
        "patterns": ["*transfer*", "*send*", "*payment*"],
    },
    "check_aave_health": {
        "keywords": ["aave", "health", "hf", "liquidation"],
        "patterns": ["*aave*health*", "*health*"],
    },
    "monitor_aave_health": {
        "keywords": ["monitor", "watch", "alert", "aave"],
        "patterns": ["*monitor*", "*alert*"],
    },
}


TERMINAL_STATUSES = {"success", "error", "cancelled"}


@dataclass
class ReasoningResult:
    intent: str
    intent_confidence: float
    entities: dict[str, Any]
    selected_workflow: dict[str, Any] | None
    execution: dict[str, Any] | None
    error: str | None = None


class KeeperHubAPI:
    def __init__(self, api_key: str, base_url: str = "https://app.keeperhub.com"):
        if not api_key:
            raise ValueError("Missing KEEPERHUB_API_KEY")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Cymatic-Platform-Agent/0.1 (+https://app.keeperhub.com)",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"KeeperHub {method} {path} failed: {exc.code} {raw}") from exc

    def list_workflows(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/api/workflows")
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("workflows"), list):
            return payload["workflows"]
        return []

    def execute_workflow(self, workflow_id: str, input_payload: dict[str, Any]) -> str:
        payload = self._request(
            "POST",
            f"/api/workflow/{workflow_id}/execute",
            {"input": input_payload},
        )
        execution_id = payload.get("executionId") or payload.get("id")
        if not isinstance(execution_id, str) or not execution_id:
            raise RuntimeError("Execution id missing in KeeperHub response")
        return execution_id

    def execution_status(self, execution_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/workflows/executions/{execution_id}/status")

    def list_executions(self, workflow_id: str) -> list[dict[str, Any]]:
        payload = self._request("GET", f"/api/workflows/{workflow_id}/executions")
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("executions"), list):
            return payload["executions"]
        return []


class ReasoningAgent:
    def __init__(self, keeperhub: KeeperHubAPI):
        self.keeperhub = keeperhub

    def handle_call_text(self, call_text: str) -> ReasoningResult:
        intent, confidence = self._extract_intent(call_text)
        entities = self._extract_entities(call_text)
        workflows = self.keeperhub.list_workflows()
        selected = self._match_workflow(intent, call_text, workflows)
        if not selected:
            return ReasoningResult(
                intent=intent,
                intent_confidence=confidence,
                entities=entities,
                selected_workflow=None,
                execution=None,
                error="No matching workflow found",
            )

        input_payload = self._build_execution_input(intent, entities)
        execution_id = self.keeperhub.execute_workflow(selected["id"], input_payload)

        status = "pending"
        for _ in range(8):
            status_payload = self.keeperhub.execution_status(execution_id)
            status = str(status_payload.get("status", "pending")).lower()
            if status in TERMINAL_STATUSES:
                break
            time.sleep(1)

        execution = self._resolve_execution(selected["id"], execution_id, fallback_status=status)
        return ReasoningResult(
            intent=intent,
            intent_confidence=confidence,
            entities=entities,
            selected_workflow=selected,
            execution=execution,
        )

    def _extract_intent(self, text: str) -> tuple[str, float]:
        normalized = text.lower()
        best_intent = "check_token_balance"
        best_score = -1

        for intent_name, rule in INTENT_RULES.items():
            score = 0
            for keyword in rule["keywords"]:
                if keyword in normalized:
                    score += 1
            if score > best_score:
                best_intent = intent_name
                best_score = score

        confidence = min(0.99, 0.4 + (best_score * 0.15)) if best_score > 0 else 0.35
        return best_intent, confidence

    def _extract_entities(self, text: str) -> dict[str, Any]:
        normalized = text.lower()
        entities: dict[str, Any] = {}

        for keyword, chain_id in CHAIN_KEYWORDS.items():
            if re.search(rf"\b{re.escape(keyword)}\b", normalized):
                entities["chain_id"] = chain_id
                break

        addresses = re.findall(r"0x[a-fA-F0-9]{40}", text)
        if addresses:
            entities["wallet_address"] = addresses[0]
        if len(addresses) > 1:
            entities["to_address"] = addresses[1]

        amount_match = re.search(r"\b(\d+(?:\.\d+)?)\b", normalized)
        if amount_match:
            entities["amount"] = amount_match.group(1)

        token_match = re.search(r"\b(usdc|usdt|dai|weth|eth)\b", normalized)
        if token_match:
            entities["token_symbol"] = token_match.group(1).upper()

        return entities

    def _match_workflow(
        self,
        intent: str,
        call_text: str,
        workflows: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        normalized_text = call_text.lower()
        patterns = INTENT_RULES.get(intent, {}).get("patterns", [])
        intent_keywords = set(INTENT_RULES.get(intent, {}).get("keywords", []))
        action_hint_by_intent = {
            "check_token_balance": "web3/check-token-balance",
            "transfer_erc20": "web3/transfer-token",
            "check_aave_health": "web3/read-contract",
            "monitor_aave_health": "web3/read-contract",
        }
        expected_action = action_hint_by_intent.get(intent)

        best: tuple[int, dict[str, Any]] | None = None

        for workflow in workflows:
            workflow_name = str(workflow.get("name", "")).lower()
            description = str(workflow.get("description", "")).lower()
            action_types: list[str] = []
            nodes = workflow.get("nodes")
            if isinstance(nodes, list):
                for node in nodes:
                    if not isinstance(node, dict) or node.get("type") != "action":
                        continue
                    data = node.get("data") or {}
                    config = data.get("config") if isinstance(data, dict) else {}
                    if isinstance(config, dict):
                        action_type = config.get("actionType")
                        if isinstance(action_type, str):
                            action_types.append(action_type.lower())

            searchable = f"{workflow_name} {description} {' '.join(action_types)}".strip()
            if not searchable:
                continue

            score = 0
            if any(fnmatch.fnmatch(workflow_name, p) for p in patterns):
                score += 8
            if any(fnmatch.fnmatch(searchable, p) for p in patterns):
                score += 5

            for keyword in intent_keywords:
                if keyword in searchable:
                    score += 2
                if keyword in normalized_text and keyword in searchable:
                    score += 1

            if expected_action and expected_action in action_types:
                score += 10

            if workflow.get("enabled"):
                score += 1

            if best is None or score > best[0]:
                best = (score, workflow)

        if best is None or best[0] <= 0:
            return None
        return best[1]

    def _build_execution_input(self, intent: str, entities: dict[str, Any]) -> dict[str, Any]:
        chain_id = entities.get("chain_id", "1")
        wallet = entities.get("wallet_address", "0x0000000000000000000000000000000000000000")
        token_map = {
            "1": {
                "USDC": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            },
            "8453": {
                "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "USDT": "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2",
            },
            "42161": {
                "USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
                "USDT": "0xFd086bC7CD5C481DCC9C85ebe478A1C0b69FCbb9",
            },
        }
        token_symbol = entities.get("token_symbol", "USDC")
        token_address = token_map.get(chain_id, token_map["1"]).get(token_symbol, token_map["1"]["USDC"])

        if intent == "check_token_balance":
            return {
                "chainId": chain_id,
                "address": wallet,
                "tokenAddress": token_address,
            }
        if intent == "transfer_erc20":
            return {
                "chainId": chain_id,
                "toAddress": entities.get("to_address", wallet),
                "tokenAddress": token_address,
                "amount": entities.get("amount", "1"),
                "walletId": os.getenv("KEEPERHUB_WALLET_ID", ""),
            }
        if intent == "check_aave_health":
            return {
                "chainId": chain_id,
                "walletAddress": wallet,
            }
        if intent == "monitor_aave_health":
            return {
                "chainId": chain_id,
                "walletAddress": wallet,
                "healthThreshold": float(os.getenv("AAVE_HEALTH_THRESHOLD", "1.5")),
            }
        return {
            "chainId": chain_id,
            "address": wallet,
            "tokenAddress": token_address,
        }

    def _resolve_execution(
        self,
        workflow_id: str,
        execution_id: str,
        fallback_status: str,
    ) -> dict[str, Any]:
        executions = self.keeperhub.list_executions(workflow_id)
        for item in executions:
            if item.get("id") == execution_id:
                return {
                    "id": execution_id,
                    "status": item.get("status", fallback_status),
                    "output": item.get("output"),
                    "error": item.get("error"),
                }
        return {
            "id": execution_id,
            "status": fallback_status,
            "output": None,
            "error": None,
        }


def load_env_file() -> None:
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.getcwd(), "backend", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "backend", ".env"),
    ]

    for path in candidates:
        full = os.path.abspath(path)
        if not os.path.exists(full):
            continue
        with open(full, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)


def main() -> None:
    load_env_file()
    if len(sys.argv) < 2:
        print("Usage: python main.py '<caller sentence>'")
        sys.exit(1)

    call_text = " ".join(sys.argv[1:])
    keeperhub = KeeperHubAPI(
        api_key=os.getenv("KEEPERHUB_API_KEY", ""),
        base_url=os.getenv("KEEPERHUB_BASE_URL", "https://app.keeperhub.com"),
    )
    agent = ReasoningAgent(keeperhub)
    result = agent.handle_call_text(call_text)
    print(
        json.dumps(
            {
                "intent": result.intent,
                "intentConfidence": result.intent_confidence,
                "entities": result.entities,
                "selectedWorkflow": result.selected_workflow,
                "execution": result.execution,
                "error": result.error,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
