from pathlib import Path
from typing import Any

from scripts.xml_parser import parse_xml


def extract_xml(xml_path: str | Path) -> dict[str, Any]:
    """
    Адаптер между нашим FastAPI backend и XML-парсером J2.

    Принимает путь к XML-файлу и возвращает
    структурированные данные от J2.
    """
    return parse_xml(Path(xml_path))