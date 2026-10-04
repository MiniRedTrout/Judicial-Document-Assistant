"""SMTP-адаптер check-mail; нет встроенных адресов или паролей."""
import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from app.integration_settings import settings


def build_message(document: dict, review: dict) -> EmailMessage:
    path = Path(document["file_path"])
    if not path.is_file():
        raise FileNotFoundError("Исходный документ отсутствует; письмо не отправлено")
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = settings.mail_lawyer
    message["Subject"] = "Судебный акт на проверку: " + document["file_name"]
    message["Message-ID"] = make_msgid()
    lines = ["Документ требует проверки юриста.", "Файл: " + document["file_name"], ""]
    for match in review["matches"]:
        page = f'стр. {match["page"]}' if match["page"] is not None else "страница не указана"
        lines.extend([f'{match["phrase"]} ({page})', match["snippet"], ""])
    if review.get("requires_context_review"):
        lines.append("Отбор предварительный: требуется проверить контекст формулировок.")
    message.set_content("\n".join(lines))
    mime = mimetypes.guess_type(document["file_name"])[0] or "application/octet-stream"
    major, minor = mime.split("/", 1)
    message.add_attachment(path.read_bytes(), maintype=major, subtype=minor,
                           filename=document["file_name"])
    return message


def send_message(message: EmailMessage) -> None:
    if not settings.mail_enabled:
        raise RuntimeError("Почтовая отправка отключена (MAIL_ENABLED=false)")
    if not all((settings.mail_host, settings.mail_from, settings.mail_lawyer)):
        raise RuntimeError("Не настроены SMTP, отправитель или MAIL_LAWYER")
    if settings.mail_security not in ("ssl", "starttls", "none"):
        raise RuntimeError("MAIL_SECURITY должна быть ssl, starttls или none")
    if settings.mail_security == "ssl":
        server = smtplib.SMTP_SSL(settings.mail_host, settings.mail_port,
                                 timeout=settings.mail_timeout, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(settings.mail_host, settings.mail_port, timeout=settings.mail_timeout)
    with server:
        if settings.mail_security == "starttls":
            server.starttls(context=ssl.create_default_context())
        if settings.mail_user:
            if not settings.mail_password:
                raise RuntimeError("Не настроен MAIL_PASS")
            server.login(settings.mail_user, settings.mail_password)
        refused = server.send_message(message)
        if refused:
            raise RuntimeError("SMTP не принял получателя")
