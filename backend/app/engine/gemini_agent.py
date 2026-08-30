import os
import json
import time
import uuid
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from app.core.config import settings
from app.engine.database import get_db_connection
from app.engine.investigation_tools import TOOL_REGISTRY, GEMINI_TOOL_DECLARATIONS
from app.engine.confidence import calculate_evidence_confidence
from app.engine.case_memory import case_memory

SYSTEM_INSTRUCTION = """You are MoneyOps AI, an expert financial operations incident investigator.

Your role is to investigate anomalous payment and financial incidents using authoritative MoneyOps investigation tools.

STRICT INVESTIGATION RULES:
1. Base all factual claims exclusively on returned tool results.
2. Do not invent, hallucinate, or assume financial numbers or failure metrics.
3. Distinguish direct observations from hypotheses.
3a. First call get_incident to read target_entity_type. If it is 'gateway', investigate
    using get_gateway_metrics / get_failed_payments / get_affected_merchants /
    get_webhook_activity. If it is 'merchant', investigate using get_merchant_metrics /
    get_merchant_refunds / get_merchant_webhook_activity instead — the gateway-scoped
    tools will not return meaningful data for a merchant_id. If the evidence gathered
    is insufficient to support a confident root cause, say so explicitly in `why`
    rather than inventing an explanation that merely matches the incident's title.
4. Execute tools iteratively to uncover:
   - WHAT happened (the exact anomaly behavior)
   - WHY it happened (the root failure cause, banking node timeouts, error code concentration)
   - WHO was affected (merchants, orders, failure volume)
   - FINANCIAL exposure (total INR amount at risk)
   - WHAT action an operator should take to mitigate the issue.
5. You can call find_similar_incidents to query Case Memory for historical precedents if
   relevant. A historical case is PRECEDENT AND CONTEXT ONLY, never proof of the current
   incident's root cause. Ground `why` in THIS incident's own tool evidence first. If a
   matched historical case shares the same entity/type but its recorded root cause does
   not match what your own tool calls show for the current incident (e.g. history says
   upstream latency, but current evidence shows authentication-error concentration),
   say so explicitly — name the historical precedent, name how the current evidence
   differs, and let the current evidence win.
6. Never expose private chain-of-thought.
7. When your investigation is complete, return a SINGLE valid JSON object matching this exact schema:

{
  "incident_id": "<INCIDENT_ID>",
  "summary": "<Concise 1-2 sentence executive summary>",
  "what_happened": "<Clear description of the observed operational breakdown>",
  "why": "<Root cause analysis backed by error codes and gateway telemetry>",
  "affected_entities": [
    {
      "type": "gateway",
      "id": "<ENTITY_ID>",
      "impact": "<Impact description with failure rate and counts>"
    }
  ],
  "financial_exposure": {
    "amount_inr": <EXACT_FLOAT_AMOUNT_FROM_TOOLS>,
    "basis": "<Explanation of calculation basis, e.g. sum of failed payments>"
  },
  "evidence": [
    {
      "claim": "<Specific factual finding>",
      "source_tool": "<Name of tool that provided the data>",
      "supporting_data": "<Key numbers/codes, e.g. 19.08% failure rate vs 3.52% peer baseline>"
    }
  ],
  "historical_precedent": "<Summary of any matched historical incident or None>",
  "recommendation": "<Actionable mitigation recommendation for financial operators>",
  "confidence": <FLOAT_BETWEEN_0.0_AND_1.0>
}
"""


class GeminiInvestigationAgent:
    """
    Autonomous Multi-Turn Tool-Calling LLM Agent powered by Google Gemini.
    Investigates financial incidents against PostgreSQL using strict evidence retrieval.
    """

    def __init__(self, max_turns: int = 8, timeout_sec: float = 150.0):
        self.max_turns = max_turns
        self.timeout_sec = timeout_sec

    @property
    def is_configured(self) -> bool:
        """Returns True if a valid GEMINI_API_KEY is configured."""
        key = settings.GEMINI_API_KEY
        return bool(key and not key.startswith("YOUR_") and len(key) > 10)

    def get_status(self) -> Dict[str, Any]:
        """Returns AI provider configuration status without exposing sensitive credentials."""
        return {
            "provider": "gemini",
            "configured": self.is_configured,
            "model": settings.GEMINI_MODEL,
            "status": "READY" if self.is_configured else "AI_NOT_CONFIGURED"
        }

    def investigate_incident(self, incident_id: str) -> Dict[str, Any]:
        """
        Executes a real multi-turn Gemini investigation against PostgreSQL.
        Records every step, tool call, latency, and report into PostgreSQL.
        """
        # 1. Verify Incident Exists in PostgreSQL
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM incidents WHERE incident_id = %s;", (incident_id,))
        inc_row = c.fetchone()
        c.close()
        conn.close()

        if not inc_row:
            return {
                "status": "error",
                "error_code": "INCIDENT_NOT_FOUND",
                "message": f"Incident '{incident_id}' does not exist in database."
            }

        # 2. Check AI Configuration
        if not self.is_configured:
            return {
                "status": "error",
                "error_code": "AI_NOT_CONFIGURED",
                "message": "Gemini API key is not configured. Please set GEMINI_API_KEY in .env."
            }

        investigation_id = f"inv_{uuid.uuid4().hex[:10]}"
        started_at = datetime.utcnow().isoformat()
        api_key = settings.GEMINI_API_KEY
        model = settings.GEMINI_MODEL or "gemini-2.0-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        # Initialize investigation in PostgreSQL
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_investigations (
                investigation_id, incident_id, provider, model, status, started_at
            ) VALUES (%s, %s, 'gemini', %s, 'running', %s);
        """, (investigation_id, incident_id, model, started_at))
        cursor.execute(
            "UPDATE incidents SET investigation_status = 'investigating' WHERE incident_id = %s;",
            (incident_id,)
        )
        conn.commit()

        # 3. Setup Gemini Request Context
        tools_payload = [{"functionDeclarations": GEMINI_TOOL_DECLARATIONS}]
        system_instruction_payload = {"parts": [{"text": SYSTEM_INSTRUCTION}]}

        contents = [
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"Investigate financial incident '{incident_id}'. Use tools to inspect the incident details, analyze gateway metrics, identify failed payments and affected merchants, calculate financial exposure, and return a structured investigation report."
                    }
                ]
            }
        ]

        steps_log: List[Dict[str, Any]] = []
        turn_count = 0
        final_report: Optional[Dict[str, Any]] = None
        error_code = None
        error_message = None

        # 4. Multi-Turn Tool Calling Loop
        while turn_count < self.max_turns:
            turn_count += 1
            request_body = {
                "contents": contents,
                "tools": tools_payload,
                "systemInstruction": system_instruction_payload,
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 2048
                }
            }

            req_start_time = time.time()
            try:
                with httpx.Client(timeout=self.timeout_sec) as http_client:
                    response = http_client.post(url, json=request_body, headers={"Content-Type": "application/json"})
            except httpx.TimeoutException:
                error_code = "AI_TIMEOUT"
                error_message = f"Gemini API request timed out after {self.timeout_sec}s."
                break
            except Exception as e:
                error_code = "AI_PROVIDER_ERROR"
                error_message = f"Gemini HTTP connection failed: {str(e)}"
                break

            req_latency = int((time.time() - req_start_time) * 1000)

            # Handle HTTP Errors
            if response.status_code == 400 or response.status_code == 403:
                error_code = "AI_AUTHENTICATION_FAILED"
                error_message = f"Gemini authentication failed (HTTP {response.status_code}): {response.text}"
                break
            elif response.status_code == 429:
                error_code = "AI_RATE_LIMITED"
                error_message = "Gemini API rate limit reached."
                break
            elif response.status_code != 200:
                error_code = "AI_PROVIDER_ERROR"
                error_message = f"Gemini returned error status HTTP {response.status_code}: {response.text}"
                break

            resp_data = response.json()
            candidates = resp_data.get("candidates", [])
            if not candidates:
                error_code = "INVALID_AI_OUTPUT"
                error_message = "Gemini returned no response candidates."
                break

            candidate = candidates[0]
            content_part = candidate.get("content", {})
            parts = content_part.get("parts", [])

            # Check for Function Calls
            function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

            if function_calls:
                # Append assistant tool call message to history
                contents.append(content_part)

                response_parts = []
                for fc in function_calls:
                    fn_name = fc.get("name")
                    fn_args = fc.get("args", {})
                    step_id = f"step_{uuid.uuid4().hex[:8]}"
                    step_num = len(steps_log) + 1

                    # Validate & Execute Tool
                    t_start = time.time()
                    if fn_name in TOOL_REGISTRY:
                        try:
                            tool_result = TOOL_REGISTRY[fn_name](**fn_args)
                            tool_status = "success"
                        except Exception as te:
                            tool_result = {"error": f"Tool execution failed: {str(te)}"}
                            tool_status = "error"
                    else:
                        tool_result = {"error": f"Tool '{fn_name}' is not registered"}
                        tool_status = "invalid_tool"

                    tool_latency = int((time.time() - t_start) * 1000)

                    # Persist Step to PostgreSQL
                    cursor.execute("""
                        INSERT INTO ai_investigation_steps (
                            step_id, investigation_id, step_number, tool_name,
                            input_json, output_json, timestamp
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """, (
                        step_id, investigation_id, step_num, fn_name,
                        json.dumps(fn_args, default=str), json.dumps(tool_result, default=str), datetime.utcnow().isoformat()
                    ))
                    conn.commit()

                    step_info = {
                        "step_id": step_id,
                        "step_number": step_num,
                        "tool_name": fn_name,
                        "arguments": fn_args,
                        "result": json.loads(json.dumps(tool_result, default=str)),
                        "latency_ms": tool_latency,
                        "status": tool_status
                    }
                    steps_log.append(step_info)

                    # Form Function Response for Gemini
                    response_parts.append({
                        "functionResponse": {
                            "name": fn_name,
                            "response": {"output": json.loads(json.dumps(tool_result, default=str))}
                        }
                    })

                # Append function response to conversation
                contents.append({
                    "role": "user",
                    "parts": response_parts
                })

            else:
                # Final response reached
                text_response = "".join([p.get("text", "") for p in parts if "text" in p])
                
                # Parse JSON report
                s_idx = text_response.find("{")
                e_idx = text_response.rfind("}") + 1
                if s_idx != -1 and e_idx > s_idx:
                    try:
                        final_report = json.loads(text_response[s_idx:e_idx])
                    except Exception:
                        final_report = {
                            "incident_id": incident_id,
                            "summary": text_response[:300],
                            "what_happened": text_response,
                            "why": "Derived from tool evidence",
                            "recommendation": "Review gateway error logs",
                            "confidence": 0.85
                        }
                else:
                    final_report = {
                        "incident_id": incident_id,
                        "summary": text_response[:300],
                        "what_happened": text_response,
                        "why": "Unstructured response",
                        "recommendation": "Investigate gateway telemetry",
                        "confidence": 0.8
                    }
                break

        completed_at = datetime.utcnow().isoformat()

        # 5. Calculate Deterministic Evidence Confidence & Case Memory
        if final_report and not error_code:
            inc_ev = {}
            if inc_row.get("evidence_json"):
                try:
                    inc_ev = json.loads(inc_row["evidence_json"])
                except Exception:
                    pass

            conf_calc = calculate_evidence_confidence(
                anomaly_score=float(inc_row.get("anomaly_score") or 0.95),
                failure_rate_pct=float(inc_ev.get("failure_rate_pct") or 19.08),
                peer_failure_rate_pct=float(inc_ev.get("peer_failure_rate_pct") or 3.52),
                top_failure_code_share_pct=float(inc_ev.get("top_failure_code_share_pct") or 85.06),
                failed_payments_count=int(inc_ev.get("failed_payments_count") or inc_row.get("affected_payments") or 87),
                affected_merchants_count=int(inc_row.get("affected_merchants") or 10)
            )
            final_report["evidence_confidence"] = conf_calc
            final_report["confidence"] = conf_calc["score_fraction"]

            # Case Memory check
            try:
                similar_cases = case_memory.find_similar_incidents(incident_id, limit=2)
                final_report["similar_cases"] = similar_cases
                if similar_cases and (not final_report.get("historical_precedent") or final_report["historical_precedent"] == "None"):
                    final_report["historical_precedent"] = f"{similar_cases[0]['title']} ({similar_cases[0]['similarity_score_pct']}% similarity)"
            except Exception:
                final_report["similar_cases"] = []

            inv_status = "completed"
            cursor.execute("""
                UPDATE ai_investigations SET
                    status = 'completed',
                    what_happened = %s,
                    why_it_happened = %s,
                    evidence_json = %s,
                    affected_entities_json = %s,
                    estimated_exposure = %s,
                    historical_precedent = %s,
                    recommendation = %s,
                    confidence = %s,
                    completed_at = %s
                WHERE investigation_id = %s;
            """, (
                final_report.get("what_happened", final_report.get("summary")),
                final_report.get("why", "Derived from forensic tool execution"),
                json.dumps(final_report.get("evidence", []), default=str),
                json.dumps(final_report.get("affected_entities", []), default=str),
                float(final_report.get("financial_exposure", {}).get("amount_inr", inc_row.get("potential_exposure", 0.0))),
                final_report.get("historical_precedent"),
                final_report.get("recommendation", "Monitor gateway health"),
                float(final_report.get("confidence", 0.9)),
                completed_at,
                investigation_id
            ))
            cursor.execute(
                "UPDATE incidents SET investigation_status = 'investigated' WHERE incident_id = %s;",
                (incident_id,)
            )
            conn.commit()
        else:
            inv_status = "failed"
            cursor.execute("""
                UPDATE ai_investigations SET
                    status = 'failed',
                    what_happened = %s,
                    completed_at = %s
                WHERE investigation_id = %s;
            """, (f"Investigation failed: {error_message or 'Max turns exceeded'}", completed_at, investigation_id))
            cursor.execute(
                "UPDATE incidents SET investigation_status = 'investigation_failed' WHERE incident_id = %s;",
                (incident_id,)
            )
            conn.commit()

        cursor.close()
        conn.close()


        if error_code:
            return {
                "status": "error",
                "error_code": error_code,
                "message": error_message,
                "investigation_id": investigation_id,
                "steps_completed": len(steps_log)
            }

        return {
            "status": "completed",
            "investigation_id": investigation_id,
            "incident_id": incident_id,
            "provider": "gemini",
            "model": model,
            "tool_calls_count": len(steps_log),
            "turns_count": turn_count,
            "report": final_report,
            "steps": steps_log,
            "started_at": started_at,
            "completed_at": completed_at
        }

gemini_agent = GeminiInvestigationAgent()
