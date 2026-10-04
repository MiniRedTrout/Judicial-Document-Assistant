from fastapi import APIRouter, HTTPException
from app.services.document_store import get_document, get_mail_status
from app.services.lawyer_mail import send_document_to_lawyer

router = APIRouter(prefix="/api/documents", tags=["Lawyer"])


@router.post("/{document_id}/send-to-lawyer")
def send_to_lawyer(document_id: str):
    if get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    try:
        result = send_document_to_lawyer(document_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    if result["status"] == "ERROR":
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/{document_id}/mail-status")
def mail_status(document_id: str):
    if get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return get_mail_status(document_id)
