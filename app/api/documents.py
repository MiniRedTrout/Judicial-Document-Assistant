import logging
import sqlite3
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    UploadFile,
)

from app.schemas.document import (
    BatchUploadError,
    BatchUploadResponse,
    DocumentListItem,
    DocumentResponse,
    DocumentStatusResponse,
    UploadResponse,
)
from app.services.document_processor import process_document_background
from app.services.document_store import (
    get_document,
    get_document_result,
    get_documents,
    save_document,
)
from app.services.storage import save_uploaded_file


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)

ALLOWED_EXTENSIONS = {".pdf", ".xml"}


def _enqueue_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
) -> UploadResponse:
    """
    Проверяет и сохраняет файл, регистрирует документ
    и добавляет его обработку в фоновые задачи.
    """
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Файл не имеет имени",
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только PDF и XML файлы",
        )

    document_id, file_path = save_uploaded_file(file)
    file_type = extension[1:]

    document = {
        "document_id": document_id,
        "file_name": file.filename,
        "file_type": file_type,
        "file_path": file_path,
        "status": "UPLOADED",
        "stage": "UPLOADED",
        "message": "Файл успешно загружен",
        "progress": 0,
        "error": None,
    }

    try:
        save_document(document)
    except (sqlite3.Error, OSError):
        # Не оставляем файл без записи, если регистрация в базе не удалась.
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError:
            logger.exception("Не удалось удалить незарегистрированный файл")
        logger.exception("Не удалось зарегистрировать документ в базе")
        raise HTTPException(
            status_code=503,
            detail="Не удалось сохранить запись документа. Повторите загрузку.",
        )

    background_tasks.add_task(
        process_document_background,
        document_id,
        file_path,
        file_type,
    )

    logger.info(
        "Документ принят: id=%s, file=%s",
        document_id,
        file.filename,
    )

    return UploadResponse(
        document_id=document_id,
        file_name=file.filename,
        file_type=file_type,
        status="UPLOADED",
    )


@router.get(
    "",
    response_model=list[DocumentListItem],
)
async def list_documents():
    """
    Список документов для фронтенда.
    """
    return [
        DocumentListItem(
            document_id=document["document_id"],
            file_name=document["file_name"],
            file_type=document["file_type"],
            status=document["status"],
            stage=document["stage"],
            message=document["message"],
            progress=document["progress"],
            error=document.get("error"),
        )
        for document in get_documents()
    ]


@router.post(
    "/upload",
    status_code=202,
    response_model=UploadResponse,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Загрузка одного документа.
    """
    return _enqueue_document(file, background_tasks)


@router.post(
    "/upload-batch",
    status_code=202,
    response_model=BatchUploadResponse,
)
async def upload_documents_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    """
    Загрузка нескольких документов.

    Неподдерживаемые файлы попадают в errors.
    Остальные принимаются и обрабатываются.
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Не передано ни одного файла",
        )

    accepted: list[UploadResponse] = []
    errors: list[BatchUploadError] = []

    for file in files:
        try:
            uploaded = _enqueue_document(
                file=file,
                background_tasks=background_tasks,
            )
            accepted.append(uploaded)

        except HTTPException as error:
            errors.append(
                BatchUploadError(
                    file_name=file.filename,
                    error=str(error.detail),
                )
            )

        except OSError:
            logger.exception(
                "Не удалось сохранить файл: %s",
                file.filename,
            )

            errors.append(
                BatchUploadError(
                    file_name=file.filename,
                    error="Не удалось сохранить файл",
                )
            )

    if not accepted:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Ни один файл не принят",
                "errors": [
                    error.model_dump()
                    for error in errors
                ],
            },
        )

    return BatchUploadResponse(
        documents=accepted,
        errors=errors,
    )


@router.get(
    "/{document_id}/result",
)
async def get_document_result_by_id(
    document_id: str,
):
    document = get_document(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Документ не найден",
        )

    result = get_document_result(document_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Результат обработки ещё не готов",
        )

    return result


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
)
async def get_document_status(
    document_id: str,
):
    document = get_document(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Документ не найден",
        )

    return DocumentStatusResponse(
        document_id=document["document_id"],
        status=document["status"],
        stage=document["stage"],
        message=document["message"],
        progress=document["progress"],
        error=document.get("error"),
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
async def get_document_by_id(
    document_id: str,
):
    document = get_document(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Документ не найден",
        )

    return DocumentResponse(
        document_id=document["document_id"],
        file_name=document["file_name"],
        file_type=document["file_type"],
        file_path=document["file_path"],
        status=document["status"],
    )
