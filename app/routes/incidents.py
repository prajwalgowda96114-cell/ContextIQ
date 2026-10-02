"""FastAPI router for Incidents, Ingestion, Feedback, and SSE streaming."""
import pathlib
import sys
import uuid

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from app.adapters.bus_local import BusLocal
    from app.adapters.retriever_local import RetrieverNumpy
    from app.adapters.storage_local import StorageLocal
    from app.adapters.warehouse_sqlite import WarehouseSQLite
    from app.llm import LLMClient
    from app.models import (
        AuditEvent,
        Feedback,
        Incident,
        InputItem,
        ModalityEnum,
        PriorityEnum,
        StatusEnum,
    )
    from app.pipeline import PipelineEngine
except ImportError:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    from app.adapters.bus_local import BusLocal
    from app.adapters.retriever_local import RetrieverNumpy
    from app.adapters.storage_local import StorageLocal
    from app.adapters.warehouse_sqlite import WarehouseSQLite
    from app.llm import LLMClient
    from app.models import (
        AuditEvent,
        Feedback,
        Incident,
        InputItem,
        ModalityEnum,
        PriorityEnum,
        StatusEnum,
    )
    from app.pipeline import PipelineEngine

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

# Initialize singleton components
storage_adapter = StorageLocal()
bus_adapter = BusLocal()
warehouse_adapter = WarehouseSQLite()
retriever_adapter = RetrieverNumpy()
llm_client = LLMClient()

pipeline_engine = PipelineEngine(
    storage=storage_adapter,
    bus=bus_adapter,
    warehouse=warehouse_adapter,
    retriever=retriever_adapter,
    llm=llm_client
)


class IncidentCreateSchema(BaseModel):
    title: str = "New Emergency Incident"
    description: str = ""
    zone: str = "Unknown"


class FeedbackSchema(BaseModel):
    decision_id: str
    officer_action: str  # "approve" | "override"
    reason: str
    new_priority: str | None = None


@router.get("")
def list_incidents():
    incidents = warehouse_adapter.list_incidents()
    results = []
    for inc in incidents:
        dec = warehouse_adapter.get_latest_decision(inc.incident_id)
        results.append({
            "incident_id": inc.incident_id,
            "title": inc.title,
            "zone": inc.zone,
            "status": inc.status.value,
            "priority": (dec.priority.value if dec else inc.priority.value),
            "confidence": (dec.confidence if dec else None),
            "review_required": (dec.review_required if dec else False),
            "created_at": inc.created_at
        })
    return results


@router.post("")
def create_incident(data: IncidentCreateSchema):
    incident_id = f"INC-2026-{str(uuid.uuid4().int)[:4]}"
    inc = Incident(
        incident_id=incident_id,
        title=data.title,
        description=data.description,
        zone=data.zone,
        status=StatusEnum.PROCESSING
    )
    warehouse_adapter.save_incident(inc)
    return inc.model_dump()


@router.get("/{incident_id}")
def get_incident_detail(incident_id: str):
    inc = warehouse_adapter.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    inputs = warehouse_adapter.get_inputs_for_incident(incident_id)
    facts = warehouse_adapter.get_facts_for_incident(incident_id)
    decisions = warehouse_adapter.get_decisions_for_incident(incident_id)
    audit_events = warehouse_adapter.get_audit_events_for_incident(incident_id)
    query_text = inc.zone + " " + " ".join([f.claim for f in facts[:3]])
    past_cases = retriever_adapter.search(query_text, zone=inc.zone, top_k=5)

    return {
        "incident": inc.model_dump(),
        "inputs": [i.model_dump() for i in inputs],
        "facts": [f.model_dump() for f in facts],
        "decisions": [d.model_dump() for d in decisions],
        "latest_decision": (decisions[-1].model_dump() if decisions else None),
        "past_cases": [c.model_dump() for c in past_cases],
        "audit_events": [a.model_dump() for a in audit_events]
    }


@router.post("/{incident_id}/inputs")
async def add_input_item(
    incident_id: str,
    background_tasks: BackgroundTasks,
    modality: str = Form(...),
    text_content: str | None = Form(None),
    file: UploadFile | None = File(None)
):
    inc = warehouse_adapter.get_incident(incident_id)
    if not inc:
        # Auto-create incident if not existing
        inc = Incident(incident_id=incident_id, title=f"Incident {incident_id}")
        warehouse_adapter.save_incident(inc)

    if modality not in ["text", "image", "pdf"]:
        raise HTTPException(status_code=400, detail="Modality must be text, image, or pdf")

    input_id = f"inp_{modality}_{uuid.uuid4().hex[:6]}"
    filename = f"{modality}_input.txt" if modality == "text" else (file.filename if file else f"{modality}_input")

    if modality == "text":
        content_bytes = (text_content or "").encode("utf-8")
    else:
        if not file:
            raise HTTPException(status_code=400, detail="File is required for image/pdf modality")
        content_bytes = await file.read()

    # Save raw file via storage adapter
    uri, sha256 = await storage_adapter.save_file(incident_id, filename, content_bytes)

    input_item = InputItem(
        input_id=input_id,
        incident_id=incident_id,
        modality=ModalityEnum(modality),
        uri=uri,
        filename=filename,
        bytes_sha256=sha256
    )
    warehouse_adapter.save_input(input_item)

    # Launch pipeline re-evaluation in background task
    background_tasks.add_task(pipeline_engine.run_pipeline, incident_id)

    return {
        "status": "queued",
        "input_item": input_item.model_dump()
    }


@router.get("/{incident_id}/stream")
async def stream_incident_events(incident_id: str):
    """SSE endpoint delivering live stage updates."""
    return StreamingResponse(
        bus_adapter.event_generator(incident_id),
        media_type="text/event-stream"
    )


@router.post("/{incident_id}/feedback")
def submit_officer_feedback(incident_id: str, fb: FeedbackSchema):
    inc = warehouse_adapter.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    fb_id = f"fb_{uuid.uuid4().hex[:6]}"
    feedback = Feedback(
        feedback_id=fb_id,
        decision_id=fb.decision_id,
        incident_id=incident_id,
        officer_action=fb.officer_action,
        reason=fb.reason,
        new_priority=PriorityEnum[fb.new_priority] if fb.new_priority else None
    )
    warehouse_adapter.save_feedback(feedback)

    # Update incident status
    inc.status = StatusEnum.REVIEWED
    if fb.new_priority and fb.new_priority in PriorityEnum.__members__:
        inc.priority = PriorityEnum[fb.new_priority]
    warehouse_adapter.save_incident(inc)

    # Log audit event
    warehouse_adapter.save_audit_event(AuditEvent(
        event_id=f"audit_{uuid.uuid4().hex[:8]}",
        request_id="officer_review",
        incident_id=incident_id,
        stage="human_review",
        backend="officer",
        detail=f"Officer action={fb.officer_action}, reason='{fb.reason}'"
    ))

    return {"status": "success", "feedback": feedback.model_dump()}
