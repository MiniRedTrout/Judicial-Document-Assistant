"""Отбор из ветки check-mail. """
from dataclasses import asdict

from scripts.find_word import check_document, normalize_text, find_markers


def review_pdf(source, fields: dict | None = None) -> dict:
    checked = check_document(source)
    matches = [asdict(match) for match in checked.matches]
    confirmed = False
    phrase = (fields or {}).get("matched_phrase")
    evidence = (fields or {}).get("lawyer_evidence")
    # Для автоматической отправки нужны фраза и цитата из исходного текста.
    if isinstance(phrase, str) and isinstance(evidence, str) and evidence.strip():
        evidence_text = normalize_text(evidence)
        for match in matches:
            if (normalize_text(phrase).rstrip(".") == normalize_text(match["phrase"]).rstrip(".")
                    and evidence_text in normalize_text(source.text)
                    and evidence_text in normalize_text(match["snippet"])
                    and any(normalize_text(item.phrase).rstrip(".") == normalize_text(match["phrase"]).rstrip(".")
                            for item in find_markers(evidence_text))):
                confirmed = True
                break
    return {
        "needs_lawyer": checked.needs_lawyer,
        "requires_context_review": checked.needs_lawyer and not confirmed,
        "selection_method": "llm_and_markers" if confirmed else "marker_candidates",
        "matches": matches,
    }
