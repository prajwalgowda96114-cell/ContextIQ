"""5-Stage Incident Processing Pipeline for ContextIQ with SSE streaming."""
import asyncio
import os
import pathlib
import sys
import time
import uuid

try:
    from app.adapters.bus_local import BusLocal
    from app.adapters.retriever_local import RetrieverNumpy
    from app.adapters.storage_local import StorageLocal
    from app.adapters.warehouse_sqlite import WarehouseSQLite
    from app.confidence import ConfidenceEngine
    from app.llm import LLMClient
    from app.models import (
        AuditEvent,
        Conflict,
        Decision,
        Fact,
        Incident,
        InputItem,
        PriorityEnum,
        ReasonItem,
        StatusEnum,
    )
    from app.verifier import Verifier
except ImportError:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from app.adapters.bus_local import BusLocal
    from app.adapters.retriever_local import RetrieverNumpy
    from app.adapters.storage_local import StorageLocal
    from app.adapters.warehouse_sqlite import WarehouseSQLite
    from app.confidence import ConfidenceEngine
    from app.llm import LLMClient
    from app.models import (
        AuditEvent,
        Conflict,
        Decision,
        Fact,
        Incident,
        InputItem,
        PriorityEnum,
        ReasonItem,
        StatusEnum,
    )
    from app.verifier import Verifier


class PipelineEngine:
    def __init__(
        self,
        storage: StorageLocal,
        bus: BusLocal,
        warehouse: WarehouseSQLite,
        retriever: RetrieverNumpy,
        llm: LLMClient
    ):
        self.storage = storage
        self.bus = bus
        self.warehouse = warehouse
        self.retriever = retriever
        self.llm = llm

    async def run_pipeline(self, incident_id: str, request_id: str = "") -> Decision:
        start_time = time.time()
        latency_ms = {}
        backends = {
            "storage": "local:fs" if os.getenv("MODE") != "gcp" else "gcp:gcs",
            "bus": "local:asyncio_queue" if os.getenv("MODE") != "gcp" else "gcp:pubsub",
            "warehouse": "local:sqlite" if os.getenv("MODE") != "gcp" else "gcp:bigquery",
            "retriever": "local:numpy_cosine" if os.getenv("MODE") != "gcp" else "gcp:vectorsearch",
            "llm": f"genai:{self.llm.decide_model}" if os.getenv("MODE") != "gcp" else f"vertexai:{self.llm.decide_model}"
        }

        request_id = request_id or str(uuid.uuid4())[:8]

        # Fetch incident & existing inputs from warehouse
        incident = self.warehouse.get_incident(incident_id)
        if not incident:
            incident = Incident(incident_id=incident_id, title=f"Incident {incident_id}")
            self.warehouse.save_incident(incident)

        inputs = self.warehouse.get_inputs_for_incident(incident_id)

        # -------------------------------------------------------------
        # STAGE 1: INGESTING
        # -------------------------------------------------------------
        t0 = time.time()
        await self.bus.publish(incident_id, {
            "incident_id": incident_id,
            "stage": "Ingesting",
            "status": "start",
            "ms": 0,
            "backend": backends["storage"],
            "payload": {"input_count": len(inputs)}
        })
        await asyncio.sleep(0.05)
        ms_ingest = int((time.time() - t0) * 1000)
        latency_ms["ingest"] = ms_ingest

        await self.bus.publish(incident_id, {
            "incident_id": incident_id,
            "stage": "Ingesting",
            "status": "done",
            "ms": ms_ingest,
            "backend": backends["storage"],
            "payload": {"inputs": [i.model_dump() for i in inputs]}
        })

        # -------------------------------------------------------------
        # STAGE 2: UNDERSTANDING (Parallel Fact Extraction)
        # -------------------------------------------------------------
        t0 = time.time()
        await self.bus.publish(incident_id, {
            "incident_id": incident_id,
            "stage": "Understanding",
            "status": "start",
            "ms": 0,
            "backend": backends["llm"],
            "payload": {}
        })

        async def _extract_for_input(inp: InputItem):
            content = await self.storage.get_file(inp.uri)
            raw_facts = await self.llm.extract_facts(
                modality=inp.modality.value,
                filename=inp.filename,
                content=content,
                input_id=inp.input_id,
                incident_id=incident_id
            )
            parsed_facts = []
            for idx, rf in enumerate(raw_facts):
                fact_id = f"fact_{inp.modality.value[:2]}_{idx+1}_{str(uuid.uuid4())[:4]}"
                fact = Fact(
                    fact_id=fact_id,
                    incident_id=incident_id,
                    input_id=inp.input_id,
                    modality=inp.modality,
                    claim=rf.get("claim", ""),
                    evidence_pointer=rf.get("evidence_pointer", f"{inp.modality.value} source"),
                    zone=rf.get("zone", "Unknown"),
                    hazard=rf.get("hazard", "Unknown"),
                    severity=rf.get("severity", "unknown"),
                    affected_people=rf.get("affected_people", "unknown"),
                    confidence=float(rf.get("confidence", 0.9)),
                    observable=bool(rf.get("observable", True))
                )
                parsed_facts.append(fact)
                # Stream fact chip to SSE UI as it's extracted
                await self.bus.publish(incident_id, {
                    "incident_id": incident_id,
                    "stage": "Understanding",
                    "status": "progress",
                    "ms": int((time.time() - t0) * 1000),
                    "backend": backends["llm"],
                    "payload": {"new_fact": fact.model_dump()}
                })
            return parsed_facts

        # Run extract calls in parallel
        tasks = [_extract_for_input(inp) for inp in inputs]
        nested_facts = await asyncio.gather(*tasks) if tasks else []
        all_facts: list[Fact] = [f for sublist in nested_facts for f in sublist]

        # Save facts to database
        self.warehouse.save_facts(all_facts)

        # Deterministic fusion & conflict detection
        conflicts: list[Conflict] = []
        zones_seen = set(f.zone for f in all_facts if f.zone != "Unknown")
        primary_zone = list(zones_seen)[0] if zones_seen else "Zone B"

        # Detect conflicting reports (e.g. clear vs destroyed)
        claims_text = " ".join([f.claim.lower() for f in all_facts])
        if "clear" in claims_text and ("destroyed" in claims_text or "blocked" in claims_text):
            conflicts.append(Conflict(
                conflict_id=f"conflict_{uuid.uuid4().hex[:6]}",
                incident_id=incident_id,
                fact_ids=[f.fact_id for f in all_facts],
                description="Contradictory reports regarding road accessibility and status."
            ))

        ms_understanding = int((time.time() - t0) * 1000)
        latency_ms["understanding"] = ms_understanding

        await self.bus.publish(incident_id, {
            "incident_id": incident_id,
            "stage": "Understanding",
            "status": "done",
            "ms": ms_understanding,
            "backend": backends["llm"],
            "payload": {
                "fact_count": len(all_facts),
                "conflicts_count": len(conflicts),
                "zone": primary_zone
            }
        })

        # Update incident zone in DB
        incident.zone = primary_zone
        self.warehouse.save_incident(incident)

        # -------------------------------------------------------------
        # STAGE 3: RETRIEVING CONTEXT
        # -------------------------------------------------------------
        t0 = time.time()
        await self.bus.publish(incident_id, {
            "incident_id": incident_id,
            "stage": "Retrieving Context",
            "status": "start",
            "ms": 0,
            "backend": backends["retriever"],
            "payload": {}
        })

        query_summary = f"{primary_zone} " + " ".join([f.claim for f in all_facts[:3]])
        past_cases = self.retriever.search(query_summary, zone=primary_zone, top_k=5)

        ms_retrieval = int((time.time() - t0) * 1000)
        latency_ms["retrieval"] = ms_retrieval

        await self.bus.publish(incident_id, {
            "incident_id": incident_id,
            "stage": "Retrieving Context",
            "status": "done",
            "ms": ms_retrieval,
            "backend": backends["retriever"],
            "payload": {"past_cases": [c.model_dump() for c in past_cases]}
        })

        # -------------------------------------------------------------
        # STAGE 4: GENERATING DECISION
        # -------------------------------------------------------------
        t0 = time.time()
        await self.bus.publish(incident_id, {
            "incident_id": incident_id,
            "stage": "Generating Decision",
            "status": "start",
            "ms": 0,
            "backend": backends["llm"],
            "payload": {}
        })

        fused_fact_dicts = [f.model_dump() for f in all_facts]
        conflict_dicts = [c.model_dump() for c in conflicts]
        case_dicts = [c.model_dump() for c in past_cases]

        raw_decision_dict = await self.llm.generate_decision(
            fused_facts=fused_fact_dicts,
            conflicts=conflict_dicts,
            past_cases=case_dicts
        )

        ms_decision = int((time.time() - t0) * 1000)
        latency_ms["decision_generation"] = ms_decision

        await self.bus.publish(incident_id, {
            "incident_id": incident_id,
            "stage": "Generating Decision",
            "status": "done",
            "ms": ms_decision,
            "backend": backends["llm"],
            "payload": raw_decision_dict
        })

        # -------------------------------------------------------------
        # STAGE 5: VALIDATING EVIDENCE & CONFIDENCE
        # -------------------------------------------------------------
        t0 = time.time()
        await self.bus.publish(incident_id, {
            "incident_id": incident_id,
            "stage": "Validating Evidence",
            "status": "start",
            "ms": 0,
            "backend": backends["warehouse"],
            "payload": {}
        })

        raw_reasons = raw_decision_dict.get("reasons", [])
        verified_reasons, unsupported_count = Verifier.verify_decision(
            reasons=raw_reasons,
            valid_facts=fused_fact_dicts,
            valid_cases=case_dicts
        )

        modalities_present = list(set(i.modality.value for i in inputs))
        model_uncertainty = float(raw_decision_dict.get("model_uncertainty", 0.1))

        conf_score, conf_breakdown, review_req, review_reason = ConfidenceEngine.calculate_confidence(
            fused_facts=fused_fact_dicts,
            modalities_present=modalities_present,
            conflicts=conflict_dicts,
            past_cases=case_dicts,
            raw_reasons_count=len(raw_reasons),
            verified_reasons_count=len(verified_reasons),
            model_uncertainty=model_uncertainty
        )

        # Versioning support
        existing_decisions = self.warehouse.get_decisions_for_incident(incident_id)
        next_version = len(existing_decisions) + 1

        priority_str = raw_decision_dict.get("priority", "HIGH").upper()
        if priority_str not in PriorityEnum.__members__:
            priority_str = "HIGH"

        reason_items = [
            ReasonItem(
                text=vr["text"],
                fact_ids=vr.get("fact_ids", []),
                case_ids=vr.get("case_ids", [])
            ) for vr in verified_reasons
        ]

        total_ms = int((time.time() - start_time) * 1000)
        latency_ms["total"] = total_ms

        final_decision = Decision(
            decision_id=f"dec_{incident_id}_v{next_version}_{uuid.uuid4().hex[:4]}",
            incident_id=incident_id,
            version=next_version,
            priority=PriorityEnum[priority_str],
            recommended_action=raw_decision_dict.get("recommended_action", "Proceed with incident verification."),
            reasons=reason_items,
            confidence=conf_score,
            confidence_breakdown=conf_breakdown,
            review_required=review_req,
            review_reason=review_reason,
            backends=backends,
            latency_ms=latency_ms
        )

        self.warehouse.save_decision(final_decision)

        # Update incident status
        incident.priority = final_decision.priority
        incident.status = StatusEnum.NEEDS_REVIEW if review_req else StatusEnum.DECIDED
        self.warehouse.save_incident(incident)

        ms_validation = int((time.time() - t0) * 1000)
        latency_ms["validation"] = ms_validation

        # Audit Event logging
        self.warehouse.save_audit_event(AuditEvent(
            event_id=f"audit_{uuid.uuid4().hex[:8]}",
            request_id=request_id,
            incident_id=incident_id,
            stage="pipeline_completed",
            backend="pipeline",
            detail=f"Version v{next_version} generated. Priority={final_decision.priority.value}, Confidence={conf_score}%, Review={review_req}"
        ))

        await self.bus.publish(incident_id, {
            "incident_id": incident_id,
            "stage": "Validating Evidence",
            "status": "done",
            "ms": ms_validation,
            "backend": backends["warehouse"],
            "payload": {"decision": final_decision.model_dump()}
        })

        return final_decision
