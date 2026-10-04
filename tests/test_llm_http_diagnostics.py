import io
import json
import unittest
import urllib.error
from types import SimpleNamespace
from unittest.mock import patch
from app.integration_settings import settings
from app.services.integrations.llm import extract_fields, LLMUnavailable


class LlmHttpDiagnosticsTests(unittest.TestCase):
    def request_with_error(self, body, status=403):
        error = urllib.error.HTTPError('https://api.example.test', status, 'Denied', {}, io.BytesIO(body))
        with patch.object(settings, 'llm_key', 'test-key'), patch('urllib.request.urlopen', side_effect=error) as transport:
            with self.assertRaises(LLMUnavailable) as caught:
                extract_fields(SimpleNamespace(text='Вымышленный документ'))
        self.assertEqual(transport.call_args.args[0].get_header('User-agent'), 'DeloDocumentAssistant/1.0')
        return str(caught.exception)

    def test_model_permission_error_shows_code_not_raw_response(self):
        body = json.dumps({'error': {'code': 'model_permission_blocked_project',
                                    'message': 'secret-input-and-key'}}).encode()
        message = self.request_with_error(body)
        self.assertIn('model_permission_blocked_project', message)
        self.assertIn('разрешение модели', message)
        self.assertNotIn('secret-input-and-key', message)

    def test_http_client_block_has_specific_code(self):
        message = self.request_with_error(b'error code: 1010')
        self.assertIn('1010', message)

    def test_unknown_response_is_not_exposed(self):
        for body in [b'<html>private-proxy-details</html>',
                     b'{"error":{"code":"gsk_private-secret","message":"private-proxy-details"}}',
                     b'{"error":{"code":["untrusted"]}}']:
            with self.subTest(body=body):
                message = self.request_with_error(body)
                self.assertEqual(message, 'LLM API вернул HTTP 403')
