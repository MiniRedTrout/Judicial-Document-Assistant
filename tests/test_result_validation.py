import unittest
from app.services.pdf_result_mapper import map_pdf_result
from app.services.xml_result_mapper import map_xml_result

class ValidationTests(unittest.TestCase):
    def pdf(self, **overrides):
        fields={'тип_документа':'Судебный приказ','фио':'Иванов Иван','дело_номер':'2-1/2026',
                'дело_дата':'2026-01-02','дз_осн':'0'}
        fields.update(overrides)
        return map_pdf_result(fields,'test.pdf')

    def xml(self, **overrides):
        fields={'DocType2':'Постановление о возбуждении','DocDate':'2026-01-02',
                'DbtrName':'Иванов Иван','IpNo':'001/26','IdDocNo':'2-1',
                'IdDocDate':'2026-01-01','IdDebtSum':'0'}
        fields.update(overrides)
        return map_xml_result(fields,'test.xml')

    def test_valid_pdf_optional_fields_do_not_block(self):
        result=self.pdf()
        self.assertFalse(result.analysis.requires_review)
        self.assertEqual(result.analysis.review_reasons,[])
        self.assertIn('паспорт',result.analysis.missing_fields)

    def test_valid_xml_zero_total_optional_penalty(self):
        self.assertFalse(self.xml(rub_peni=None).analysis.requires_review)

    def test_missing_required_whitespace(self):
        for result in (self.pdf(фио='   '),self.xml(IpNo='')):
            self.assertTrue(result.analysis.requires_review)
            self.assertTrue(any('обязательные поля' in s for s in result.analysis.review_reasons))

    def test_invalid_optional_date_still_requires_review(self):
        self.assertTrue(self.pdf(дата_рождения='2026-99-01').analysis.requires_review)

    def test_negative_amount_and_reversed_period(self):
        result=self.pdf(дз_осн='-1',период_дз_начало='2026-02-01',период_дз_оконч='2026-01-01')
        self.assertTrue(any('Отрицательная' in s for s in result.analysis.review_reasons))
        self.assertTrue(any('Начало периода' in s for s in result.analysis.review_reasons))

    def test_missing_llm_does_not_claim_model_extraction(self):
        result=map_pdf_result({},'test.pdf',errors=['LLM_API_KEY не настроен'])
        self.assertTrue(result.analysis.requires_review)
        self.assertIn('LLM_API_KEY не настроен', result.analysis.review_reasons)
        self.assertFalse(any('извлечены моделью' in s for s in result.analysis.review_reasons))

    def test_llm_error_is_not_hidden_by_complete_fields(self):
        fields={'тип_документа':'приказ','фио':'Имя','дело_номер':'1','дело_дата':'2026-01-01','дз_осн':'10'}
        self.assertTrue(map_pdf_result(fields,'test.pdf',errors=['LLM API вернул HTTP 429']).analysis.requires_review)

    def test_recheck_preserves_source_and_mail_status(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app.services import document_store as store
        from scripts.recheck_results import main
        fields={'тип_документа':'приказ','фио':'Имя','дело_номер':'1','дело_дата':'2026-01-01','дз_осн':'10'}
        with tempfile.TemporaryDirectory() as folder, patch.object(store,'DB_PATH',Path(folder)/'db.sqlite'):
            store.init_db()
            store.save_document({'document_id':'old','file_name':'original.pdf','file_type':'pdf'})
            store.save_document_result('old',{'llm_fields':fields,'extracted_text':'original text',
                'lawyer_review':{'needs_lawyer':True},'analysis':{'review_reasons':['Поля PDF извлечены моделью; требуется проверка сотрудником']}})
            store.update_document_status('old','REQUIRES_REVIEW','COMPLETED','old message',100)
            store.claim_mail_delivery('old')
            store.finish_mail_delivery('old','SENT',message_id='test-id')
            main()
            self.assertEqual(store.get_document('old')['status'],'COMPLETED')
            self.assertEqual(store.get_document_result('old')['extracted_text'],'original text')
            self.assertTrue(store.get_document_result('old')['lawyer_review']['needs_lawyer'])
            self.assertEqual(store.get_mail_status('old')['status'],'SENT')
            self.assertEqual(store.get_mail_status('old')['message_id'],'test-id')
