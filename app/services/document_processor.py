"""Обработка документов: PDF -> LLM, XML -> схема -> SQLite."""
import logging
from pathlib import Path

from app.integration_settings import settings
from app.services.document_store import get_document, save_document_result, update_document_status
from app.services.xml_result_mapper import map_xml_result, serialize_xml_fields

logger = logging.getLogger(__name__)


def _finish_result(document_id: str, result: dict, kind: str) -> None:
    review = result["analysis"]["requires_review"]
    update_document_status(
        document_id, "REQUIRES_REVIEW" if review else "COMPLETED", "COMPLETED",
        f"Данные {kind} сохранены; требуется проверка" if review
        else f"Данные {kind} сохранены; проверки полноты и формата пройдены", 100,
    )


def _process_xml(document_id: str, path: Path) -> None:
    from app.services.integrations.xml_parser import extract_xml
    update_document_status(document_id, "PROCESSING", "EXTRACTING_FIELDS",
                           "Разбираем XML-документ ФССП...", 20)
    xml_result = extract_xml(path)
    if not any(xml_result.get(k) for k in ("DocType", "DocType2", "DbtrName", "IpNo")):
        raise ValueError("XML-парсер не обнаружил сведения документа ФССП")
    update_document_status(document_id, "PROCESSING", "VALIDATING",
                           "Преобразуем поля XML в схему результата...", 85)
    document = get_document(document_id)
    file_name = document["file_name"] if document else path.name
    result = map_xml_result(xml_result, file_name).model_dump(mode="json")
    result["xml_fields"] = serialize_xml_fields(xml_result)
    result["xml_metadata"] = {key: value for key, value in xml_result.items() if key.startswith("_")}
    result["extracted_text"] = xml_result.get("IdDebtText") or ""
    # Постановления ФССП не отправляются по фразам, процитированным из судебного акта.
    result["lawyer_review"] = {"needs_lawyer": False, "requires_context_review": False,
                              "selection_method": "not_applicable_xml", "matches": []}
    save_document_result(document_id, result)
    _finish_result(document_id, result, "XML")


def _process_pdf(document_id: str, path: Path) -> None:
    from app.services.integrations.pdf_extractor import extract_pdf
    from app.services.integrations.llm import extract_fields, LLMUnavailable
    from app.services.pdf_result_mapper import map_pdf_result
    from app.services.lawyer_review import review_pdf

    update_document_status(document_id, "PROCESSING", "EXTRACTING_TEXT",
                           "Извлекаем текст из PDF...", 20)
    source = extract_pdf(path)
    if source.errors:
        raise RuntimeError("Ошибка извлечения PDF: " + "; ".join(source.errors))
    if not source.text.strip():
        raise RuntimeError("Не удалось извлечь текст из PDF")
    document = get_document(document_id)
    file_name = document["file_name"] if document else path.name
    update_document_status(document_id, "PROCESSING", "EXTRACTING_FIELDS",
                           "Классифицируем документ и извлекаем поля через LLM...", 60)
    fields = {}
    errors = []
    try:
        fields = extract_fields(source)
    except LLMUnavailable as error:
        errors.append(str(error))
    except Exception:
        logger.exception("Ошибка адаптера LLM, документ %s", document_id)
        errors.append("Ошибка LLM; извлечённый текст сохранён для повторной обработки")
    update_document_status(document_id, "PROCESSING", "VALIDATING",
                           "Проверяем формат полей и отбираем акты юристу...", 85)
    try:
        mapped = map_pdf_result(fields, file_name, errors=errors, source_text=source.text)
    except Exception:
        logger.exception("Ошибка преобразования ответа LLM, документ %s", document_id)
        errors.append("Ответ модели не соответствует схеме; текст сохранён")
        fields = {}
        mapped = map_pdf_result({}, file_name, errors=errors)
    result = mapped.model_dump(mode="json")
    result["llm_fields"] = serialize_xml_fields(fields)
    result["extracted_text"] = source.text
    result["lawyer_review"] = review_pdf(source, fields)
    save_document_result(document_id, result)
    _finish_result(document_id, result, "PDF")
    review = result["lawyer_review"]
    if (settings.mail_auto_send and settings.mail_enabled
            and review["needs_lawyer"] and not review["requires_context_review"]):
        from app.services.lawyer_mail import send_document_to_lawyer
        send_document_to_lawyer(document_id)


def process_document_background(document_id: str, file_path: str, file_type: str) -> None:
    try:
        update_document_status(document_id, "PROCESSING", "STARTING",
                               "Начинаем обработку документа...", 5)
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        if file_type.lower() == "xml":
            _process_xml(document_id, path)
        elif file_type.lower() == "pdf":
            _process_pdf(document_id, path)
        else:
            raise ValueError(f"Неподдерживаемый тип файла: {file_type}")
    except Exception as error:
        logger.exception("Ошибка обработки документа %s", document_id)
        update_document_status(document_id, "ERROR", "ERROR",
                               "При обработке документа произошла ошибка", 100,
                               error=str(error) if isinstance(error, (FileNotFoundError, ValueError))
                               else "Ошибка обработки. Подробности в журнале сервера.")
