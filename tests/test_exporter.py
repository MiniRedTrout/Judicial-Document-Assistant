import csv
import io
import unittest
from unittest.mock import patch
from app.services.exporter import export_csv, OCR_COLUMNS, XML_COLUMNS, safe_cell

class ExportTests(unittest.TestCase):
    def doc(self, kind='pdf',stage='COMPLETED'):
        return dict(document_id='test', file_name='original.'+kind, file_type=kind, stage=stage)

    def test_pdf_template_validated_values_and_missing(self):
        result={'document':{'file_name':'original.pdf','document_type_2':'приказ'},'debtor':{'inn':'001234','middle_name':'Иванович'},'debt':{'principal':'0'},'co_defendants':{'names':['А','Б']}}
        with patch('app.services.exporter.get_document_result',return_value=result):
            content,count=export_csv([self.doc()], 'pdf')
        rows=list(csv.reader(io.StringIO(content.decode('utf-8-sig'))))
        self.assertEqual(rows[0],OCR_COLUMNS)
        self.assertEqual(count,1)
        self.assertEqual(rows[1][7],'Иванович')
        self.assertEqual(rows[1][12],'001234')
        self.assertEqual(rows[1][17],'0')
        self.assertEqual(rows[1][2],'НЕ ИЗВЛЕЧЕНО')
        self.assertEqual(rows[1][-1],'А; Б')

    def test_xml_original_filename_and_template(self):
        with patch('app.services.exporter.get_document_result',return_value={'xml_fields':{'FileName':'uuid.xml','DbtrName':'Имя','rub_deb':0}}):
            content,count=export_csv([self.doc('xml')], 'xml')
        rows=list(csv.reader(io.StringIO(content.decode('utf-8-sig'))))
        self.assertEqual(rows[0],XML_COLUMNS)
        self.assertEqual(rows[1][0],'original.xml')
        self.assertEqual(rows[1][20],'0')

    def test_omits_pending_failed_and_other_format(self):
        with patch('app.services.exporter.get_document_result') as read:
            content,count=export_csv([self.doc(stage='ERROR'),self.doc(stage='PROCESSING'),self.doc('xml')], 'pdf')
        self.assertEqual(count,0)
        read.assert_not_called()

    def test_csv_formula_protection(self):
        self.assertEqual(safe_cell(' =HYPERLINK("x")'), '\' =HYPERLINK("x")')
        self.assertEqual(safe_cell('@SUM(A1)'), "'@SUM(A1)")
        self.assertEqual(safe_cell(None),'НЕ ИЗВЛЕЧЕНО')
