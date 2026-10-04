"""Адаптер ветки feature-llm к OpenAI-совместимому HTTP API."""
import json
import urllib.error
import urllib.request
from pathlib import Path

from app.integration_settings import settings

PROMPT_PATH = Path(__file__).resolve().parents[3] / "src" / "llm" / "prompt.txt"


class LLMUnavailable(RuntimeError):
    pass


def _reject_constant(value):
    raise ValueError("Недопустимое числовое значение JSON")


def extract_fields(source) -> dict:
    if not settings.llm_key:
        raise LLMUnavailable("LLM_API_KEY не настроен")
    text = source.text
    if not text.strip():
        raise LLMUnavailable("Текст PDF пуст")
    if len(text) > settings.llm_max_chars:
        raise LLMUnavailable("Текст превышает LLM_MAX_CHARS; документ не отправлен частично")
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
    }
    if settings.llm_json_mode:
        payload["response_format"] = {"type": "json_object"}
    request = urllib.request.Request(
        settings.llm_base.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + settings.llm_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout) as response:
            raw = json.loads(response.read())
        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content, parse_constant=_reject_constant)
    except urllib.error.HTTPError as error:
        status_code = error.code
        error.close()
        raise LLMUnavailable(f"LLM API вернул HTTP {status_code}") from None
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError):
        raise LLMUnavailable("LLM недоступна или вернула некорректный JSON") from None
    if not isinstance(parsed, dict) or parsed.get("error"):
        raise LLMUnavailable("LLM не вернула объект извлечённых полей")
    return parsed
