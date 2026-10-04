from pathlib import Path
from typing import Any
from scripts.xml_parser import parse_xml


def extract_xml(xml_path: str | Path) -> dict[str, Any]:
    result = parse_xml(Path(xml_path), include_details=True)
    if result is None:
        raise ValueError("Не удалось прочитать XML: проверьте формат и журнал сервера")
    return result
