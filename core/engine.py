"""
E:\AI_Hub\agents\core\engine.py
Hardened Two-Phase Decoupled Dispatch Engine
- Position 0 Prefix Alignment (100% RadixAttention KV-Cache Reuse)
- Guard-Gated Hybrid Intent Routing
- Dual-Path Parameter Extraction (OpenAI Array + Content Substring Fallback)
- Human-in-the-Loop (HITL) Execution Circuit Breaker
"""
import json
import urllib.error
import urllib.request
from typing import List, Dict, Any, Optional
from core.router import IntentRouter
from core.registry import ToolRegistry

class AgentEngine:
    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen2.5-coder:14b-instruct-q4_K_M",
        system_prompt: str = "You are a helpful local AI co-developer.",
        context_window: int = 32768
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.system_prompt = system_prompt
        self.context_window = context_window
        self.registry = ToolRegistry()
        self.router = IntentRouter(base_url=self.base_url, model=self.model)

        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

    def step(self, user_input: str) -> Dict[str, Any]:
        required_tools = self.router.probe_intents(self.history, user_input)

        if not required_tools:
            assistant_text = self._dispatch_pure_completion(user_input)
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": assistant_text})
            return {"status": "completed", "response": assistant_text}

        tool_results: Dict[str, Any] = {}
        pending_approvals: List[Dict[str, Any]] = []

        for tool_name in required_tools:
            tool_meta = self.registry.get_tool_metadata(tool_name)
            tool_schema = tool_meta.get("schema")
            if not tool_schema:
                continue

            extracted_args = self._extract_parameters_ephemeral(user_input, tool_schema)
            print(f"  [Action] Ephemeral Extraction: `{tool_name}` with {extracted_args}")

            if tool_meta.get("requires_approval", False):
                pending_approvals.append({
                    "tool_name": tool_name,
                    "args": extracted_args,
                    "reason": "Destructive or state-changing action requires confirmation."
                })
            else:
                tool_results[tool_name] = self.registry.execute(tool_name, extracted_args)

        if pending_approvals:
            return {
                "status": "confirmation_required",
                "pending_actions": pending_approvals,
                "completed_observations": tool_results
            }

        assistant_text = self._synthesize_with_observations(user_input, tool_results)

        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": assistant_text})
        return {"status": "completed", "response": assistant_text}

    def _extract_parameters_ephemeral(self, user_input: str, tool_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dual-Path Extraction: Checks top-level message.tool_calls first.
        If empty, defensively parses inline raw JSON / <tool_call> tags from message.content.
        """
        recent_history = self.history[-2:] if len(self.history) > 1 else []
        ephemeral_messages = [{"role": "system", "content": self.system_prompt}]

        for msg in recent_history:
            if msg["role"] in ["user", "assistant"]:
                ephemeral_messages.append({"role": msg["role"], "content": msg["content"]})

        ephemeral_messages.append({
            "role": "user",
            "content": f"{user_input}\n\n[INSTRUCTION: Emit parameter arguments for tool '{tool_schema['function']['name']}' as valid JSON.]"
        })

        payload = {
            "model": self.model,
            "messages": ephemeral_messages,
            "tools": [tool_schema],
            "stream": False,
            "options": {"temperature": 0.0, "num_ctx": self.context_window},
            "keep_alive": "60m"
        }

        res = self._post_request(payload)
        try:
            choices = res.get("choices", [])
            message = choices[0].get("message", {}) if choices else {}

            # Path A: Standard OpenAI tool_calls array
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                t_call = tool_calls[0] if isinstance(tool_calls, list) else tool_calls
                raw_args = t_call.get("function", {}).get("arguments", {})
                return self._normalise_tool_arguments(
                    json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                )

            # Path B: Defensive Fallback for inline <tool_call> tags or raw JSON in content
            content = message.get("content", "").strip()
            if content:
                cleaned = content.replace("<tool_call>", "").replace("</tool_call>", "").strip()
                start_idx = cleaned.find("{")
                end_idx = cleaned.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    candidate = cleaned[start_idx:end_idx + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError:
                        parsed, _ = json.JSONDecoder().raw_decode(candidate)
                    if "arguments" in parsed and isinstance(parsed["arguments"], dict):
                        return parsed["arguments"]
                    if "parameters" in parsed and isinstance(parsed["parameters"], dict):
                        return parsed["parameters"]
                    return self._normalise_tool_arguments(parsed)
        except Exception as e:
            print(f"  [Extraction Warning] Ephemeral argument parsing failed: {e}")

        return {}

    @staticmethod
    def _normalise_tool_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Unwrap common OpenAI-compatible function_call serialization."""
        if not isinstance(arguments, dict):
            return {}
        function_call = arguments.get("function_call")
        if isinstance(function_call, dict):
            nested = function_call.get("arguments", {})
            if isinstance(nested, str):
                try:
                    nested = json.loads(nested)
                except json.JSONDecodeError:
                    return {}
            if isinstance(nested, dict):
                return nested
        if isinstance(arguments.get("function"), str) and "expression" in arguments:
            return {"expression": arguments["expression"]}
        params = arguments.get("params")
        if isinstance(params, dict) and isinstance(params.get("operation"), str):
            return {"expression": params["operation"]}
        return arguments

    def _synthesize_with_observations(self, user_input: str, tool_results: Dict[str, Any]) -> str:
        obs_lines = ["\n<observation>", "[VERIFIED DETERMINISTIC TOOL EXECUTION RESULTS]"]
        for tool_name, result in tool_results.items():
            obs_lines.append(f"- {tool_name}: {result}")
        obs_lines.append("</observation>\n")

        tail_injected_turn = f"{user_input}\n" + "\n".join(obs_lines)
        synthesis_messages = self.history + [{"role": "user", "content": tail_injected_turn}]

        payload = {
            "model": self.model,
            "messages": synthesis_messages,
            "stream": False,
            "options": {
                "num_ctx": self.context_window,
                "temperature": 0.2,
                "num_predict": 300,
            },
            "keep_alive": "60m"
        }
        res = self._post_request(payload)
        choices = res.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        return message.get("content", "")

    def _dispatch_pure_completion(self, user_input: str) -> str:
        messages = self.history + [{"role": "user", "content": user_input}]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": self.context_window,
                "temperature": 0.2,
                "num_predict": 300,
            },
            "keep_alive": "60m"
        }
        res = self._post_request(payload)
        choices = res.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        return message.get("content", "")

    def _post_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as e:
            return {"choices": [{"message": {"content": f"Execution Error: {e}"}}]}
        except Exception as e:
            return {"choices": [{"message": {"content": f"Execution Error: {e}"}}]}