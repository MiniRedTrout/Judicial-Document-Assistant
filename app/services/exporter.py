"""CSV по двум исходным шаблонам хакатона. Идентификаторы остаются текстом."""
import csv
import io
from app.services.document_store import get_document_result

OCR_COLUMNS = 'тип документа,Файл,улица,дом,кв,фамилия,имя,отчетство,фио,дата рождения,паспорт,снилс,инн,дело_номер,дело_дата,период_дз_начало,период_дз_оконч,дз_осн,дз_пени,дз_пошлина,соответчики_кол-во,соответчики_фио'.split(',')
XML_COLUMNS = 'FileName,DocType,DocType2,DebtorType,DocDate,IdDebtText,IdDocNo,IdDocDate,IdDeloNo,IdDeloDate,IdDebtSum,IpNo,IdType,DbtrAdr,street,dom,kv,DbtrName,date_start,date_end,rub_deb,rub_peni,rub_poshlina,rub_post'.split(',')
OCR_PATHS = ['document.document_type_2', 'document.file_name', 'address.street', 'address.dom', 'address.kv', 'debtor.last_name', 'debtor.first_name', 'debtor.middle_name', 'debtor.full_name', 'debtor.birth_date', 'debtor.passport', 'debtor.snils', 'debtor.inn', 'case.number', 'case.case_date', 'debt.period_start', 'debt.period_end', 'debt.principal', 'debt.penalty', 'debt.state_duty', 'co_defendants.count', 'co_defendants.names']

def value_at(result, path):
    value = result
    for part in path.split('.'):
        value = value.get(part) if isinstance(value, dict) else None
    return value

def safe_cell(value):
    if isinstance(value, list):
        value = '; '.join(str(item) for item in value)
    if value is None or str(value).strip() == '':
        return 'НЕ ИЗВЛЕЧЕНО'
    text = str(value)
    # CSV, открытый в Excel, не должен исполнять содержимое документов как формулы.
    if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
        text = "'" + text
    return text

def export_csv(documents, kind):
    columns = OCR_COLUMNS if kind == 'pdf' else XML_COLUMNS
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(columns)
    count = 0
    for document in documents:
        if document['file_type'].lower() != kind or document['stage'] != 'COMPLETED':
            continue
        result = get_document_result(document['document_id'])
        if not result or document['stage'] != 'COMPLETED':
            continue
        if kind == 'pdf':
            values = [value_at(result, path) for path in OCR_PATHS]
        else:
            fields = result.get('xml_fields', {})
            values = [document['file_name'] if col == 'FileName' else fields.get(col) for col in columns]
        writer.writerow([safe_cell(value) for value in values])
        count += 1
    return stream.getvalue().encode('utf-8-sig'), count
