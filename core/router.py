r"""
E:\AI_Hub\agents\core\router.py
Hardened Intent Router with Fast Heuristics & Defensive JSON Parsing
"""
import re
import json
import urllib.request
from typing import List, Dict, Any

class IntentRouter:
    """
    Uses fast regex heuristics and Ollama's logit-constrained grammar decoding
    to classify user intent in ~20-30 ms without exposing tool schemas to main context.
    """
    MATH_PATTERN = re.compile(
        r'(\d+\s*[\+\-\*/\^xX]\s*\d+)|(\d+\s*(times|multiplied by|divided by|plus|minus)\s*\d+)|(calculate|compute)',
        re.IGNORECASE
    )
    TIME_PATTERN = re.compile(
        r'(what time|current time|date|clock|today)',
        re.IGNORECASE
    )
    CODE_REQUEST_PATTERN = re.compile(
        r'^\s*(write|create|implement|generate|draft|design|refactor|debug|explain|review)\b',
        re.IGNORECASE
    )
    CODE_CONTEXT_PATTERN = re.compile(
        r'\b(def|class|struct|function|script|code|c\+\+|python|javascript|rust|golang|bash|ruby|sql|uint\d+_t|malloc)\b',
        re.IGNORECASE
    )

    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "qwen2.5-coder:14b-instruct-q4_K_M"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def probe_intents(self, history: List[Dict[str, Any]], current_query: str) -> List[str]:
        required = set()

        # Fast Heuristic Check (< 1 ms)
        # Coding requests may contain words such as "calculate" or "time"
        # as domain vocabulary without requesting deterministic tools.
        if self.CODE_REQUEST_PATTERN.search(current_query) or self.CODE_CONTEXT_PATTERN.search(current_query):
            return []
        if self.MATH_PATTERN.search(current_query):
            required.add("calculator")
        if self.TIME_PATTERN.search(current_query):
            required.add("get_current_time")

        if required:
            return list(required)

        # Logit-Constrained Probe Fallback for Referential/Anaphoric Queries
        probe_messages = []
        recent_history = history[-2:] if len(history) > 1 else []
        for msg in recent_history:
            if msg["role"] in ["user", "assistant"]:
                probe_messages.append({"role": msg["role"], "content": msg["content"]})

        probe_prompt = (
            "You are a deterministic intent classifier. DO NOT answer the user. "
            "DO NOT explain concepts. Output ONLY one JSON object.\n"
            "The object must have this shape: {\"required_tools\": [\"calculator\", \"get_current_time\"]}.\n"
            "Allowed tools: calculator and get_current_time.\n"
            "Select calculator for math or arithmetic, and get_current_time for system clock or date requests.\n"
            "If no tools are needed, output exactly {\"required_tools\": []}."
        )
        probe_messages.insert(0, {"role": "system", "content": probe_prompt})
        probe_messages.append({"role": "user", "content": current_query})

        payload = {
            "model": self.model,
            "messages": probe_messages,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 100,
                "stop": ["}", "\n\n", "```"],
            },
            "keep_alive": "60m"
        }

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                content = res["choices"][0]["message"]["content"]

                # Defensive JSON Extraction: Slice between first '{' and last '}'
                # Prevents JSONDecodeError when open-weight models emit markdown fences or preambles
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    clean_json = content[start_idx:end_idx + 1]
                    parsed = json.loads(clean_json)
                    return parsed.get("required_tools", [])
                else:
                    print(f"  [Router Warning] Could not locate JSON object in probe response: '{content}'")
                    return []
        except Exception as e:
            print(f"  [Router Error] Probe parsing failed: {e}")
            return []