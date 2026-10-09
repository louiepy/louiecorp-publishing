import os
import unittest
from unittest.mock import patch

os.environ.setdefault('SUPABASE_URL', 'https://example.supabase.co')
os.environ.setdefault('SUPABASE_SERVICE_ROLE_KEY', 'dummy')
os.environ.setdefault('MEDIA_WORKER_URL', 'https://example.worker.dev')
os.environ.setdefault('MEDIA_BOT_SECRET', 'dummy')

from newsroom import images


class MediaUploadAuthTests(unittest.TestCase):

    def test_cover_upload_sends_bearer_token(self):
        image = {'url': 'https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg'}
        with patch.object(images, 'MEDIA_BOT_SECRET', 'newsroom-secret'), patch.object(
            images, 'MEDIA_WORKER_URL', 'https://example.worker.dev'
        ), patch.object(
            images, 'request', return_value=(200, {}, b'{"ok":true}')
        ) as request_mock:
            url = images.upload(image, 'covers/newsroom-example.jpg')

        self.assertEqual(url, 'https://example.worker.dev/media/covers/newsroom-example.jpg')
        args, kwargs = request_mock.call_args
        self.assertEqual(args[0], 'https://example.worker.dev/bot-media/covers/newsroom-example.jpg')
        self.assertEqual(kwargs['method'], 'PUT')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer newsroom-secret')
        self.assertEqual(kwargs['headers']['X-Image-Source'], image['url'])

    def test_pdf_upload_sends_bearer_token(self):
        with patch.object(images, 'MEDIA_BOT_SECRET', 'newsroom-secret'), patch.object(
            images, 'MEDIA_WORKER_URL', 'https://example.worker.dev'
        ), patch.object(
            images, 'request', return_value=(200, {}, b'{"ok":true}')
        ) as request_mock:
            url = images.upload_pdf(b'%PDF-1.4 test', 'pdfs/newsroom-example.pdf')

        self.assertEqual(url, 'https://example.worker.dev/media/pdfs/newsroom-example.pdf')
        args, kwargs = request_mock.call_args
        self.assertEqual(args[0], 'https://example.worker.dev/bot-media/pdfs/newsroom-example.pdf')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer newsroom-secret')
        self.assertEqual(kwargs['headers']['Content-Type'], 'application/pdf')

    def test_cover_upload_surfaces_worker_auth_failure(self):
        image = {'url': 'https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg'}
        with patch.object(images, 'MEDIA_BOT_SECRET', 'newsroom-secret'), patch.object(
            images, 'request', return_value=(401, {}, b'{"error":"Bot authentication failed."}')
        ):
            with self.assertRaises(RuntimeError) as raised:
                images.upload(image, 'covers/newsroom-example.jpg')
        self.assertIn('Bot authentication failed.', str(raised.exception))

    def test_cover_upload_requires_local_secret(self):
        image = {'url': 'https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg'}
        with patch.object(images, 'MEDIA_BOT_SECRET', ''):
            with self.assertRaises(RuntimeError) as raised:
                images.upload(image, 'covers/newsroom-example.jpg')
        self.assertEqual(str(raised.exception), 'MEDIA_BOT_SECRET is not configured.')


    def test_cover_upload_retries_transient_worker_errors(self):
        image = {'url': 'https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg'}
        with patch.object(images, 'MEDIA_BOT_SECRET', 'newsroom-secret'), patch.object(
            images, 'MEDIA_WORKER_URL', 'https://example.worker.dev'
        ), patch.object(
            images, 'request',
            side_effect=[
                (503, {}, b'upstream unavailable'),
                (200, {}, b'{"ok":true}'),
            ],
        ) as request_mock, patch.object(images.time, 'sleep'):
            url = images.upload(image, 'covers/newsroom-example.jpg')
        self.assertEqual(url, 'https://example.worker.dev/media/covers/newsroom-example.jpg')
        self.assertEqual(request_mock.call_count, 2)

    def test_cover_upload_rejects_unapproved_hosts_before_worker_call(self):
        image = {'url': 'https://example.com/photo.jpg'}
        with patch.object(images, 'MEDIA_BOT_SECRET', 'newsroom-secret'), patch.object(
            images, 'request', return_value=(200, {}, b'{"ok":true}')
        ) as request_mock:
            with self.assertRaises(RuntimeError) as raised:
                images.upload(image, 'covers/newsroom-example.jpg')
        self.assertIn('approved Wikimedia or Unsplash host', str(raised.exception))
        self.assertEqual(request_mock.call_count, 0)

    def test_cover_upload_does_not_retry_permanent_validation_errors(self):
        image = {'url': 'https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg'}
        with patch.object(images, 'MEDIA_BOT_SECRET', 'newsroom-secret'), patch.object(
            images, 'request', return_value=(400, {}, b'{"error":"Image source is not an approved host."}')
        ) as request_mock:
            with self.assertRaises(RuntimeError):
                images.upload(image, 'covers/newsroom-example.jpg')
        self.assertEqual(request_mock.call_count, 1)


if __name__ == '__main__':
    unittest.main()
