#!/usr/bin/env python3
"""
Local AI Agent powered by Ollama
- High-Precision Tool Routing (Zero tool-poisoning on greetings/chat)
- Tested for llama3.1:8b-instruct-q4_K_M & qwen2.5-coder:14b-instruct-q4_K_M
"""

import argparse
import datetime
import http.server
import json
import os
import re
import sys
import urllib.error
import urllib.request
import webbrowser

MODEL_ALIASES = {
    "llama": "llama3.1:8b-instruct-q4_K_M",
    "llama3": "llama3.1:8b-instruct-q4_K_M",
    "llama3.1": "llama3.1:8b-instruct-q4_K_M",
    "qwen": "qwen2.5-coder:14b-instruct-q4_K_M",
    "qwen2.5": "qwen2.5-coder:14b-instruct-q4_K_M",
    "coder": "qwen2.5-coder:14b-instruct-q4_K_M"
}

# ==========================================
# 1. TOOL REGISTRY
# ==========================================
class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self.schemas = []

    def register(self, name: str, description: str, parameters: dict):
        def decorator(func):
            self.tools[name] = func
            self.schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters
                }
            })
            return func
        return decorator

    def execute(self, name: str, arguments: dict) -> str:
        if name not in self.tools:
            return f"Error: Tool '{name}' not found."
        try:
            return str(self.tools[name](**arguments))
        except Exception as e:
            return f"Error executing '{name}': {str(e)}"

registry = ToolRegistry()

@registry.register(
    name="calculator",
    description="Calculate mathematical expressions. Pass arithmetic expression as string.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "e.g. '453 * 18'"}
        },
        "required": ["expression"]
    }
)
def calculator(expression: str) -> str:
    clean_expr = str(expression).strip().replace(",", "")
    allowed = set("0123456789+-*/(). %")
    if not all(c in allowed for c in clean_expr):
        return f"Invalid characters in math expression: {clean_expr}"
    try:
        return str(eval(clean_expr, {"__builtins__": None}, {}))
    except Exception as err:
        return f"Calculation error: {err}"

@registry.register(
    name="get_current_time",
    description="Get current system date and time.",
    parameters={"type": "object", "properties": {}}
)
def get_current_time() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==========================================
# 2. AGENT ENGINE WITH PRECISION ROUTER
# ==========================================
class Agent:
    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "llama3.1:8b-instruct-q4_K_M"
    ):
        self.base_url = base_url.rstrip("/")
        self.model = MODEL_ALIASES.get(model.lower(), model)
        self.system_prompt = (
            "You are a helpful, direct, and capable local AI assistant. "
            "Respond naturally and thoroughly to user questions."
        )
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def _requires_tools(self, user_text: str) -> bool:
        """
        High-Precision Intent Gate:
        Only enables tools when actual math or time requests are present.
        """
        text = user_text.lower().strip()

        # 1. Obvious conversational inputs -> NO tools
        # Handles punctuation like "Hi,", "Hello!", "whats up"
        clean_text = re.sub(r"[^\w\s]", "", text)
        first_word = clean_text.split()[0] if clean_text.split() else ""
        if first_word in ["hi", "hello", "hey", "greetings"]:
            return False

        if any(phrase in text for phrase in [
            "what can you do", "who are you", "tell me about yourself",
            "explain", "how does", "what is an agent", "write code", "python", "c++"
        ]):
            return False

        # Negative filter: If user explicitly says "not asking for time"
        if "not asking" in text or "dont want the time" in text:
            return False

        # 2. Math check: Must have digits AND an arithmetic symbol, or explicit calc command
        has_math_pattern = bool(re.search(r"\d+\s*[\+\-\*\/\^]\s*\d+", text))
        has_calc_word = any(w in text for w in ["calculate", "compute", "evaluate"]) and any(c.isdigit() for c in text)

        # 3. Time check: Must explicitly ask for current time/date
        has_time_query = any(phrase in text for phrase in [
            "current time", "what time is it", "what is the time",
            "today's date", "current date", "what is the date", "what date is it"
        ])

        return has_math_pattern or has_calc_word or has_time_query

    def _call_ollama(self, messages: list, tools: list = None) -> dict:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer ollama"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools if tools else None,
            "stream": False
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]
        except urllib.error.URLError as err:
            return {"role": "assistant", "content": f"⚠️ Ollama connection failed: {err.reason}"}
        except Exception as err:
            return {"role": "assistant", "content": f"⚠️ Runtime Error: {err}"}

    def chat(self, user_input: str, on_thought=None) -> str:
        self.messages.append({"role": "user", "content": user_input})

        # Precision Routing: Only attach tools if the prompt demands it
        needs_tools = self._requires_tools(user_input)
        active_tools = registry.schemas if needs_tools else None

        max_turns = 4
        while max_turns > 0:
            max_turns -= 1
            assistant_msg = self._call_ollama(self.messages, tools=active_tools)
            tool_calls = assistant_msg.get("tool_calls")
            content = assistant_msg.get("content") or ""

            # If legitimate tool calls were produced
            if tool_calls:
                self.messages.append(assistant_msg)
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    raw_args = tc["function"]["arguments"]
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

                    if on_thought:
                        on_thought(f"Invoking: `{fn_name}` with {args}")

                    result = registry.execute(fn_name, args)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", "call_1"),
                        "name": fn_name,
                        "content": result
                    })
                # After executing tools, synthesize final answer in pure chat mode
                active_tools = None
                continue

            clean_reply = content.strip()
            self.messages.append({"role": "assistant", "content": clean_reply})
            return clean_reply

        return "Error: Exceeded reasoning loops."


# ==========================================
# 3. INTERFACES (CLI & BROWSER GUI)
# ==========================================
def run_cli(agent: Agent):
    print("=" * 60)
    print(f"  Local AI Agent ({agent.model})")
    print("  Type 'exit' or 'quit' to stop.")
    print("=" * 60)

    def log_thought(msg):
        print(f"\033[93m[Action]\033[0m {msg}")

    while True:
        try:
            user_text = input("\n\033[94mUser > \033[0m").strip()
            if not user_text:
                continue
            if user_text.lower() in ["exit", "quit"]:
                break
            response = agent.chat(user_text, on_thought=log_thought)
            print(f"\033[92mAgent >\033[0m {response}")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break


def run_gui(agent: Agent, port: int = 8080):
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Local Agent ({agent.model})</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; display: flex; justify-content: center; height: 100vh; }}
        .chat-container {{ width: 100%; max-width: 860px; height: 100vh; display: flex; flex-direction: column; }}
        .header {{ padding: 16px 20px; background: #1e293b; border-bottom: 1px solid #334155; font-size: 1.05rem; font-weight: 600; display: flex; justify-content: space-between; }}
        .badge {{ font-size: 0.8rem; background: #0284c7; padding: 3px 8px; border-radius: 6px; }}
        .messages {{ flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 14px; }}
        .bubble {{ max-width: 82%; padding: 14px 18px; border-radius: 12px; line-height: 1.5; font-size: 0.95rem; white-space: pre-wrap; }}
        .user {{ align-self: flex-end; background: #2563eb; color: #fff; }}
        .agent {{ align-self: flex-start; background: #1e293b; border: 1px solid #334155; }}
        .system {{ align-self: center; font-size: 0.8rem; color: #94a3b8; font-style: italic; }}
        .input-bar {{ display: flex; padding: 16px; background: #1e293b; border-top: 1px solid #334155; gap: 10px; }}
        input {{ flex: 1; padding: 12px 16px; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: #fff; font-size: 0.95rem; outline: none; }}
        button {{ padding: 12px 20px; border-radius: 8px; border: none; background: #2563eb; color: #fff; font-weight: 600; cursor: pointer; }}
        button:hover {{ background: #1d4ed8; }}
    </style>
</head>
<body>
<div class="chat-container">
    <div class="header">
        <span>Local AI Agent</span>
        <span class="badge">{agent.model}</span>
    </div>
    <div class="messages" id="chat">
        <div class="bubble system">Connected to Ollama ({agent.model}). Ready for conversation, tools, and code.</div>
    </div>
    <form class="input-bar" id="chatForm">
        <input type="text" id="userInput" placeholder="Type a message..." autocomplete="off" required />
        <button type="submit">Send</button>
    </form>
</div>
<script>
    const chat = document.getElementById('chat');
    const form = document.getElementById('chatForm');
    const input = document.getElementById('userInput');

    function appendMessage(text, role) {{
        const div = document.createElement('div');
        div.className = 'bubble ' + role;
        div.textContent = text;
        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
    }}

    form.onsubmit = async (e) => {{
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        appendMessage(text, 'user');
        input.value = '';

        try {{
            const res = await fetch('/api/chat', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ message: text }})
            }});
            const data = await res.json();
            appendMessage(data.reply, 'agent');
        }} catch (err) {{
            appendMessage("Connection error.", 'system');
        }}
    }};
</script>
</body>
</html>"""

    class ChatHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        def do_POST(self):
            if self.path == "/api/chat":
                content_len = int(self.headers.get("Content-Length", 0))
                post_body = self.rfile.read(content_len)
                req_data = json.loads(post_body.decode("utf-8"))
                user_msg = req_data.get("message", "")

                reply = agent.chat(user_msg)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"reply": reply}).encode("utf-8"))

    server = http.server.HTTPServer(("127.0.0.1", port), ChatHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"Starting Chat GUI at {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Local Ollama AI Agent.")
    parser.add_argument("--cli", action="store_true", help="Terminal CLI mode.")
    parser.add_argument("--gui", action="store_true", help="Browser GUI mode.")
    parser.add_argument("--model", type=str, default="llama3", help="Model alias: llama3, qwen, coder.")
    parser.add_argument("--base-url", type=str, default="http://localhost:11434/v1", help="Ollama endpoint.")
    parser.add_argument("--port", type=int, default=8080, help="GUI port.")
    args = parser.parse_args()

    agent_instance = Agent(base_url=args.base_url, model=args.model)

    if args.gui:
        run_gui(agent_instance, port=args.port)
    else:
        run_cli(agent_instance)