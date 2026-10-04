"""Регрессии для сумм и адреса в предоставленном OCR, без внешнего API."""
import unittest
from app.services.pdf_source_checks import check_pdf_source
from app.services.pdf_result_mapper import map_pdf_result

OCR = '''Должником по исполнительному документу является Пробников Савелий Викторович.
Адрес фактический: Тест,,2-й Проезд, 23,17.
Принять меры принудительного исполнения на сумму: 137327,10.
Задолженность по оплате за потребленную тепловую энергию
за период 04.01.2028 по 02.01.2033 в размере 85422,50
(отопление 78244,48 руб.; ГВС 7178,02 руб.); пени в размере 47904,60.
Адрес регистрации: Тест, ул. 2-й Проезд д: 23-17К4.
Паспорт: серия [не читается] 564951.'''


def fields():
    return {'тип_документа': 'судебный приказ', 'фио': 'Пробников Савелий Викторович',
            'дело_номер': '2-8416/2033', 'дело_дата': '2033-02-14',
            'дз_осн': '137327.10', 'дз_пени': '47904.60',
            'улица': '2-й Проезд', 'дом': '23-17К4', 'кв': None,
            'паспорт': '564951'}


class PdfSourceChecksTests(unittest.TestCase):
    def test_provided_ocr_corrects_total_and_address_with_review(self):
        original = fields()
        result = map_pdf_result(original, 'example.pdf', source_text=OCR)
        self.assertEqual(str(result.debt.principal), '85422.50')
        self.assertEqual((result.address.dom, result.address.kv), ('23', '17К4'))
        self.assertIsNone(result.debt.state_duty)
        self.assertIsNone(result.debtor.birth_date)
        self.assertTrue(result.analysis.requires_review)
        self.assertTrue(any('6 цифр' in reason for reason in result.analysis.review_reasons))
        self.assertEqual(original, fields(), 'Raw LLM response must remain unchanged')

    def test_already_correct_amount_is_kept(self):
        original = {'дз_осн': '85422.50'}
        checked, reasons = check_pdf_source(original, OCR)
        self.assertEqual(checked, original)
        self.assertEqual(reasons, [])

    def test_multiple_principals_are_not_resolved_by_order(self):
        text = OCR + ' Задолженность по оплате за потребленную воду в размере 12345,67.'
        checked, reasons = check_pdf_source({'дз_осн': '137327.10'}, text)
        self.assertEqual(checked['дз_осн'], '137327.10')
        self.assertTrue(reasons)

    def test_missing_principal_is_not_computed_from_total(self):
        checked, reasons = check_pdf_source({'дз_осн': None, 'дз_пошлина': None}, OCR)
        self.assertIsNone(checked['дз_осн'])
        self.assertIsNone(checked['дз_пошлина'])
        self.assertEqual(reasons, [])

    def test_hyphen_alone_does_not_split_house(self):
        original = {'дом': '23-17К4', 'улица': '2-й Проезд', 'кв': None}
        checked, reasons = check_pdf_source(original, 'Тест, ул. 2-й Проезд д: 23-17К4.')
        self.assertEqual(checked, original)
        self.assertTrue(reasons)

    def test_explicit_apartment_is_not_overwritten(self):
        original = {'дом': '23', 'кв': '17К4', 'улица': '2-й Проезд'}
        self.assertEqual(check_pdf_source(original, OCR), (original, []))

    def test_complete_passport_needs_no_incomplete_warning(self):
        original = fields()
        original.update({'паспорт': '8228 564951', 'дз_осн': '85422.50', 'дом': '23', 'кв': '17К4'})
        result = map_pdf_result(original, 'example.pdf', source_text=OCR)
        self.assertFalse(result.analysis.requires_review)

    def test_unrelated_amount_is_not_replaced(self):
        checked, reasons = check_pdf_source({'дз_осн': '123.45'}, OCR)
        self.assertEqual(checked['дз_осн'], '123.45')
        self.assertTrue(reasons)

    def test_negative_amount_is_not_read_as_positive_evidence(self):
        checked, reasons = check_pdf_source({'дз_осн': '137327.10'},
            'На сумму: 137327,10. Задолженность по оплате за потребленную воду в размере -85422,50.')
        self.assertEqual(checked['дз_осн'], '137327.10')
        self.assertEqual(reasons, [])

    def test_recheck_uses_saved_ocr_and_preserves_mail_and_raw_fields(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app.services import document_store as store
        from scripts.recheck_results import main
        with tempfile.TemporaryDirectory() as folder, patch.object(store, 'DB_PATH', Path(folder) / 'db.sqlite'):
            store.init_db()
            store.save_document({'document_id': 'saved', 'file_name': 'example.pdf', 'file_type': 'pdf'})
            store.save_document_result('saved', {'llm_fields': fields(), 'extracted_text': OCR,
                'analysis': {'review_reasons': []}, 'lawyer_review': {'needs_lawyer': True}})
            store.update_document_status('saved', 'COMPLETED', 'COMPLETED', 'Готово', 100)
            store.claim_mail_delivery('saved')
            store.finish_mail_delivery('saved', 'SENT', message_id='existing-message')
            main()
            result = store.get_document_result('saved')
            self.assertEqual(str(result['debt']['principal']), '85422.50')
            self.assertEqual(result['address']['kv'], '17К4')
            self.assertEqual(result['llm_fields'], fields())
            self.assertEqual(result['extracted_text'], OCR)
            self.assertTrue(result['lawyer_review']['needs_lawyer'])
            self.assertEqual(store.get_mail_status('saved')['message_id'], 'existing-message')
            self.assertEqual(store.get_document('saved')['status'], 'REQUIRES_REVIEW')
