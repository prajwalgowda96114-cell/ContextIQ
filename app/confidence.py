"""Confidence score & human review recommendation engine for ContextIQ."""
import os
import pathlib
import sys
from typing import Any

try:
    from app.models import ConfidenceBreakdown
except ImportError:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from app.models import ConfidenceBreakdown



class ConfidenceEngine:
    REVIEW_THRESHOLD = float(os.getenv("REVIEW_THRESHOLD", "70"))

    @classmethod
    def calculate_confidence(
        self,
        fused_facts: list[dict[str, Any]],
        modalities_present: list[str],
        conflicts: list[dict[str, Any]],
        past_cases: list[dict[str, Any]],
        raw_reasons_count: int,
        verified_reasons_count: int,
        model_uncertainty: float = 0.1
    ) -> tuple[float, ConfidenceBreakdown, bool, str]:
        """Calculates multi-factor confidence score and determines human review status.
        Returns (total_score, breakdown, review_required, review_reason).
        """
        # 1. C - Input Completeness (0-1)
        required_fields = ["zone", "hazard", "severity", "affected_people"]
        filled_count = 0
        total_fields = max(len(fused_facts) * len(required_fields), 1)

        for f in fused_facts:
            for field in required_fields:
                val = f.get(field)
                if val and val != "Unknown" and val != "unknown":
                    filled_count += 1

        c_completeness = min(filled_count / total_fields, 1.0)
        # Boost completeness if multiple modalities submitted
        if len(modalities_present) >= 3:
            c_completeness = min(c_completeness + 0.2, 1.0)
        elif len(modalities_present) == 2:
            c_completeness = min(c_completeness + 0.1, 1.0)

        # 2. A - Cross-Modal Agreement (0-1)
        # Check if facts from different modalities corroborate zone or hazard
        zones_by_modality = {}
        for f in fused_facts:
            mod = f.get("modality", "text")
            z = f.get("zone", "Unknown")
            if z != "Unknown":
                zones_by_modality.setdefault(z, set()).add(mod)

        corroborated_zones = [z for z, mods in zones_by_modality.items() if len(mods) >= 2]
        a_agreement = 0.9 if corroborated_zones else (0.7 if len(modalities_present) > 1 else 0.5)

        # 3. R - Retrieval Relevance (0-1)
        top_cases = past_cases[:3]
        if top_cases:
            mean_sim = sum(c.get("similarity_score", 0.7) for c in top_cases) / len(top_cases)
            r_relevance = min(max(mean_sim, 0.0), 1.0)
        else:
            r_relevance = 0.5

        # 4. E - Evidence Coverage (0-1)
        if raw_reasons_count > 0:
            e_coverage = min(verified_reasons_count / raw_reasons_count, 1.0)
        else:
            e_coverage = 0.0

        # 5. U - Model Uncertainty (0-1)
        u_uncertainty = min(max(model_uncertainty, 0.0), 1.0)

        # Raw weighted formula
        raw_weighted = (
            0.25 * c_completeness +
            0.25 * a_agreement +
            0.20 * r_relevance +
            0.20 * e_coverage +
            0.10 * (1.0 - u_uncertainty)
        )
        raw_weighted = min(max(raw_weighted, 0.0), 1.0)

        # Conflict penalty: minus 10 points (0.10) per unresolved conflict
        conflict_penalty = len(conflicts) * 0.10

        final_score = round(max(0.0, (raw_weighted - conflict_penalty) * 100.0), 1)

        breakdown = ConfidenceBreakdown(
            completeness=round(c_completeness * 100, 1),
            agreement=round(a_agreement * 100, 1),
            retrieval_relevance=round(r_relevance * 100, 1),
            evidence_coverage=round(e_coverage * 100, 1),
            model_uncertainty=round(u_uncertainty * 100, 1),
            conflict_penalty=round(conflict_penalty * 100, 1),
            total_score=final_score
        )

        review_required = final_score < self.REVIEW_THRESHOLD
        review_reason = None

        if review_required:
            lowest_factor = min(
                [
                    ("input completeness", breakdown.completeness),
                    ("cross-modal agreement", breakdown.agreement),
                    ("retrieval relevance", breakdown.retrieval_relevance),
                    ("evidence coverage", breakdown.evidence_coverage),
                ],
                key=lambda x: x[1]
            )
            if conflicts:
                review_reason = f"Confidence {final_score}% is below threshold {self.REVIEW_THRESHOLD}%. Unresolved conflicting reports detected."
            else:
                review_reason = f"Confidence {final_score}% is below threshold {self.REVIEW_THRESHOLD}%. Low {lowest_factor[0]} ({lowest_factor[1]}%)."

        return final_score, breakdown, review_required, review_reason
