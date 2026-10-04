"""Преобразование результата J2 в общую схему нашего backend."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.result_validation import apply_validation

from app.schemas.document_result import (
    AddressInfo,
    AnalysisResult,
    CaseInfo,
    DebtInfo,
    DebtorInfo,
    DocumentInfo,
    DocumentResult,
    DocumentType,
    EnforcementInfo,
)


def _to_date(value: Any) -> date | None:
    """J2 возвращает строки дат и pandas.Timestamp (наследник datetime)."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None
    for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Неизвестный формат даты: {text}")


def _to_decimal(value: Any) -> Decimal | None:
    """Не превращаем пустое значение в 0; деньги переводим через строку."""
    if value is None or value == "":
        return None
    text = str(value).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not text:
        return None
    number = Decimal(text)
    if not number.is_finite():
        raise ValueError("Сумма должна быть конечным числом")
    return number


def map_xml_result(xml_result: dict[str, Any], file_name: str) -> DocumentResult:
    """Сопоставляет поля J2 с полями API; ошибки значений отмечает для проверки."""
    review_reasons = []
    missing_fields = [
        key for key, value in xml_result.items()
        if value is None or (isinstance(value, str) and not value.strip())
    ]

    def read_date(key: str) -> date | None:
        try:
            return _to_date(xml_result.get(key))
        except (TypeError, ValueError):
            review_reasons.append(f"Поле {key}: не удалось преобразовать дату")
            if key not in missing_fields:
                missing_fields.append(key)
            return None

    def read_money(key: str) -> Decimal | None:
        try:
            return _to_decimal(xml_result.get(key))
        except (InvalidOperation, TypeError, ValueError):
            review_reasons.append(f"Поле {key}: не удалось преобразовать сумму")
            if key not in missing_fields:
                missing_fields.append(key)
            return None

    # Это правило для уже разобранного XML, а не классификатор J2 для PDF.
    document_type_2 = xml_result.get("DocType2")
    document_type = DocumentType.UNKNOWN
    if isinstance(document_type_2, str) and document_type_2.startswith("Постановление"):
        document_type = DocumentType.FSSP_DECISION
    else:
        review_reasons.append("Тип XML-документа не определён; классификатор ещё не подключён")

    result = DocumentResult(
        document=DocumentInfo(
            file_name=file_name,
            document_type=document_type,
            document_type_2=document_type_2,
            document_date=read_date("DocDate"),
            debtor_type=xml_result.get("DebtorType"),
        ),
        debtor=DebtorInfo(full_name=xml_result.get("DbtrName")),
        address=AddressInfo(
            full_address=xml_result.get("DbtrAdr"),
            street=xml_result.get("street"),
            dom=xml_result.get("dom"),
            kv=xml_result.get("kv"),
        ),
        case=CaseInfo(
            number=xml_result.get("IdDeloNo"),
            case_date=read_date("IdDeloDate"),
        ),
        debt=DebtInfo(
            period_start=read_date("date_start"),
            period_end=read_date("date_end"),
            principal=read_money("rub_deb"),
            penalty=read_money("rub_peni"),
            state_duty=read_money("rub_poshlina"),
            postal_expenses=read_money("rub_post"),
        ),
        enforcement=EnforcementInfo(
            proceedings_number=xml_result.get("IpNo"),
            debt_text=xml_result.get("IdDebtText"),
            document_number=xml_result.get("IdDocNo"),
            document_date=read_date("IdDocDate"),
            debt_sum=read_money("IdDebtSum"),
            id_type=xml_result.get("IdType"),
        ),
        analysis=AnalysisResult(
            requires_review=True,
            review_reasons=review_reasons,
            missing_fields=missing_fields,
        ),
    )

    # Отмечаем незаполненные поля XML-шаблона. Пустое поле может быть допустимым:
    # список не означает, что каждое из этих полей обязательно в любом документе.
    return apply_validation(result, "xml")


def serialize_xml_fields(xml_result: dict[str, Any]) -> dict[str, Any]:
    """Сохраняет все исходные поля J2, приводя Timestamp к JSON-совместимой дате."""
    return {
        key: value.date().isoformat() if isinstance(value, datetime)
        else value.isoformat() if isinstance(value, date)
        else str(value) if isinstance(value, Decimal)
        else value
        for key, value in xml_result.items()
    }
