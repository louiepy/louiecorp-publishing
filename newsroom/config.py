import os

SITE_URL = os.getenv('SITE_URL', 'https://louiecorp.com').rstrip('/')
SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_SERVICE_ROLE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
MEDIA_WORKER_URL = os.getenv('MEDIA_WORKER_URL', 'https://louiecorp.louievolt.workers.dev').rstrip('/')
MEDIA_BOT_SECRET = os.environ.get('MEDIA_BOT_SECRET', '')
UNSPLASH_ACCESS_KEY = os.environ.get('UNSPLASH_ACCESS_KEY', '')
MAX_DAILY_AUTOMATED = int(os.getenv('MAX_DAILY_AUTOMATED', '3'))
AUTO_PUBLISH = os.getenv('AUTO_PUBLISH', 'false').lower() == 'true'
MIN_IMPORTANCE = int(os.getenv('MIN_IMPORTANCE', '68'))
MAX_SOURCES = int(os.getenv('MAX_SOURCES', '6'))
USER_AGENT = 'LouieCorp-Newsroom/1.0 (+https://louiecorp.com/editorial-policy.html)'

RSS_FEEDS = [
    ('Google News Uganda', 'https://news.google.com/rss/search?q=Uganda&hl=en-US&gl=UG&ceid=UG:en', 'uganda'),
    ('Google News Africa', 'https://news.google.com/rss/search?q=Africa&hl=en-US&gl=UG&ceid=UG:en', 'africa'),
    ('Google News World', 'https://news.google.com/rss/search?q=world+news&hl=en-US&gl=UG&ceid=UG:en', 'world'),
    ('Google News science', 'https://news.google.com/rss/search?q=science+research+space+biology+law+human+rights&hl=en-US&gl=UG&ceid=UG:en', 'knowledge'),
]

KNOWLEDGE_FIELDS = [
    'Law and legal systems', 'Human rights and public policy', 'Political science and governance',
    'Economics and development', 'Sociology and society', 'Psychology and human behaviour',
    'Biology and life sciences', 'Medicine and public health', 'Environmental science and climate',
    'Physics and astronomy', 'Space science', 'Computer science and artificial intelligence',
    'History and archaeology', 'International relations', 'Geography and urban studies',
    'Education and learning', 'Public administration', 'Philosophy and ethics'
]
