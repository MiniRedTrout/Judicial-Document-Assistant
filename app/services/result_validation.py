"""Проверка полноты и формата результатов; не юридическая экспертиза."""
import re
from app.schemas.document_result import DocumentType

REQUIRED = {
    'pdf': [('debtor.full_name', 'ФИО должника'), ('case.number', 'номер дела'),
            ('case.case_date', 'дата дела'), ('debt.principal', 'основной долг')],
    'xml': [('document.document_date', 'дата постановления'),
            ('debtor.full_name', 'имя должника'),
            ('enforcement.proceedings_number', 'номер исполнительного производства'),
            ('enforcement.document_number', 'номер исполнительного документа'),
            ('enforcement.document_date', 'дата исполнительного документа'),
            ('enforcement.debt_sum', 'сумма по исполнительному документу')],
}

def value_at(result, path):
    value = result
    for key in path.split('.'):
        value = getattr(value, key, None)
    return value

def apply_validation(result, kind):
    reasons = list(result.analysis.review_reasons)
    missing = list(result.analysis.missing_fields)
    if result.document.document_type in (DocumentType.UNKNOWN, DocumentType.UNSUPPORTED):
        if not any('Тип ' in reason for reason in reasons):
            reasons.append('Тип документа не определён')
    required = REQUIRED[kind]
    # ФССП в PDF требует реквизитов производства, как и XML.
    if kind == 'pdf' and result.document.document_type == DocumentType.FSSP_DECISION:
        required = REQUIRED['xml']
    absent = []
    for path, label in required:
        value = value_at(result, path)
        if value is None or (isinstance(value, str) and not value.strip()):
            absent.append(label)
            if path not in missing:
                missing.append(path)
    if absent:
        reasons.append('Не извлечены обязательные поля: ' + ', '.join(absent))
    for path in ('debt.principal', 'debt.penalty', 'debt.state_duty',
                 'debt.postal_expenses', 'enforcement.debt_sum', 'enforcement.enforcement_fee'):
        value = value_at(result, path)
        if value is not None and value < 0:
            reasons.append('Отрицательная сумма: ' + path)
    debt = result.debt
    if debt and debt.period_start and debt.period_end and debt.period_start > debt.period_end:
        reasons.append('Начало периода задолженности позже его окончания')
    debtor = result.debtor
    if kind == 'pdf' and debtor and debtor.passport:
        digits = re.sub(r'\D', '', debtor.passport)
        if len(digits) == 6:
            reasons.append('Проверьте полноту паспорта: извлечены только 6 цифр, серия могла потеряться при OCR')
    if debtor and debtor.birth_date and result.case and result.case.case_date:
        if debtor.birth_date > result.case.case_date:
            reasons.append('Дата рождения должника позже даты дела')
    result.analysis.review_reasons = list(dict.fromkeys(reasons))
    result.analysis.missing_fields = list(dict.fromkeys(missing))
    result.analysis.requires_review = bool(result.analysis.review_reasons)
    return result
