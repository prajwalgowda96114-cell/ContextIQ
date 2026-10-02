"""Deterministic evidence verifier for ContextIQ decisions."""
import re
from typing import Any


class Verifier:
    @staticmethod
    def verify_decision(
        reasons: list[dict[str, Any]],
        valid_facts: list[dict[str, Any]],
        valid_cases: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], int]:
        """Validates decision reasons against provided facts and retrieved cases.
        Returns (verified_reasons, unsupported_claims_count).
        """
        fact_id_map = {f["fact_id"]: f for f in valid_facts if "fact_id" in f}
        case_id_map = {c["case_id"]: c for c in valid_cases if "case_id" in c}

        verified_reasons = []
        unsupported_count = 0

        for r in reasons:
            text = r.get("text", "")
            cited_facts = r.get("fact_ids", [])
            cited_cases = r.get("case_ids", [])

            # 1. Verify citations exist
            valid_cited_facts = [fid for fid in cited_facts if fid in fact_id_map]
            valid_cited_cases = [cid for cid in cited_cases if cid in case_id_map]

            # 2. Require >= 1 citation
            if not valid_cited_facts and not valid_cited_cases:
                unsupported_count += 1
                continue

            # 3. Numeric & location hallucination check
            cited_corpus = " ".join(
                [fact_id_map[fid].get("claim", "") + " " + str(fact_id_map[fid].get("evidence_pointer", "")) for fid in valid_cited_facts] +
                [case_id_map[cid].get("summary", "") for cid in valid_cited_cases]
            )

            # Extract numbers from reason text (excluding version/case identifiers like CASE-2024-089)
            clean_text = re.sub(r"CASE-\d+-\d+|INC-\d+-\d+|fact_\w+", "", text)
            numbers_in_reason = set(re.findall(r"\b\d+\b", clean_text))
            numbers_in_corpus = set(re.findall(r"\b\d+\b", cited_corpus))

            # If reason claims numbers not in cited corpus, flag as unsupported
            unsupported_numbers = numbers_in_reason - numbers_in_corpus
            if unsupported_numbers:
                # Dropped due to unsupported numeric claim
                unsupported_count += 1
                continue

            # Keep verified reason with validated citation lists
            r_copy = dict(r)
            r_copy["fact_ids"] = valid_cited_facts
            r_copy["case_ids"] = valid_cited_cases
            verified_reasons.append(r_copy)

        return verified_reasons, unsupported_count
