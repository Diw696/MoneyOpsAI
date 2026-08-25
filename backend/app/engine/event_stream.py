import asyncio
import json
from datetime import datetime
from typing import Dict, Any
from app.engine.database import get_db_connection
from app.engine.event_pipeline import event_pipeline

class EventStreamEngine:
    """
    Lean event-driven processing pipeline using asyncio.Queue.
    Ingests payment stream events, routes through canonical pipeline stages,
    and returns database-derived operational telemetry.
    """

    def __init__(self):
        self.queue = asyncio.Queue()
        self.is_running = False
        self.worker_task = None

    async def start(self):
        if not self.is_running:
            self.is_running = True
            self.worker_task = asyncio.create_task(self._process_queue())

    async def stop(self):
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()

    async def push_event(self, event_type: str, payload: Dict[str, Any], source: str = "synthetic"):
        """Pushes a financial event into the stream queue."""
        await self.queue.put({
            "event_type": event_type,
            "payload": payload,
            "source": source,
            "received_at": datetime.utcnow().isoformat()
        })

    async def _process_queue(self):
        """Worker loop continuously popping and processing events via canonical pipeline."""
        while self.is_running:
            try:
                item = await self.queue.get()
                event_pipeline.process_event(
                    raw_event_type=item["event_type"],
                    raw_payload=item["payload"],
                    source=item.get("source", "synthetic")
                )
                self.queue.task_done()
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error processing stream event: {e}")
                await asyncio.sleep(0.1)

    def get_stats(self) -> Dict[str, Any]:
        """
        Calculates operational telemetry directly from SQLite tables.
        Zero hardcoded counters.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # Count total canonical events + payment webhooks
        cursor.execute("SELECT COUNT(*) as total FROM canonical_events")
        can_count = cursor.fetchone()["total"] or 0

        cursor.execute("SELECT COUNT(*) as total_anomalies FROM canonical_events WHERE is_anomaly = 1")
        anom_count = cursor.fetchone()["total_anomalies"] or 0

        cursor.execute("""
            SELECT 
                COUNT(*) as active_incidents,
                SUM(potential_exposure) as pot_exp,
                SUM(recoverable_exposure) as rec_exp
            FROM incidents 
            WHERE status != 'resolved'
        """)
        inc_stats = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) as total_audit FROM audit_logs")
        audit_count = cursor.fetchone()["total_audit"] or 0

        conn.close()

        return {
            "events_processed": can_count,
            "active_incidents": inc_stats["active_incidents"] or 0,
            "anomalies_detected": anom_count,
            "potential_exposure": inc_stats["pot_exp"] or 0.0,
            "recoverable_exposure": inc_stats["rec_exp"] or 0.0,
            "audited_actions_count": audit_count,
            "queue_depth": self.queue.qsize(),
            "stream_status": "streaming" if self.is_running else "ready"
        }

event_stream = EventStreamEngine()
