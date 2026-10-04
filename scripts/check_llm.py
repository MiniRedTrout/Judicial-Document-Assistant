"""Проверка LLM на вымышленном документе, без OCR, SQLite и отправки писем.
Запуск: python -m scripts.check_llm
Выполняет один реальный API-запрос с вашим ключом из .env.
"""
from types import SimpleNamespace
from app.integration_settings import settings
from app.services.integrations.llm import extract_fields, LLMUnavailable


def main():
    print("API:", settings.llm_base)
    print("Модель:", settings.llm_model)
    if not settings.llm_key.strip():
        print("Ключ не задан; запроса не было")
        return 1
    text = ("Вымышленный документ для проверки API. Судебный приказ от 01.10.2026. "
            "Дело № 2-001/2026. Взыскать с Тестова Ивана Ивановича "
            "основной долг 1000 рублей. Остальные сведения отсутствуют.")
    try:
        fields = extract_fields(SimpleNamespace(text=text))
    except LLMUnavailable as error:
        print("Проверка не пройдена:", error)
        return 1
    print("API вернул JSON с полями:", len(fields))
    print("Тип документа:", fields.get("тип_документа"))
    print("Проверка подключения завершена; сверку реальных PDF выполните отдельно")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
