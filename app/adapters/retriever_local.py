"""Local Numpy vector retrieval adapter over seeded historical incidents."""
import pathlib
import sys

try:
    from app.models import PastCase
except ImportError:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    from app.models import PastCase

SEED_CASES = [
    PastCase(
        case_id="CASE-2024-089",
        summary="Flash flood in Zone B Market Area with 6 residents trapped on rooftops near River Bridge.",
        zone="Zone B",
        hazard="Submerged power transformer and fast river currents.",
        outcome="Emergency boat deployment deployed within 20 mins; electrical grid powered down; 0 fatalities.",
        lessons="Immediate power grid shutdown is vital before water rescue in urban flood zones."
    ),
    PastCase(
        case_id="CASE-2024-042",
        summary="Urban waterlogging in Zone C commercial district. 2 stalls flooded, road traffic jammed.",
        zone="Zone C",
        hazard="Blocked storm drains causing 1ft surface water.",
        outcome="Pumping trucks dispatched; traffic rerouted to bypass road; cleared in 2 hours.",
        lessons="Early traffic diversion prevents gridlock and allows drainage equipment fast access."
    ),
    PastCase(
        case_id="CASE-2025-012",
        summary="Heavy monsoon rain bulletin for Zone A hill slope areas.",
        zone="Zone A",
        hazard="Saturated soil, potential minor mudslides on unpaved slopes.",
        outcome="Precautionary warning issued; road patrols monitored culverts; no casualties.",
        lessons="Continuous rain advisories require preemptive monitoring of drainage culverts."
    ),
    PastCase(
        case_id="CASE-2025-104",
        summary="Landslide blocking Zone D Highway near Quarry Junction.",
        zone="Zone D",
        hazard="Heavy boulders blocking primary arterial road.",
        outcome="Heavy earthmovers deployed; alternative route established via East Bypass.",
        lessons="Single arterial blockages require immediate multi-agency traffic control."
    ),
    PastCase(
        case_id="CASE-2024-118",
        summary="Flash flood inundating low-lying residential colony in Zone B.",
        zone="Zone B",
        hazard="Rising river levels overflowing flood containment walls.",
        outcome="High-ground evacuation triggered; shelter established at Zone B Community Center.",
        lessons="Early evacuation triggers based on river gauge alerts reduce rescue delay."
    ),
    PastCase(
        case_id="CASE-2025-055",
        summary="Storm surge and canal overflow near Zone C industrial estate.",
        zone="Zone C",
        hazard="Chemical store inundation risk.",
        outcome="Hazardous material containment barriers installed; water pumped to secondary reservoir.",
        lessons="Industrial waterlogging requires immediate hazardous material checks."
    )
]


class RetrieverNumpy:
    def __init__(self):
        self.cases = SEED_CASES.copy()

    def add_case(self, case: PastCase):
        self.cases.append(case)

    def search(self, query_text: str, zone: str = "Unknown", top_k: int = 5) -> list[PastCase]:
        """Calculates text-similarity relevance scores against seed cases."""
        query_words = set(query_text.lower().split())
        results = []

        for case in self.cases:
            case_text = f"{case.summary} {case.zone} {case.hazard} {case.lessons}".lower()
            case_words = set(case_text.split())
            
            # Word overlap similarity
            overlap = len(query_words.intersection(case_words))
            score = 0.5 + (overlap / max(len(query_words), 1)) * 0.4
            
            # Boost score if zone matches
            if zone.lower() in case.zone.lower():
                score += 0.15

            score = min(round(score, 2), 0.98)
            
            c_copy = case.model_copy()
            c_copy.similarity_score = score
            results.append(c_copy)

        # Sort by similarity score descending
        results.sort(key=lambda x: x.similarity_score or 0.0, reverse=True)
        return results[:top_k]
