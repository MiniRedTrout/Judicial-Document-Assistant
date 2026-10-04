"""Консервативная сверка PDF: исправляем только подтверждённые текстом значения."""
import re
from decimal import Decimal, InvalidOperation

AMOUNT = r"(?<![\d.,])\d{1,3}(?:[ \u00a0]\d{3})*[.,]\d{2}(?!\d)|(?<![\d.,])\d+[.,]\d{2}(?!\d)"


def money(value):
    try:
        number = Decimal(str(value).replace(" ", "").replace("\u00a0", "").replace(",", "."))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def check_pdf_source(fields, source_text):
    # Исходные llm_fields сохраняются отдельно; словарь ответа не меняем.
    checked = dict(fields)
    reasons = []
    text = re.sub(r"\s+", " ", source_text or "")
    # Узкий шаблон: долг за потреблённую энергию/услуги + явный размер.
    # Не выбираем произвольное первое число из документа или тарифов.
    principal_pattern = (
        r"задолженность\s+по\s+оплате\s+за\s+потребленную\s+"
        r"(?:тепловую\s+энергию|электроэнергию|воду)"
        r"(?:(?!задолженность|пени|пошлин|взыскать).){0,260}?"
        r"(?:в\s+)?размере\s+(" + AMOUNT + r")"
    )
    principals = {money(m.group(1)) for m in re.finditer(principal_pattern, text, re.I)}
    totals = {money(m.group(1)) for m in re.finditer(r"на\s+сумму\s*[:：]?\s*(" + AMOUNT + r")", text, re.I)}
    principals.discard(None)
    totals.discard(None)
    current = money(checked.get("дз_осн"))
    if len(principals) == 1 and current in totals and current not in principals:
        checked["дз_осн"] = str(next(iter(principals)))
        reasons.append("Основной долг исправлен по тексту: модель подставила общую сумму; проверьте исправление")
    elif current is not None and principals and current not in principals:
        reasons.append("Основной долг отличается от явно указанной в тексте задолженности; требуется сверка")

    # Формат 23-17К4 неоднозначен сам по себе. Разделяем лишь при наличии
    # второго адреса с теми же улицей, домом и квартирой в отдельных компонентах.
    dom = str(checked.get("дом") or "").strip()
    street = str(checked.get("улица") or "").strip()
    combined = re.fullmatch(r"(\d+[а-яА-Я]?)-(\d+(?:[кК]\d+)?)", dom)
    if combined and not checked.get("кв") and street:
        house, flat = combined.groups()
        flat_number = re.match(r"\d+", flat).group()
        structured = re.escape(street) + r"\s*,\s*" + re.escape(house) + r"\s*,\s*" + re.escape(flat_number) + r"(?!\d)"
        literal = r"(?:д(?:ом)?[.:]?\s*)" + re.escape(dom) + r"(?![\w-])"
        if re.search(structured, text, re.I) and re.search(literal, text, re.I):
            checked["дом"], checked["кв"] = house, flat
            reasons.append("Дом и квартира разделены по повторным адресным фрагментам; проверьте исправление")
        else:
            reasons.append("В номере дома возможно объединены дом и квартира; требуется сверка адреса")
    return checked, reasons
