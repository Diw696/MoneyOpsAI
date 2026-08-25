import sys
import argparse
from app.engine.agent import investigation_agent

def run_cli_investigation(incident_id: str):
    print("=" * 60)
    print(f" MONEYOPS AI — CLI INCIDENT INVESTIGATOR: {incident_id}")
    print("=" * 60)
    
    report = investigation_agent.investigate(incident_id)

    print(f"Investigation ID: {report.investigation_id}")
    print(f"Incident:         {report.incident_id} ({report.incident_type})")
    print(f"Severity:         {report.severity.upper()}")
    print(f"Confidence:       {report.confidence*100:.1f}%")
    print(f"Exposure:         INR {report.financial_exposure:,.2f}")
    print(f"Affected Scope:   {report.affected_merchants_count} merchants, {report.affected_transactions_count} transactions")
    print("-" * 60)
    print("AGENT REASONING STEPS:")
    for step in report.agent_steps:
        print(f"  Step {step.step_number}: {step.title}")
        print(f"    Tool: {step.tool_name}")
        print(f"    Description: {step.description}")
    print("-" * 60)
    print("ROOT CAUSE ANALYSIS:")
    print(f"  {report.root_cause}")
    print(f"  Hypothesis: {report.root_cause_hypothesis}")
    print("-" * 60)
    print("GOVERNED ACTION:")
    print(f"  Action:            {report.action_name}")
    print(f"  Tier:              {report.action_tier.value.upper()}")
    print(f"  Requires Approval: {report.requires_approval}")
    print(f"  Recommendation:    {report.recommended_action}")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Investigate an incident via MoneyOps AI agent.")
    parser.add_argument("incident_id", type=str, default="INC-2841", nargs="?", help="Incident ID (e.g. INC-2841)")
    args = parser.parse_args()
    run_cli_investigation(args.incident_id)
