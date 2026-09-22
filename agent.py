"""
E:\AI_Hub\agents\agent.py
Modular Local AI Agent CLI Runner with HITL Circuit Breaker
"""
import sys
import argparse
from core.engine import AgentEngine
from personalities.general_cousin import SYSTEM_PROMPT, MODEL_NAME, CONTEXT_WINDOW

def main():
    parser = argparse.ArgumentParser(description="Local Agentic Orchestrator")
    parser.add_argument("--cli", action="store_true", help="Launch in Interactive CLI mode")
    args = parser.parse_args()

    print("============================================================")
    print(f"  Local AI Agent ({MODEL_NAME})")
    print("  Engine: Guarded Hybrid Dispatch | HITL: Active")
    print("  Type 'exit' or 'quit' to stop.")
    print("============================================================")

    engine = AgentEngine(
        model=MODEL_NAME,
        system_prompt=SYSTEM_PROMPT,
        context_window=CONTEXT_WINDOW
    )

    if args.cli or len(sys.argv) == 1:
        while True:
            try:
                user_input = input("\nUser > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit"]:
                    print("Exiting local agent session.")
                    break

                result = engine.step(user_input)

                if result["status"] == "confirmation_required":
                    print("\n[SAFETY CIRCUIT BREAKER TRIGGERED]")
                    print("The following actions require explicit user confirmation:")
                    for action in result["pending_actions"]:
                        print(f"  - Tool: `{action['tool_name']}` | Args: {action['args']}")
                        print(f"    Reason: {action['reason']}")

                    confirm = input("\nDo you authorize these actions? [y/N]: ").strip().lower()
                    if confirm == 'y':
                        for action in result["pending_actions"]:
                            res = engine.registry.execute(action["tool_name"], action["args"])
                            result["completed_observations"][action["tool_name"]] = res

                        final_response = engine._synthesize_with_observations(user_input, result["completed_observations"])
                        engine.history.append({"role": "user", "content": user_input})
                        engine.history.append({"role": "assistant", "content": final_response})
                        print(f"\nAgent > {final_response}")
                    else:
                        print("Actions denied by user. Step aborted.")
                else:
                    print(f"Agent > {result['response']}")

            except KeyboardInterrupt:
                print("\nSession interrupted.")
                break

if __name__ == "__main__":
    main()