import gzip
import os
import unittest
from unittest.mock import patch

os.environ.setdefault(
    'SUPABASE_URL',
    'https://example.supabase.co',
)
os.environ.setdefault(
    'SUPABASE_SERVICE_ROLE_KEY',
    'dummy',
)

from newsroom import ai
from newsroom.http import decode_body


class GeminiIntegrationTests(unittest.TestCase):

    def test_generate_url_uses_configured_flash_model(self):
        url = ai.generate_url(
            api_key='test-key',
            model='gemini-3.8-flash',
        )
        self.assertIn(
            '/v1beta/models/gemini-3.8-flash:generateContent',
            url,
        )
        self.assertIn('key=test-key', url)
        self.assertNotIn('models/models/', url)

    def test_generate_url_strips_models_prefix(self):
        url = ai.generate_url(
            api_key='test-key',
            model='models/gemini-3.8-flash',
        )
        self.assertIn(
            '/v1beta/models/gemini-3.8-flash:generateContent',
            url,
        )
        self.assertNotIn('models/models/', url)

    def test_default_model_is_current_stable_flash(self):
        import inspect
        from newsroom import config as newsroom_config

        source = inspect.getsource(newsroom_config)
        self.assertIn(
            "'gemini-3.8-flash'",
            source,
        )

    def test_generate_raises_readable_gemini_error(self):
        payload = (
            b'{"error":{"code":404,"message":'
            b'"models/gemini-2.5-flash is not found for API version v1beta",'
            b'"status":"NOT_FOUND"}}'
        )

        with patch(
            'newsroom.ai.GEMINI_API_KEY',
            'test-key',
        ), patch(
            'newsroom.ai.request',
            return_value=(
                404,
                {'Content-Type': 'application/json'},
                payload,
            ),
        ):
            with self.assertRaises(RuntimeError) as caught:
                ai.generate({'candidate': {}}, 'news')

        message = str(caught.exception)
        self.assertIn('Gemini 404', message)
        self.assertIn('not found', message.lower())
        self.assertNotIn('\x1f\x8b', message)


class GzipDecodeTests(unittest.TestCase):

    def test_decode_body_handles_gzip_without_header(self):
        original = b'{"message":"column newsroom_runs.error_message does not exist"}'
        compressed = gzip.compress(original)
        self.assertEqual(
            original,
            decode_body(compressed, {}),
        )

    def test_decode_body_handles_gzip_header(self):
        original = b'{"error":"invalid json"}'
        compressed = gzip.compress(original)
        self.assertEqual(
            original,
            decode_body(
                compressed,
                {'Content-Encoding': 'gzip'},
            ),
        )


class SupabaseErrorReportingTests(unittest.TestCase):

    def test_rest_decodes_gzip_error_body(self):
        from newsroom import supabase

        original = b'{"message":"column newsroom_runs.error_message does not exist"}'
        compressed = gzip.compress(original)

        with patch(
            'newsroom.supabase.request',
            return_value=(
                400,
                {'Content-Encoding': 'gzip'},
                compressed,
            ),
        ):
            with self.assertRaises(RuntimeError) as caught:
                supabase.rest('newsroom_runs', method='POST', data={})

        message = str(caught.exception)
        self.assertIn('Supabase 400', message)
        self.assertIn('error_message', message)
        self.assertNotIn('\x1f\x8b', message)


if __name__ == '__main__':
    unittest.main()
