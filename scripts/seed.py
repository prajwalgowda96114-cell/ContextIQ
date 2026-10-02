"""Seeding script to populate ContextIQ demo incidents A, B, C into storage and warehouse."""
import asyncio
import os
import pathlib
import sys

# Add backend directory to sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.models import Incident, InputItem, ModalityEnum, StatusEnum, PriorityEnum
from app.adapters.storage_local import StorageLocal
from app.adapters.bus_local import BusLocal
from app.adapters.warehouse_sqlite import WarehouseSQLite
from app.adapters.retriever_local import RetrieverNumpy
from app.llm import LLMClient
from app.pipeline import PipelineEngine

ROOT = pathlib.Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"


async def seed():
    storage = StorageLocal()
    bus = BusLocal()
    warehouse = WarehouseSQLite()
    retriever = RetrieverNumpy()
    llm = LLMClient()
    pipeline = PipelineEngine(storage, bus, warehouse, retriever, llm)

    # 1. Incident A - Zone B (Critical Flooding)
    inc_a_id = "INC-2026-0001"
    inc_a = Incident(
        incident_id=inc_a_id,
        title="Severe Flash Flood & Submerged Grid",
        description="Multiple reports of rising waters, rooftop strandings, and submerged transformer in Zone B.",
        zone="Zone B",
        status=StatusEnum.PROCESSING
    )
    warehouse.save_incident(inc_a)

    dir_a = SAMPLES_DIR / "incident_a"
    if dir_a.exists():
        text_bytes = (dir_a / "reports.txt").read_bytes()
        uri_t, sha_t = await storage.save_file(inc_a_id, "reports.txt", text_bytes)
        warehouse.save_input(InputItem(
            input_id=f"inp_text_a", incident_id=inc_a_id, modality=ModalityEnum.TEXT,
            uri=uri_t, filename="reports.txt", bytes_sha256=sha_t
        ))

        photo_bytes = (dir_a / "photo.jpg").read_bytes()
        uri_p, sha_p = await storage.save_file(inc_a_id, "photo.jpg", photo_bytes)
        warehouse.save_input(InputItem(
            input_id=f"inp_image_a", incident_id=inc_a_id, modality=ModalityEnum.IMAGE,
            uri=uri_p, filename="photo.jpg", bytes_sha256=sha_p
        ))

        pdf_bytes = (dir_a / "advisory.pdf").read_bytes()
        uri_pdf, sha_pdf = await storage.save_file(inc_a_id, "advisory.pdf", pdf_bytes)
        warehouse.save_input(InputItem(
            input_id=f"inp_pdf_a", incident_id=inc_a_id, modality=ModalityEnum.PDF,
            uri=uri_pdf, filename="advisory.pdf", bytes_sha256=sha_pdf
        ))

    print(f"Running pipeline for Incident A ({inc_a_id})...")
    dec_a = await pipeline.run_pipeline(inc_a_id)
    print(f"Incident A -> Priority: {dec_a.priority.value}, Confidence: {dec_a.confidence}%")

    # 2. Incident B - Zone C (Waterlogging)
    inc_b_id = "INC-2026-0002"
    inc_b = Incident(
        incident_id=inc_b_id,
        title="Commercial Corridor Waterlogging",
        description="Drainage overflow and stalled traffic in Zone C.",
        zone="Zone C",
        status=StatusEnum.PROCESSING
    )
    warehouse.save_incident(inc_b)

    dir_b = SAMPLES_DIR / "incident_b"
    if dir_b.exists():
        text_bytes = (dir_b / "reports.txt").read_bytes()
        uri_t, sha_t = await storage.save_file(inc_b_id, "reports.txt", text_bytes)
        warehouse.save_input(InputItem(
            input_id=f"inp_text_b", incident_id=inc_b_id, modality=ModalityEnum.TEXT,
            uri=uri_t, filename="reports.txt", bytes_sha256=sha_t
        ))

        photo_bytes = (dir_b / "photo.jpg").read_bytes()
        uri_p, sha_p = await storage.save_file(inc_b_id, "photo.jpg", photo_bytes)
        warehouse.save_input(InputItem(
            input_id=f"inp_image_b", incident_id=inc_b_id, modality=ModalityEnum.IMAGE,
            uri=uri_p, filename="photo.jpg", bytes_sha256=sha_p
        ))

    print(f"Running pipeline for Incident B ({inc_b_id})...")
    dec_b = await pipeline.run_pipeline(inc_b_id)
    print(f"Incident B -> Priority: {dec_b.priority.value}, Confidence: {dec_b.confidence}%")

    # 3. Incident C - Zone A (Precautionary Rain)
    inc_c_id = "INC-2026-0003"
    inc_c = Incident(
        incident_id=inc_c_id,
        title="Hill Slope Monsoon Watch",
        description="Continuous rain in Zone A with no reported damage.",
        zone="Zone A",
        status=StatusEnum.PROCESSING
    )
    warehouse.save_incident(inc_c)

    dir_c = SAMPLES_DIR / "incident_c"
    if dir_c.exists():
        text_bytes = (dir_c / "reports.txt").read_bytes()
        uri_t, sha_t = await storage.save_file(inc_c_id, "reports.txt", text_bytes)
        warehouse.save_input(InputItem(
            input_id=f"inp_text_c", incident_id=inc_c_id, modality=ModalityEnum.TEXT,
            uri=uri_t, filename="reports.txt", bytes_sha256=sha_t
        ))

    print(f"Running pipeline for Incident C ({inc_c_id})...")
    dec_c = await pipeline.run_pipeline(inc_c_id)
    print(f"Incident C -> Priority: {dec_c.priority.value}, Confidence: {dec_c.confidence}%")

    print("\nAll demo incidents seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
