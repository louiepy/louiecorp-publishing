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
os.environ.setdefault(
    'MEDIA_WORKER_URL',
    'https://example.worker.dev',
)
os.environ.setdefault(
    'MEDIA_BOT_SECRET',
    'dummy',
)

from newsroom import main as newsroom_main


class MainFlowTests(unittest.TestCase):

    def test_rejects_bad_candidate_and_continues(self):
        run = {'id': 'run-1'}
        article = {
            'title': 'Verified title',
            'excerpt': 'Verified excerpt',
            'content_html': '<p>' + ('word ' * 560) + '</p>',
            'category': 'World',
            'image_query': 'Kampala parliament',
            'image_caption': 'Caption',
        }

        candidates = [
            {
                'title': 'Candidate one',
                'url': 'https://example.com/one',
                'description': 'desc',
                'track': 'news',
            },
            {
                'title': 'Candidate two',
                'url': 'https://example.com/two',
                'description': 'desc',
                'track': 'news',
            },
        ]

        sources_bad = [{
            'title': 'Only one',
            'url': 'https://pub1.example/article',
            'publisher': 'pub1.example',
            'retrieved_at': '2026-01-01T00:00:00+00:00',
            'text': 'x' * 300,
        }]

        sources_good = [
            {
                'title': 'One',
                'url': 'https://pub1.example/article',
                'publisher': 'pub1.example',
                'retrieved_at': '2026-01-01T00:00:00+00:00',
                'text': 'x' * 300,
            },
            {
                'title': 'Two',
                'url': 'https://pub2.example/article',
                'publisher': 'pub2.example',
                'retrieved_at': '2026-01-01T00:01:00+00:00',
                'text': 'y' * 300,
            },
        ]

        with patch(
            'newsroom.main.automated_today',
            return_value=[],
        ), patch(
            'newsroom.main.uganda_done_today',
            return_value=True,
        ), patch(
            'newsroom.main.candidate_is_eligible',
            side_effect=lambda candidate, *_args, **_kwargs: (
                candidate.setdefault(
                    'importance_score',
                    80,
                )
                or True
            ),
        ), patch(
            'newsroom.main.discover',
            return_value=candidates,
        ), patch(
            'newsroom.main.find_duplicate',
            return_value=None,
        ), patch(
            'newsroom.main.research',
            side_effect=[sources_bad, sources_good],
        ) as research_mock, patch(
            'newsroom.main.generate',
            return_value=article,
        ), patch(
            'newsroom.main.choose',
            return_value={
                'url': 'https://img.example/cover.jpg',
                'credit': 'Example',
                'license': 'CC',
                'caption': 'Caption',
            },
        ), patch(
            'newsroom.main.upload',
            return_value='https://cdn.example/cover.jpg',
        ), patch(
            'newsroom.main.category_id',
            return_value='cat-1',
        ), patch(
            'newsroom.main.find_author',
            return_value='author-1',
        ), patch(
            'newsroom.main.insert_article',
            return_value={'id': 'article-1', 'slug': 'verified-title'},
        ), patch(
            'newsroom.main.log_run',
            return_value=run,
        ), patch(
            'newsroom.main.log_candidate',
            return_value={'id': 'candidate-1'},
        ), patch(
            'newsroom.main.log_sources',
            return_value=[],
        ) as log_sources_mock, patch(
            'newsroom.supabase.rest',
            return_value=[],
        ):
            code = newsroom_main.main('news')

        self.assertEqual(0, code)
        self.assertEqual(2, research_mock.call_count)
        self.assertEqual(1, log_sources_mock.call_count)
        logged_sources = log_sources_mock.call_args[0][0]
        self.assertEqual(2, len(logged_sources))


if __name__ == '__main__':
    unittest.main()
