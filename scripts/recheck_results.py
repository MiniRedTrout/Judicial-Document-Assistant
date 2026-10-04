"""Пересчитывает проверки сохранённых результатов, не запускает OCR/LLM/SMTP.
Запуск из корня: python -m scripts.recheck_results
"""
from app.services import document_store as store
from app.services.xml_result_mapper import map_xml_result
from app.services.pdf_result_mapper import map_pdf_result
from app.services.document_processor import _finish_result


def main():
    store.init_db()
    updated = skipped = 0
    for document in store.get_documents():
        if document['stage'] != 'COMPLETED':
            skipped += 1
            continue
        identifier = document['document_id']
        result = store.get_document_result(identifier)
        kind = document['file_type'].lower()
        if not result:
            skipped += 1
            continue
        if kind == 'xml' and 'xml_fields' in result:
            mapped = map_xml_result(result['xml_fields'], document['file_name'])
        elif kind == 'pdf' and 'llm_fields' in result:
            fields = result['llm_fields']
            # Сохраняем ошибки вызова/ответа LLM, остальные проверки вычисляются заново.
            errors = [reason for reason in result.get('analysis', {}).get('review_reasons', [])
                      if 'LLM' in reason or 'Ответ модели' in reason]
            mapped = map_pdf_result(fields, document['file_name'], errors=errors)
        else:
            skipped += 1
            continue
        result.update(mapped.model_dump(mode='json'))
        store.save_document_result(identifier, result)
        _finish_result(identifier, result, kind.upper())
        updated += 1
    print(f'Обновлено результатов: {updated}; пропущено: {skipped}')


if __name__ == '__main__':
    main()
