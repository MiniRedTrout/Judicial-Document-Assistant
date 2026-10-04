"""Отправка сохранённого результата с защитой от повторного нажатия."""
import logging

from app.services import document_store as store
from app.services.integrations.mailer import build_message, send_message

logger = logging.getLogger(__name__)


def send_document_to_lawyer(document_id: str) -> dict:
    document = store.get_document(document_id)
    if document is None:
        raise ValueError("Документ не найден")
    result = store.get_document_result(document_id)
    if not result:
        raise ValueError("Результат обработки ещё не готов")
    review = result.get("lawyer_review", {})
    if not review.get("needs_lawyer"):
        raise ValueError("Документ не отобран для юриста")
    if not store.claim_mail_delivery(document_id):
        return store.get_mail_status(document_id)
    try:
        message = build_message(document, review)
        send_message(message)
    except Exception:
        logger.exception("Почтовая отправка не завершилась для документа %s", document_id)
        # Не возвращаем исключение SMTP клиенту: в нём могут быть реквизиты сервера.
        store.finish_mail_delivery(document_id, "ERROR", error="Письмо не отправлено. Проверьте настройки и журнал сервера.")
    else:
        store.finish_mail_delivery(document_id, "SENT", message_id=message["Message-ID"])
    return store.get_mail_status(document_id)
