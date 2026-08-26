import sys
import json
import argparse
from app.core.config import settings
from app.engine.gemini_agent import gemini_agent
from app.engine.investigation_tools import InvestigationTools

def main():
    parser = argparse.ArgumentParser(description="MoneyOps AI — Autonomous Incident Investigator")
    parser.add_argument("--incident", type=str, default="INC-0001", help="Incident ID to investigate")
    args = parser.parse_args()

    print("=" * 68)
    print(" MONEYOPS AI V2 — AUTONOMOUS GEMINI INVESTIGATION ENGINE")
    print("=" * 68)

    status = gemini_agent.get_status()
    print(f"Provider Configured : {status['configured']} ({status['provider'].upper()})")
    print(f"Model Target        : {status['model']}")
    print(f"Incident Target     : {args.incident}\n")

    if not status["configured"]:
        print("[NOTICE] GEMINI_API_KEY is not configured in .env.")
        print("   The system will strictly NOT fabricate a fake AI report.")
        print("   Please set GEMINI_API_KEY in your .env file to enable live cloud LLM investigations.\n")
        print("   Local Tool Registry is testable directly against PostgreSQL:")
        gw_metrics = InvestigationTools.get_gateway_metrics("Gateway_X")
        print(f"   [Tool Direct Test] get_gateway_metrics('Gateway_X'):")
        print(f"     - Failure Rate : {gw_metrics.get('failure_rate_pct')}%")
        print(f"     - Peer Average : {gw_metrics.get('peer_failure_rate_pct')}%")
        print(f"     - Top Error    : {gw_metrics.get('failure_code_breakdown', [{}])[0].get('failure_code')}")
        print("=" * 68)
        return

    print(f"Starting Multi-Turn Gemini Investigation on {args.incident}...")
    res = gemini_agent.investigate_incident(args.incident)

    if res.get("status") == "error":
        print(f"\n[ERROR] Investigation Error: [{res.get('error_code')}] {res.get('message')}")
        return

    print(f"\n[SUCCESS] Investigation Completed in {res.get('turns_count')} turns ({res.get('tool_calls_count')} tool calls).")
    print(f"Investigation ID : {res.get('investigation_id')}")

    print("\n--- Investigation Execution Trace (Tool Calling Steps) ---")
    for st in res.get("steps", []):
        print(f"  Step {st['step_number']}: Gemini → {st['tool_name']}({json.dumps(st['arguments'])}) [{st['latency_ms']}ms]")

    report = res.get("report", {})
    print("\n--- Final Structured Investigation Findings ---")
    print(f"Summary         : {report.get('summary')}")
    print(f"What Happened   : {report.get('what_happened')}")
    print(f"Root Cause (Why): {report.get('why')}")
    print(f"Recommendation  : {report.get('recommendation')}")
    print(f"Confidence      : {report.get('confidence')}")

    print("\n" + "=" * 68)

if __name__ == "__main__":
    main()
