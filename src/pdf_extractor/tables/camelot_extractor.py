from pathlib import Path

from src.schemas.pdf_parser import TableData
from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_tables_camelot(pdf_path: str | Path) -> list[TableData]:
    """Извлекает таблицы из PDF с текстовым слоем через Camelot."""
    try:
        import camelot
    except ImportError:
        logger.warning("Camelot не установлен — пропускаем извлечение таблиц")
        return []

    pdf_path = Path(pdf_path)
    tables: list[TableData] = []

    for flavor in ("lattice", "stream"):
        try:
            found = camelot.read_pdf(str(pdf_path), pages="all", flavor=flavor)
            for t in found:
                try:
                    if t.df.empty:
                        continue
                    tables.append(
                        TableData(
                            page=int(t.page),
                            data=t.df.values.tolist(),
                            extractor=f"camelot_{flavor}",
                            confidence=(
                                float(t.accuracy) if hasattr(t, "accuracy") else None
                            ),
                        )
                    )
                except Exception as e:
                    logger.warning("Ошибка обработки таблицы: {}", e)
                    continue
            if tables:
                logger.debug(
                    "{}: найдено {} таблиц ({})",
                    pdf_path.name,
                    len(tables),
                    flavor,
                )
                break
        except Exception as e:
            logger.debug("Camelot {} не сработал для {}: {}", flavor, pdf_path.name, e)
            continue

    return tables