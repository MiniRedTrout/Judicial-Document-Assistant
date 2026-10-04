"""Адаптер ветки feature-llm к OpenAI-совместимому HTTP API."""
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from app.integration_settings import settings

PROMPT_PATH = Path(__file__).resolve().parents[3] / "src" / "llm" / "prompt.txt"


class LLMUnavailable(RuntimeError):
    pass


def _reject_constant(value):
    raise ValueError("Недопустимое числовое значение JSON")


HTTP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "DeloDocumentAssistant/1.0",
}


def _http_failure(error) -> str:
    """Показываем только известные коды, а не текст ответа с возможными секретами."""
    code = None
    try:
        body = error.read(8192).decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
            detail = payload.get("error", {}) if isinstance(payload, dict) else {}
            if isinstance(detail, dict):
                known = {
                    "model_permission_blocked_org", "model_permission_blocked_project",
                    "permissions_error", "invalid_api_key", "rate_limit_exceeded",
                    "context_length_exceeded", "json_validate_failed", "model_not_found",
                }
                for candidate in (detail.get("code"), detail.get("type")):
                    if isinstance(candidate, str) and candidate in known:
                        code = candidate
                        break
        except (TypeError, ValueError):
            pass
        if code is None and re.search(r"error code:\s*1010\b", body, re.I):
            code = "1010"
    except (OSError, AttributeError):
        pass
    finally:
        error.close()
    message = f"LLM API вернул HTTP {error.code}"
    if code:
        message += f" (код: {code})"
    if code in {"model_permission_blocked_org", "model_permission_blocked_project", "permissions_error"}:
        message += "; проверьте разрешение модели в настройках организации/проекта Groq"
    elif code == "1010":
        message += "; HTTP-клиент отклонён защитой API"
    return message


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
        headers={**HTTP_HEADERS, "Authorization": "Bearer " + settings.llm_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout) as response:
            raw = json.loads(response.read())
        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content, parse_constant=_reject_constant)
    except urllib.error.HTTPError as error:
        raise LLMUnavailable(_http_failure(error)) from None
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError):
        raise LLMUnavailable("LLM недоступна или вернула некорректный JSON") from None
    if not isinstance(parsed, dict) or parsed.get("error"):
        raise LLMUnavailable("LLM не вернула объект извлечённых полей")
    return parsed
