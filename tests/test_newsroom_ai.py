import gzip
import json
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
        self.assertIn(
            "'gemini-3.5-flash-lite'",
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

    def test_prompt_requires_publication_length(self):
        with patch(
            'newsroom.ai.GEMINI_API_KEY',
            'test-key',
        ), patch(
            'newsroom.ai.request',
            return_value=(
                200,
                {'Content-Type': 'application/json'},
                gemini_success_body(),
            ),
        ) as request_mock, patch(
            'newsroom.ai.time.sleep',
        ):
            ai.generate({'candidate': {}}, 'news')

        payload = request_mock.call_args.kwargs['data']
        prompt = payload['contents'][0]['parts'][0]['text']
        self.assertIn('at least 700 words', prompt)
        self.assertIn('complete newspaper-style article', prompt)
        self.assertEqual(
            8192,
            payload['generationConfig']['maxOutputTokens'],
        )


def gemini_success_body():
    article = {
        'title': 'Verified title',
        'excerpt': 'Verified excerpt',
        'category': 'World',
        'tags': ['uganda'],
        'content_html': '<p>body</p>',
        'image_query': 'Kampala parliament',
        'image_caption': 'Caption',
        'image_alt': 'Alt',
        'source_credit': 'Example',
    }
    return json.dumps({
        'candidates': [{
            'content': {
                'parts': [{'text': json.dumps(article)}],
            },
        }],
    }).encode('utf-8')


def gemini_error_body(code, message, status_name):
    return json.dumps({
        'error': {
            'code': code,
            'message': message,
            'status': status_name,
        },
    }).encode('utf-8')


class GeminiRetryTests(unittest.TestCase):

    def test_retries_503_then_succeeds(self):
        responses = [
            (
                503,
                {'Content-Type': 'application/json'},
                gemini_error_body(
                    503,
                    'This model is currently experiencing high demand.',
                    'UNAVAILABLE',
                ),
            ),
            (
                200,
                {'Content-Type': 'application/json'},
                gemini_success_body(),
            ),
        ]
        with patch(
            'newsroom.ai.GEMINI_API_KEY',
            'test-key',
        ), patch(
            'newsroom.ai.request',
            side_effect=responses,
        ) as request_mock, patch(
            'newsroom.ai.time.sleep',
        ) as sleep_mock:
            article = ai.generate({'candidate': {}}, 'news')

        self.assertEqual('Verified title', article['title'])
        self.assertEqual(2, request_mock.call_count)
        sleep_mock.assert_called_once_with(2)

    def test_retries_429_then_succeeds(self):
        responses = [
            (
                429,
                {'Content-Type': 'application/json'},
                gemini_error_body(
                    429,
                    'Resource exhausted',
                    'RESOURCE_EXHAUSTED',
                ),
            ),
            (
                200,
                {'Content-Type': 'application/json'},
                gemini_success_body(),
            ),
        ]
        with patch(
            'newsroom.ai.GEMINI_API_KEY',
            'test-key',
        ), patch(
            'newsroom.ai.request',
            side_effect=responses,
        ) as request_mock, patch(
            'newsroom.ai.time.sleep',
        ) as sleep_mock:
            article = ai.generate({'candidate': {}}, 'news')

        self.assertEqual('Verified title', article['title'])
        self.assertEqual(2, request_mock.call_count)
        sleep_mock.assert_called_once_with(2)

    def test_repeated_503_fails_after_bounded_retries(self):
        unavailable = (
            503,
            {'Content-Type': 'application/json'},
            gemini_error_body(
                503,
                'This model is currently experiencing high demand.',
                'UNAVAILABLE',
            ),
        )
        with patch(
            'newsroom.ai.GEMINI_API_KEY',
            'test-key',
        ), patch(
            'newsroom.ai.GEMINI_MODEL',
            'gemini-3.8-flash',
        ), patch(
            'newsroom.ai.GEMINI_FALLBACK_MODEL',
            'gemini-3.8-flash',
        ), patch(
            'newsroom.ai.request',
            return_value=unavailable,
        ) as request_mock, patch(
            'newsroom.ai.time.sleep',
        ) as sleep_mock:
            with self.assertRaises(RuntimeError) as caught:
                ai.generate({'candidate': {}}, 'news')

        message = str(caught.exception)
        self.assertIn('temporarily unavailable', message)
        self.assertIn('503', message)
        self.assertEqual(ai.MAX_ATTEMPTS, request_mock.call_count)
        self.assertEqual(ai.MAX_ATTEMPTS - 1, sleep_mock.call_count)
        self.assertEqual(
            [((2,),), ((4,),), ((8,),)],
            sleep_mock.call_args_list,
        )

    def test_404_fails_without_retrying(self):
        payload = gemini_error_body(
            404,
            'models/gemini-2.5-flash is not found for API version v1beta',
            'NOT_FOUND',
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
        ) as request_mock, patch(
            'newsroom.ai.time.sleep',
        ) as sleep_mock:
            with self.assertRaises(RuntimeError) as caught:
                ai.generate({'candidate': {}}, 'news')

        self.assertIn('Gemini 404', str(caught.exception))
        self.assertEqual(1, request_mock.call_count)
        sleep_mock.assert_not_called()


def requested_model(call):
    url = call.args[0] if call.args else call.kwargs.get('url', '')
    return url.split('/models/', 1)[-1].split(':', 1)[0]


class GeminiFallbackTests(unittest.TestCase):

    def test_primary_succeeds_without_fallback(self):
        with patch(
            'newsroom.ai.GEMINI_API_KEY',
            'test-key',
        ), patch(
            'newsroom.ai.GEMINI_MODEL',
            'gemini-3.8-flash',
        ), patch(
            'newsroom.ai.GEMINI_FALLBACK_MODEL',
            'gemini-3.5-flash-lite',
        ), patch(
            'newsroom.ai.request',
            return_value=(
                200,
                {'Content-Type': 'application/json'},
                gemini_success_body(),
            ),
        ) as request_mock, patch(
            'newsroom.ai.time.sleep',
        ) as sleep_mock:
            article = ai.generate({'candidate': {}}, 'news')

        self.assertEqual('Verified title', article['title'])
        self.assertEqual(1, request_mock.call_count)
        self.assertEqual(
            'gemini-3.8-flash',
            requested_model(request_mock.call_args_list[0]),
        )
        sleep_mock.assert_not_called()

    def test_primary_503s_then_fallback_succeeds(self):
        unavailable = (
            503,
            {'Content-Type': 'application/json'},
            gemini_error_body(
                503,
                'This model is currently experiencing high demand.',
                'UNAVAILABLE',
            ),
        )
        responses = [unavailable] * ai.MAX_ATTEMPTS + [(
            200,
            {'Content-Type': 'application/json'},
            gemini_success_body(),
        )]
        with patch(
            'newsroom.ai.GEMINI_API_KEY',
            'test-key',
        ), patch(
            'newsroom.ai.GEMINI_MODEL',
            'gemini-3.8-flash',
        ), patch(
            'newsroom.ai.GEMINI_FALLBACK_MODEL',
            'gemini-3.5-flash-lite',
        ), patch(
            'newsroom.ai.request',
            side_effect=responses,
        ) as request_mock, patch(
            'newsroom.ai.time.sleep',
        ):
            article = ai.generate({'candidate': {}}, 'news')

        self.assertEqual('Verified title', article['title'])
        self.assertEqual(ai.MAX_ATTEMPTS + 1, request_mock.call_count)
        models = [
            requested_model(call)
            for call in request_mock.call_args_list
        ]
        self.assertEqual(
            ['gemini-3.8-flash'] * ai.MAX_ATTEMPTS,
            models[:-1],
        )
        self.assertEqual('gemini-3.5-flash-lite', models[-1])

    def test_primary_429s_then_fallback_succeeds(self):
        exhausted = (
            429,
            {'Content-Type': 'application/json'},
            gemini_error_body(
                429,
                'Resource exhausted',
                'RESOURCE_EXHAUSTED',
            ),
        )
        responses = [exhausted] * ai.MAX_ATTEMPTS + [(
            200,
            {'Content-Type': 'application/json'},
            gemini_success_body(),
        )]
        with patch(
            'newsroom.ai.GEMINI_API_KEY',
            'test-key',
        ), patch(
            'newsroom.ai.GEMINI_MODEL',
            'gemini-3.8-flash',
        ), patch(
            'newsroom.ai.GEMINI_FALLBACK_MODEL',
            'gemini-3.5-flash-lite',
        ), patch(
            'newsroom.ai.request',
            side_effect=responses,
        ) as request_mock, patch(
            'newsroom.ai.time.sleep',
        ):
            article = ai.generate({'candidate': {}}, 'news')

        self.assertEqual('Verified title', article['title'])
        self.assertEqual(ai.MAX_ATTEMPTS + 1, request_mock.call_count)
        self.assertEqual(
            'gemini-3.5-flash-lite',
            requested_model(request_mock.call_args_list[-1]),
        )

    def test_primary_404_does_not_invoke_fallback(self):
        payload = gemini_error_body(
            404,
            'models/gemini-3.8-flash is not found for API version v1beta',
            'NOT_FOUND',
        )
        with patch(
            'newsroom.ai.GEMINI_API_KEY',
            'test-key',
        ), patch(
            'newsroom.ai.GEMINI_MODEL',
            'gemini-3.8-flash',
        ), patch(
            'newsroom.ai.GEMINI_FALLBACK_MODEL',
            'gemini-3.5-flash-lite',
        ), patch(
            'newsroom.ai.request',
            return_value=(
                404,
                {'Content-Type': 'application/json'},
                payload,
            ),
        ) as request_mock, patch(
            'newsroom.ai.time.sleep',
        ) as sleep_mock:
            with self.assertRaises(RuntimeError) as caught:
                ai.generate({'candidate': {}}, 'news')

        self.assertIn('Gemini 404', str(caught.exception))
        self.assertEqual(1, request_mock.call_count)
        self.assertEqual(
            'gemini-3.8-flash',
            requested_model(request_mock.call_args_list[0]),
        )
        sleep_mock.assert_not_called()

    def test_both_primary_and_fallback_fail(self):
        unavailable = (
            503,
            {'Content-Type': 'application/json'},
            gemini_error_body(
                503,
                'This model is currently experiencing high demand.',
                'UNAVAILABLE',
            ),
        )
        with patch(
            'newsroom.ai.GEMINI_API_KEY',
            'test-key',
        ), patch(
            'newsroom.ai.GEMINI_MODEL',
            'gemini-3.8-flash',
        ), patch(
            'newsroom.ai.GEMINI_FALLBACK_MODEL',
            'gemini-3.5-flash-lite',
        ), patch(
            'newsroom.ai.request',
            return_value=unavailable,
        ) as request_mock, patch(
            'newsroom.ai.time.sleep',
        ) as sleep_mock:
            with self.assertRaises(RuntimeError) as caught:
                ai.generate({'candidate': {}}, 'news')

        message = str(caught.exception)
        self.assertIn('gemini-3.8-flash', message)
        self.assertIn('gemini-3.5-flash-lite', message)
        self.assertIn('temporarily unavailable', message)
        self.assertEqual(ai.MAX_ATTEMPTS * 2, request_mock.call_count)
        self.assertEqual((ai.MAX_ATTEMPTS - 1) * 2, sleep_mock.call_count)
        models = [
            requested_model(call)
            for call in request_mock.call_args_list
        ]
        self.assertEqual(
            ['gemini-3.8-flash'] * ai.MAX_ATTEMPTS
            + ['gemini-3.5-flash-lite'] * ai.MAX_ATTEMPTS,
            models,
        )


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
