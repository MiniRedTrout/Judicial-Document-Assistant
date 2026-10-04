from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Response
from app.services.document_store import get_document, get_documents
from app.services.exporter import export_csv

router = APIRouter(prefix='/api/exports', tags=['Export'])

@router.get('/{kind}.csv')
def download_csv(kind: Literal['pdf', 'xml'], document_id: list[str] | None = Query(default=None)):
    documents = get_documents()
    if document_id is not None:
        documents = []
        for identifier in dict.fromkeys(document_id):
            document = get_document(identifier)
            if document is None:
                raise HTTPException(404, 'Документ не найден')
            documents.append(document)
    content, count = export_csv(documents, kind)
    if not count:
        raise HTTPException(409, 'Нет обработанных документов выбранного формата')
    return Response(content, media_type='text/csv; charset=utf-8', headers={
        'Content-Disposition': f'attachment; filename="{kind}_results.csv"',
        'Cache-Control': 'no-store',
    })
