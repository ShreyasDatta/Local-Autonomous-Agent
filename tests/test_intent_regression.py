import json
from unittest.mock import Mock, patch

import pytest

from core.engine import AgentEngine
from core.registry import ToolRegistry
from core.router import IntentRouter


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


def ollama_message(content):
    return {"choices": [{"message": {"content": content}}]}


def tool_call_response(arguments):
    return {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "arguments": json.dumps(arguments),
                            }
                        }
                    ]
                }
            }
        ]
    }


def print_gate_receipt(gate, title, scenario, payload_tools, result):
    status = result.get("status", "completed")
    tools_label = "None" if payload_tools is None else "Attached"
    print(f"\n[TEST GATE: {gate} | {title}]")
    print(f"  - Scenario: {scenario}")
    print(f"  - Outbound Payload Schema Attached: {tools_label}")
    print(f"  - Result: PASS (Status: {status}, Tools: {tools_label})")


@pytest.fixture
def engine():
    return AgentEngine(
        base_url="http://ollama.test/v1",
        model="test-model",
        system_prompt="Fixed test system prompt.",
    )


def test_pure_chat_returns_completed_without_tools(engine):
    completion_payloads = []

    def post_request(payload):
        completion_payloads.append(payload)
        return ollama_message("A pure conversational answer.")

    with patch.object(engine.router, "probe_intents", return_value=[]), patch.object(
        engine, "_post_request", side_effect=post_request
    ):
        result = engine.step("Explain dependency inversion in one sentence.")

    assert result == {
        "status": "completed",
        "response": "A pure conversational answer.",
    }
    assert completion_payloads[0].get("tools") is None
    assert "tools" not in completion_payloads[0]
    assert engine.history[-1] == {
        "role": "assistant",
        "content": "A pure conversational answer.",
    }
    print_gate_receipt(
        "INT-01",
        "ZERO SCHEMA INFILTRATION",
        "Pure conversational completion",
        completion_payloads[0].get("tools"),
        result,
    )


def test_anaphoric_query_passes_last_two_turns_to_ephemeral_hop(engine):
    engine.history.extend(
        [
            {"role": "user", "content": "Calculate 1024 * 16."},
            {"role": "assistant", "content": "The result is 16384."},
        ]
    )
    extraction_payloads = []
    synthesis_payloads = []

    def post_request(payload):
        if "tools" in payload:
            extraction_payloads.append(payload)
            return tool_call_response({"expression": "16384 * 8"})
        synthesis_payloads.append(payload)
        return ollama_message("The result is 131072.")

    with patch.object(engine.router, "probe_intents", return_value=["calculator"]), patch.object(
        engine, "_post_request", side_effect=post_request
    ):
        result = engine.step("Now multiply that result by 8.")

    extraction_messages = extraction_payloads[0]["messages"]
    assert extraction_messages[:3] == [
        {"role": "system", "content": "Fixed test system prompt."},
        {"role": "user", "content": "Calculate 1024 * 16."},
        {"role": "assistant", "content": "The result is 16384."},
    ]
    assert extraction_messages[-1]["role"] == "user"
    assert "Now multiply that result by 8." in extraction_messages[-1]["content"]
    assert extraction_payloads[0].get("tools") is not None
    assert "tools" in extraction_payloads[0]

    assert result["status"] == "completed"
    assert result["response"] == "The result is 131072."
    assert synthesis_payloads[0].get("tools") is None
    assert "tools" not in synthesis_payloads[0]
    assert all(
        "tool_calls" not in message.get("content", "")
        for message in engine.history
    )
    assert "<observation>" not in json.dumps(engine.history)
    print_gate_receipt(
        "INT-02",
        "ANAPHORIC EPHEMERAL HOP",
        "Last two history turns passed into parameter extraction",
        synthesis_payloads[0].get("tools"),
        result,
    )


def test_destructive_tool_requires_confirmation_before_execution(engine):
    executed = Mock(return_value="changed")
    engine.registry.register_tool(
        name="write_file",
        func=executed,
        schema={
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write a file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        requires_approval=True,
    )

    with patch.object(engine.router, "probe_intents", return_value=["write_file"]), patch.object(
        engine,
        "_post_request",
        return_value=tool_call_response(
            {"path": "config.txt", "content": "hello world"}
        ),
    ) as post_request:
        result = engine.step("Save hello world into config.txt.")

    assert result["status"] == "confirmation_required"
    assert result["pending_actions"] == [
        {
            "tool_name": "write_file",
            "args": {"path": "config.txt", "content": "hello world"},
            "reason": "Destructive or state-changing action requires confirmation.",
        }
    ]
    assert result["completed_observations"] == {}
    executed.assert_not_called()
    post_request.assert_called_once()
    assert engine.history == [
        {"role": "system", "content": "Fixed test system prompt."}
    ]
    print_gate_receipt(
        "INT-04",
        "HITL CIRCUIT BREAKER",
        "Destructive action halts before execution",
        extraction_payload_tools := post_request.call_args.args[0].get("tools"),
        result,
    )


def test_calculator_rejects_non_math_characters():
    registry = ToolRegistry()

    result = registry.execute("calculator", {"expression": "import os; os.system('dir')"})

    assert result.startswith("Refusal: Expression contains invalid characters.")
    print("\n[TEST GATE: INT-05 | DEFENSIVE CALCULATOR WHITELIST]")
    print("  - Scenario: Reject non-math characters in calculator input")
    print("  - Outbound Payload Schema Attached: None")
    print("  - Result: PASS (Status: refused, Tools: None)")


def test_observation_is_xml_formatted_and_not_saved_in_history(engine):
    synthesis_payloads = []

    def post_request(payload):
        if "tools" in payload:
            return tool_call_response({"expression": "453 * 18"})
        synthesis_payloads.append(payload)
        return ollama_message("453 multiplied by 18 equals 8154.")

    with patch.object(engine.router, "probe_intents", return_value=["calculator"]), patch.object(
        engine, "_post_request", side_effect=post_request
    ):
        result = engine.step("Calculate 453 * 18.")

    synthesis_messages = synthesis_payloads[0]["messages"]
    observation_tail = synthesis_messages[-1]["content"]
    assert "<observation>" in observation_tail
    assert "[VERIFIED DETERMINISTIC TOOL EXECUTION RESULTS]" in observation_tail
    assert "- calculator: 8154" in observation_tail
    assert "</observation>" in observation_tail
    assert synthesis_payloads[0].get("tools") is None
    assert "tools" not in synthesis_payloads[0]
    assert result == {
        "status": "completed",
        "response": "453 multiplied by 18 equals 8154.",
    }
    assert all("<observation>" not in message["content"] for message in engine.history)
    print_gate_receipt(
        "INT-03",
        "XML OBSERVATION HYGIENE",
        "Phase 3 observation is tail-injected and not persisted",
        synthesis_payloads[0].get("tools"),
        result,
    )


def test_router_parses_markdown_fenced_json_probe_response():
    fenced_response = ollama_message(
        "```json\n{\"required_tools\": [\"calculator\"]}\n```"
    )
    request = Mock()

    with patch("core.router.urllib.request.urlopen", return_value=FakeHTTPResponse(fenced_response)) as urlopen:
        result = IntentRouter(
            base_url="http://ollama.test/v1", model="test-model"
        ).probe_intents(
            [{"role": "assistant", "content": "The previous result was 4."}],
            "Can you use that previous result?",
        )

    assert result == ["calculator"]
    urlopen.assert_called_once()
    request = urlopen.call_args.args[0]
    payload = json.loads(request.data.decode("utf-8"))
    assert "format" not in payload
    assert payload["options"]["temperature"] == 0.0
    assert payload["options"]["num_predict"] == 100
    print("\n[TEST GATE: INT-06 | DEFENSIVE ROUTER JSON]")
    print("  - Scenario: Parse markdown-fenced intent probe JSON")
    print("  - Outbound Payload Schema Attached: Intent JSON format")
    print("  - Result: PASS (Status: completed, Tools: calculator)")


@pytest.mark.parametrize(
    "prompt",
    [
        "Write a C++ class to calculate delta time.",
        "Create a Python function that reports elapsed time.",
    ],
)
def test_router_does_not_poison_coding_prompts(prompt):
    result = IntentRouter().probe_intents([], prompt)
    assert result == []
    print("\n[TEST GATE: INT-07 | ANTI-TOOL POISONING]")
    print(f"  - Scenario: Coding prompt containing tool vocabulary ({prompt})")
    print("  - Outbound Payload Schema Attached: None")
    print("  - Result: PASS (Status: completed, Tools: None)")
