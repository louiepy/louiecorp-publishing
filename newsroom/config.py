import os

SITE_URL = os.getenv('SITE_URL', 'https://louiecorp.com').rstrip('/')
SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_SERVICE_ROLE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.8-flash') or 'gemini-3.8-flash'
GEMINI_FALLBACK_MODEL = os.getenv('GEMINI_FALLBACK_MODEL', 'gemini-3.5-flash-lite') or 'gemini-3.5-flash-lite'
MEDIA_WORKER_URL = (os.getenv('MEDIA_WORKER_URL') or 'https://louiecorp.louievolt.workers.dev').strip().rstrip('/')
MEDIA_BOT_SECRET = os.environ.get('MEDIA_BOT_SECRET', '').strip()
UNSPLASH_ACCESS_KEY = os.environ.get('UNSPLASH_ACCESS_KEY', '')
MAX_DAILY_AUTOMATED = int(os.getenv('MAX_DAILY_AUTOMATED', '3'))
AUTO_PUBLISH = os.getenv('AUTO_PUBLISH', 'false').lower() == 'true'
MIN_IMPORTANCE = int(os.getenv('MIN_IMPORTANCE', '68'))
MAX_SOURCES = int(os.getenv('MAX_SOURCES', '6'))
USER_AGENT = 'LouieCorp-Newsroom/1.0 (+https://louiecorp.com/editorial-policy.html)'

RSS_FEEDS = [
    ('Google News Uganda', 'https://news.google.com/rss/search?q=Uganda&hl=en-US&gl=UG&ceid=UG:en', 'uganda'),
    ('Google News Kampala', 'https://news.google.com/rss/search?q=Kampala&hl=en-US&gl=UG&ceid=UG:en', 'uganda'),
    ('Google News Uganda government', 'https://news.google.com/rss/search?q=Uganda+government+OR+parliament+OR+Museveni&hl=en-US&gl=UG&ceid=UG:en', 'uganda'),
    ('Google News Uganda economy', 'https://news.google.com/rss/search?q=Uganda+court+OR+election+OR+economy&hl=en-US&gl=UG&ceid=UG:en', 'uganda'),
    ('Google News Monitor Uganda', 'https://news.google.com/rss/search?q=site:monitor.co.ug+Uganda&hl=en-US&gl=UG&ceid=UG:en', 'uganda'),
    ('Google News New Vision', 'https://news.google.com/rss/search?q=site:newvision.co.ug+Uganda&hl=en-US&gl=UG&ceid=UG:en', 'uganda'),
    ('Google News Nile Post', 'https://news.google.com/rss/search?q=site:nilepost.co.ug+Uganda&hl=en-US&gl=UG&ceid=UG:en', 'uganda'),
    ('Google News Independent Uganda', 'https://news.google.com/rss/search?q=site:independent.co.ug+Uganda&hl=en-US&gl=UG&ceid=UG:en', 'uganda'),
    ('Google News ChimpReports', 'https://news.google.com/rss/search?q=site:chimpreports.com+Uganda&hl=en-US&gl=UG&ceid=UG:en', 'uganda'),
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
