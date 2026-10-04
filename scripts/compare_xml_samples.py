"""Сверка с обезличенными XML и эталоном организаторов. Без LLM и SMTP.
python -m scripts.compare_xml_samples
"""
import csv
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from app.services.integrations.xml_parser import extract_xml

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/fssp"
MONEY = {"IdDebtSum", "rub_deb", "rub_peni", "rub_poshlina", "rub_post"}
DATES = {"DocDate", "IdDocDate", "IdDeloDate", "date_start", "date_end"}


def normalized(key, value):
    if value is None or value == "":
        return ""
    if key == "FileName":
        return Path(str(value)).name
    if key in MONEY:
        return str(Decimal(str(value).replace(",", ".")).quantize(Decimal(".01")))
    if key in DATES:
        return str(value)[:10]
    return str(value).strip()


def compare_samples():
    differences = []
    checked = rows = 0
    with (FIXTURES / "labels.csv").open(encoding="utf-8-sig", newline="") as source:
        for expected in csv.DictReader(source):
            name = Path(expected["FileName"]).name
            actual = extract_xml(FIXTURES / name)
            rows += 1
            for key, value in expected.items():
                checked += 1
                parsed = normalized(key, actual.get(key))
                reference = normalized(key, value)
                if parsed != reference:
                    differences.append({"file": name, "field": key,
                                        "actual": parsed, "expected": reference})
    return {"documents": rows, "checked_cells": checked,
            "matched_cells": checked - len(differences),
            "mismatches_by_field": dict(Counter(x["field"] for x in differences)),
            "differences": differences}


if __name__ == "__main__":
    print(json.dumps(compare_samples(), ensure_ascii=False, indent=2))
