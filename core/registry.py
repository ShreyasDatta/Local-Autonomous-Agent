"""
E:\AI_Hub\agents\core\registry.py
Tool Definition Registry, Defensive ACI Whitelisting & HITL Safety Metadata
"""
import datetime
from typing import Dict, Any, List, Callable

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool(
            name="calculator",
            func=self._calculator_impl,
            schema={
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "Perform basic arithmetic operations (+, -, *, /). ONLY pass raw single-line mathematical expressions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Single-line math expression, e.g. '453 * 18'."
                            }
                        },
                        "required": ["expression"]
                    }
                }
            },
            requires_approval=False
        )

        self.register_tool(
            name="get_current_time",
            func=self._get_current_time_impl,
            schema={
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "description": "Retrieve current local system clock time.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            requires_approval=False
        )

    def register_tool(self, name: str, func: Callable, schema: Dict[str, Any], requires_approval: bool = False):
        self._tools[name] = {
            "func": func,
            "schema": schema,
            "requires_approval": requires_approval
        }

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [tool_data["schema"] for tool_data in self._tools.values()]

    def get_tool_metadata(self, name: str) -> Dict[str, Any]:
        return self._tools.get(name, {})

    def execute(self, name: str, kwargs: Dict[str, Any]) -> str:
        if name not in self._tools:
            return f"Error: Tool '{name}' is not registered."
        try:
            return str(self._tools[name]["func"](**kwargs))
        except Exception as e:
            return f"Execution Error in '{name}': {str(e)}"

    @staticmethod
    def _calculator_impl(expression: str) -> str:
        clean_expr = str(expression).strip().strip("`").strip("'").strip('"')
        clean_expr = clean_expr.replace("x", "*").replace("X", "*").replace("times", "*")

        allowed_chars = set("0123456789+-*/. ()")
        if not all(c in allowed_chars for c in clean_expr):
            return f"Refusal: Expression contains invalid characters. Cleaned string was: '{clean_expr}'"

        try:
            result = eval(clean_expr, {"__builtins__": None}, {})
            return str(result)
        except Exception as e:
            return f"Calculation Error: {str(e)}"

    @staticmethod
    def _get_current_time_impl() -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")