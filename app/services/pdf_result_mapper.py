"""Сопоставление полей LLM с общей схемой результатов backend."""
from app.schemas.document_result import (
    DocumentResult, DocumentInfo, DocumentType, DebtorInfo, AddressInfo,
    CaseInfo, DebtInfo, CoDefendantsInfo, AnalysisResult,
)
from app.services.xml_result_mapper import _to_date, _to_decimal
from app.services.result_validation import apply_validation
from app.services.pdf_source_checks import check_pdf_source

TYPES = {
    "приказ": DocumentType.COURT_ORDER, "приказ эл": DocumentType.COURT_ORDER,
    "судебный приказ": DocumentType.COURT_ORDER,
    "ил": DocumentType.WRIT_OF_EXECUTION, "ил эл": DocumentType.WRIT_OF_EXECUTION,
    "исполнительный лист": DocumentType.WRIT_OF_EXECUTION,
    "постановление фссп": DocumentType.FSSP_DECISION,
}


def map_pdf_result(fields: dict, file_name: str, errors=None, source_text="") -> DocumentResult:
    fields, source_reasons = check_pdf_source(fields, source_text)
    reasons = list(errors or []) + source_reasons
    missing = []
    def text(key):
        value = fields.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(key)
            return None
        if not isinstance(value, str):
            reasons.append(f"Поле {key} пришло не строкой; проверьте значение")
        return str(value).strip()
    def converted(key, converter):
        value = fields.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(key)
            return None
        try:
            return converter(value)
        except (ValueError, TypeError, ArithmeticError):
            reasons.append(f"Некорректное значение поля {key}")
            missing.append(key)
            return None

    raw_type = text("тип_документа")
    doc_type = TYPES.get((raw_type or "").lower(), DocumentType.UNKNOWN)
    if doc_type == DocumentType.UNKNOWN:
        reasons.append("Тип документа требует проверки классификатором")
    if not fields and not reasons:
        reasons.append("Модель не вернула извлечённые поля PDF")
    names = fields.get("соответчики_фио")
    if isinstance(names, str):
        names = [name.strip() for name in names.split(",") if name.strip()]
    elif names is None:
        names = []
    elif not isinstance(names, list) or any(not isinstance(n, str) for n in names):
        names = []
        reasons.append("Некорректный список соответчиков")
    count = converted("соответчики_кол-во", int)
    if count is not None and (count < 1 or (names and count != len(names))):
        reasons.append("Количество должников требует проверки")
    result = DocumentResult(
        document=DocumentInfo(file_name=file_name, document_type=doc_type, document_type_2=raw_type),
        debtor=DebtorInfo(
            full_name=text("фио"), last_name=text("фамилия"), first_name=text("имя"),
            middle_name=text("отчество"), birth_date=converted("дата_рождения", _to_date),
            passport=text("паспорт"), inn=text("инн"), snils=text("снилс"),
        ),
        address=AddressInfo(street=text("улица"), dom=text("дом"), kv=text("кв")),
        case=CaseInfo(number=text("дело_номер"), case_date=converted("дело_дата", _to_date)),
        debt=DebtInfo(
            period_start=converted("период_дз_начало", _to_date),
            period_end=converted("период_дз_оконч", _to_date),
            principal=converted("дз_осн", _to_decimal),
            penalty=converted("дз_пени", _to_decimal),
            state_duty=converted("дз_пошлина", _to_decimal),
        ),
        co_defendants=CoDefendantsInfo(count=count, names=names),
        analysis=AnalysisResult(requires_review=True, review_reasons=reasons,
                                missing_fields=list(dict.fromkeys(missing))),
    )

    return apply_validation(result, "pdf")
