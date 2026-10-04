"""Настройки новых интеграций. Секреты читаются из окружения, не из кода."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / ".env").is_file():
    try:
        from dotenv import load_dotenv
    except ImportError:
        raise RuntimeError("Для чтения .env установите python-dotenv") from None
    load_dotenv(ROOT / ".env", override=False)


def flag(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


@dataclass
class IntegrationSettings:
    llm_base: str = os.getenv("LLM_API_BASE", "https://api.cerebras.ai/v1")
    llm_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-oss-120b")
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "60"))
    llm_max_chars: int = int(os.getenv("LLM_MAX_CHARS", "60000"))
    llm_json_mode: bool = flag("LLM_JSON_MODE", True)
    mail_enabled: bool = flag("MAIL_ENABLED")
    mail_auto_send: bool = flag("MAIL_AUTO_SEND")
    # Правка J3: пробелы из .env не должны ломать подключение и авторизацию SMTP.
    mail_host: str = os.getenv("MAIL_SMTP_HOST", "smtp.mail.ru").strip()
    mail_port: int = int(os.getenv("MAIL_SMTP_PORT", "465"))
    mail_security: str = os.getenv("MAIL_SECURITY", "ssl").strip().lower()
    mail_user: str = os.getenv("MAIL_USER", "").strip()
    mail_password: str = os.getenv("MAIL_PASS", "").strip()
    mail_from: str = os.getenv("MAIL_FROM", os.getenv("MAIL_USER", "")).strip()
    mail_lawyer: str = os.getenv("MAIL_LAWYER", "").strip()
    mail_timeout: float = float(os.getenv("MAIL_TIMEOUT", "30"))


settings = IntegrationSettings()
