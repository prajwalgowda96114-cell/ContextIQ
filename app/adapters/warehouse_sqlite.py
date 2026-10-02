"""SQLite database warehouse adapter for local mode."""
import json
import pathlib
import sqlite3
import sys

try:
    from app.models import (
        AuditEvent,
        Decision,
        Fact,
        Feedback,
        Incident,
        InputItem,
        PastCase,
        PriorityEnum,
        StatusEnum,
    )
except ImportError:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    from app.models import (
        AuditEvent,
        Decision,
        Fact,
        Feedback,
        Incident,
        InputItem,
        PastCase,
        PriorityEnum,
        StatusEnum,
    )

DB_PATH = pathlib.Path(__file__).resolve().parents[2] / "data" / "contextiq.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class WarehouseSQLite:
    def __init__(self, db_file: pathlib.Path = DB_PATH):
        self.db_file = db_file
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                created_at TEXT,
                zone TEXT,
                status TEXT,
                priority TEXT,
                title TEXT,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS inputs (
                input_id TEXT PRIMARY KEY,
                incident_id TEXT,
                modality TEXT,
                uri TEXT,
                filename TEXT,
                bytes_sha256 TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS facts (
                fact_id TEXT PRIMARY KEY,
                incident_id TEXT,
                input_id TEXT,
                modality TEXT,
                claim TEXT,
                evidence_pointer TEXT,
                zone TEXT,
                hazard TEXT,
                severity TEXT,
                affected_people TEXT,
                confidence REAL,
                observable INTEGER
            );

            CREATE TABLE IF NOT EXISTS conflicts (
                conflict_id TEXT PRIMARY KEY,
                incident_id TEXT,
                fact_ids TEXT,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                incident_id TEXT,
                version INTEGER,
                priority TEXT,
                recommended_action TEXT,
                reasons TEXT,
                confidence REAL,
                confidence_breakdown TEXT,
                review_required INTEGER,
                review_reason TEXT,
                backends TEXT,
                latency_ms TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS past_cases (
                case_id TEXT PRIMARY KEY,
                summary TEXT,
                zone TEXT,
                hazard TEXT,
                outcome TEXT,
                lessons TEXT
            );

            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id TEXT PRIMARY KEY,
                decision_id TEXT,
                incident_id TEXT,
                officer_action TEXT,
                reason TEXT,
                new_priority TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                ts TEXT,
                request_id TEXT,
                incident_id TEXT,
                stage TEXT,
                backend TEXT,
                detail TEXT
            );
            """)

    def save_incident(self, incident: Incident):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO incidents (incident_id, created_at, zone, status, priority, title, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(incident_id) DO UPDATE SET
                   zone=excluded.zone, status=excluded.status, priority=excluded.priority,
                   title=excluded.title, description=excluded.description""",
                (incident.incident_id, incident.created_at, incident.zone, incident.status.value,
                 incident.priority.value, incident.title, incident.description)
            )

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
            if not row:
                return None
            return Incident(
                incident_id=row["incident_id"],
                created_at=row["created_at"],
                zone=row["zone"],
                status=StatusEnum(row["status"]),
                priority=PriorityEnum(row["priority"]),
                title=row["title"],
                description=row["description"]
            )

    def list_incidents(self) -> list[Incident]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM incidents ORDER BY created_at DESC").fetchall()
            return [
                Incident(
                    incident_id=r["incident_id"],
                    created_at=r["created_at"],
                    zone=r["zone"],
                    status=StatusEnum(r["status"]),
                    priority=PriorityEnum(r["priority"]),
                    title=r["title"],
                    description=r["description"]
                ) for r in rows
            ]

    def save_input(self, item: InputItem):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO inputs (input_id, incident_id, modality, uri, filename, bytes_sha256, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (item.input_id, item.incident_id, item.modality.value, item.uri, item.filename, item.bytes_sha256, item.created_at)
            )

    def get_inputs_for_incident(self, incident_id: str) -> list[InputItem]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM inputs WHERE incident_id = ?", (incident_id,)).fetchall()
            return [
                InputItem(
                    input_id=r["input_id"],
                    incident_id=r["incident_id"],
                    modality=r["modality"],
                    uri=r["uri"],
                    filename=r["filename"],
                    bytes_sha256=r["bytes_sha256"],
                    created_at=r["created_at"]
                ) for r in rows
            ]

    def save_facts(self, facts: list[Fact]):
        with self._get_conn() as conn:
            for f in facts:
                conn.execute(
                    """INSERT OR REPLACE INTO facts
                       (fact_id, incident_id, input_id, modality, claim, evidence_pointer, zone, hazard, severity, affected_people, confidence, observable)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (f.fact_id, f.incident_id, f.input_id, f.modality.value, f.claim, f.evidence_pointer,
                     f.zone, f.hazard, str(f.severity), str(f.affected_people), f.confidence, 1 if f.observable else 0)
                )

    def get_facts_for_incident(self, incident_id: str) -> list[Fact]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM facts WHERE incident_id = ?", (incident_id,)).fetchall()
            return [
                Fact(
                    fact_id=r["fact_id"],
                    incident_id=r["incident_id"],
                    input_id=r["input_id"],
                    modality=r["modality"],
                    claim=r["claim"],
                    evidence_pointer=r["evidence_pointer"],
                    zone=r["zone"],
                    hazard=r["hazard"],
                    severity=r["severity"],
                    affected_people=r["affected_people"],
                    confidence=r["confidence"],
                    observable=bool(r["observable"])
                ) for r in rows
            ]

    def save_decision(self, decision: Decision):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO decisions
                   (decision_id, incident_id, version, priority, recommended_action, reasons, confidence, confidence_breakdown, review_required, review_reason, backends, latency_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision.decision_id, decision.incident_id, decision.version, decision.priority.value,
                    decision.recommended_action, json.dumps([r.model_dump() for r in decision.reasons]),
                    decision.confidence, json.dumps(decision.confidence_breakdown.model_dump()),
                    1 if decision.review_required else 0, decision.review_reason,
                    json.dumps(decision.backends), json.dumps(decision.latency_ms), decision.created_at
                )
            )

    def get_latest_decision(self, incident_id: str) -> Decision | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM decisions WHERE incident_id = ? ORDER BY version DESC LIMIT 1", (incident_id,)).fetchone()
            if not row:
                return None
            return Decision(
                decision_id=row["decision_id"],
                incident_id=row["incident_id"],
                version=row["version"],
                priority=PriorityEnum(row["priority"]),
                recommended_action=row["recommended_action"],
                reasons=json.loads(row["reasons"]),
                confidence=row["confidence"],
                confidence_breakdown=json.loads(row["confidence_breakdown"]),
                review_required=bool(row["review_required"]),
                review_reason=row["review_reason"],
                backends=json.loads(row["backends"]),
                latency_ms=json.loads(row["latency_ms"]),
                created_at=row["created_at"]
            )

    def get_decisions_for_incident(self, incident_id: str) -> list[Decision]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM decisions WHERE incident_id = ? ORDER BY version ASC", (incident_id,)).fetchall()
            return [
                Decision(
                    decision_id=r["decision_id"],
                    incident_id=r["incident_id"],
                    version=r["version"],
                    priority=PriorityEnum(r["priority"]),
                    recommended_action=r["recommended_action"],
                    reasons=json.loads(r["reasons"]),
                    confidence=r["confidence"],
                    confidence_breakdown=json.loads(r["confidence_breakdown"]),
                    review_required=bool(r["review_required"]),
                    review_reason=r["review_reason"],
                    backends=json.loads(r["backends"]),
                    latency_ms=json.loads(r["latency_ms"]),
                    created_at=r["created_at"]
                ) for r in rows
            ]

    def save_past_case(self, case: PastCase):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO past_cases (case_id, summary, zone, hazard, outcome, lessons)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (case.case_id, case.summary, case.zone, case.hazard, case.outcome, case.lessons)
            )

    def list_past_cases(self) -> list[PastCase]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM past_cases").fetchall()
            return [
                PastCase(
                    case_id=r["case_id"],
                    summary=r["summary"],
                    zone=r["zone"],
                    hazard=r["hazard"],
                    outcome=r["outcome"],
                    lessons=r["lessons"]
                ) for r in rows
            ]

    def save_feedback(self, fb: Feedback):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO feedback (feedback_id, decision_id, incident_id, officer_action, reason, new_priority, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (fb.feedback_id, fb.decision_id, fb.incident_id, fb.officer_action, fb.reason, fb.new_priority.value if fb.new_priority else None, fb.created_at)
            )

    def save_audit_event(self, event: AuditEvent):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO audit_events (event_id, ts, request_id, incident_id, stage, backend, detail)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event.event_id, event.ts, event.request_id, event.incident_id, event.stage, event.backend, event.detail)
            )

    def get_audit_events_for_incident(self, incident_id: str) -> list[AuditEvent]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM audit_events WHERE incident_id = ? ORDER BY ts ASC", (incident_id,)).fetchall()
            return [
                AuditEvent(
                    event_id=r["event_id"],
                    ts=r["ts"],
                    request_id=r["request_id"],
                    incident_id=r["incident_id"],
                    stage=r["stage"],
                    backend=r["backend"],
                    detail=r["detail"]
                ) for r in rows
            ]
