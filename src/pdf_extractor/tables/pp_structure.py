from pathlib import Path

from src.config import pdf_settings
from src.schemas.pdf_parser import TableData
from src.utils.imaging import pdf_to_images
from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_tables_pp_structure(pdf_path: str | Path) -> list[TableData]:
    """Извлекает таблицы из сканированного PDF через PP-Structure."""
    try:
        from paddleocr import PPStructure
    except ImportError:
        logger.warning("PP-Structure не установлен — пропускаем")
        return []

    pdf_path = Path(pdf_path)
    images = pdf_to_images(pdf_path, dpi=pdf_settings.ocr_dpi)
    engine = PPStructure(show_log=False, lang="ru")

    tables: list[TableData] = []
    for i, img in enumerate(images, start=1):
        try:
            result = engine(img)
            for item in result:
                if item.get("type") == "table":
                    tables.append(
                        TableData(
                            page=i,
                            data=[],
                            extractor="pp_structure",
                        )
                    )
        except Exception as e:
            logger.debug("PP-Structure ошибка на стр. {}: {}", i, e)

    return tables