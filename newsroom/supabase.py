import datetime as dt
import urllib.parse
from .config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
from .http import get_json, request

HEADERS = {
    'apikey': SUPABASE_SERVICE_ROLE_KEY,
    'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation'
}


def rest(table, query='', method='GET', data=None, headers=None):
    url = f'{SUPABASE_URL}/rest/v1/{table}' + (f'?{query}' if query else '')
    h = dict(HEADERS); h.update(headers or {})
    status, _, body = request(url, method=method, data=data, headers=h)
    if status >= 400:
        raise RuntimeError(f'Supabase {status}: {body.decode("utf-8", "replace")[:1000]}')
    return [] if not body else __import__('json').loads(body.decode('utf-8', 'replace'))


def today_window():
    now = dt.datetime.now(dt.timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return start, end


def automated_today():
    start, end = today_window()
    q = 'select=*&created_at=gte.' + urllib.parse.quote(start, safe='') + '&created_at=lt.' + urllib.parse.quote(end, safe='') + '&limit=100'
    return rest('newsroom_runs', q)


def articles_today():
    start, end = today_window()
    q = 'select=id,title,slug,content,excerpt,cover_image_url,published_at,status,created_at&created_at=gte.' + urllib.parse.quote(start, safe='') + '&created_at=lt.' + urllib.parse.quote(end, safe='') + '&limit=100'
    return rest('articles', q)


def find_author():
    q = 'slug=eq.sentongo-r-louis&select=id,name,slug&limit=1'
    rows = rest('authors', q)
    if rows: return rows[0]['id']
    rows = rest('authors', method='POST', data={'name':'Sentongo. R. Louis','slug':'sentongo-r-louis','title':'Writer, Researcher and Analyst'})
    return rows[0]['id']


def category_id(name):
    slug = name.lower().strip().replace('&','and').replace(' ','-')
    q = 'slug=eq.' + urllib.parse.quote(slug, safe='') + '&select=id,name&limit=1'
    rows = rest('categories', q)
    if rows: return rows[0]['id']
    rows = rest('categories', method='POST', data={'name':name,'slug':slug})
    return rows[0]['id']


def find_duplicate(title, urls):
    q = 'select=id,title,slug,source_url,created_at&order=created_at.desc&limit=100'
    rows = rest('articles', q)
    import re
    def norm(s): return set(re.findall(r'[a-z0-9]{4,}', (s or '').lower()))
    target = norm(title)
    for row in rows:
        other = norm(row.get('title'))
        if target and other:
            overlap = len(target & other) / max(1, len(target | other))
            if overlap >= 0.68: return row
        if row.get('source_url') and row['source_url'] in urls: return row
    return None


def insert_article(article):
    return rest('articles', method='POST', data=article)[0]


def articles_by_ids(ids):
    values = [str(item) for item in ids if item]
    if not values:
        return []
    quoted = ','.join(values)
    try:
        return rest('articles', 'id=in.(' + quoted + ')&select=id,title,excerpt,content,newsroom_track,status,categories(name)')
    except RuntimeError:
        return rest('articles', 'id=in.(' + quoted + ')&select=id,title,excerpt,content,newsroom_track,status')


def uganda_done_today(runs=None):
    from .rank import is_uganda
    rows = runs if runs is not None else automated_today()
    ids = [r.get('article_id') for r in rows if r.get('success') and r.get('article_id')]
    if not ids:
        return False
    articles = {row.get('id'): row for row in articles_by_ids(ids)}
    candidates = []
    try:
        quoted = ','.join(str(item) for item in ids)
        candidates = rest('newsroom_candidates', 'article_id=in.(' + quoted + ')&select=article_id,title,url,track')
    except Exception:
        candidates = []
    cand_by_article = {row.get('article_id'): row for row in candidates}
    for article_id in ids:
        article = articles.get(article_id) or {}
        candidate = cand_by_article.get(article_id) or {}
        category = ((article.get('categories') or {}) or {}).get('name') or ''
        blob = {
            'title': ' '.join([article.get('title') or '', candidate.get('title') or '']),
            'description': ' '.join([
                article.get('excerpt') or '',
                article.get('content') or '',
                category,
                candidate.get('url') or '',
            ]),
            'track': candidate.get('track') or article.get('newsroom_track') or '',
        }
        if is_uganda(blob):
            return True
    return False


def set_pdf_url(article_id, pdf_url):
    try:
        return rest('articles', f'id=eq.{article_id}', method='PATCH', data={'pdf_url': pdf_url})
    except RuntimeError as error:
        if 'pdf_url' in str(error).lower():
            return rest('articles', f'id=eq.{article_id}', method='PATCH', data={'document_url': pdf_url})
        raise


def log_run(payload):
    return rest('newsroom_runs', method='POST', data=payload)[0]


def log_candidate(payload):
    return rest('newsroom_candidates', method='POST', data=payload)[0]


def log_sources(rows):
    if rows: return rest('newsroom_sources', method='POST', data=rows)
    return []
