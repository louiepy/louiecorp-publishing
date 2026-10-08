import re
import urllib.parse
from .config import UNSPLASH_ACCESS_KEY, MEDIA_WORKER_URL, MEDIA_BOT_SECRET
from .http import get_json, request


def find_wikimedia(query):
    params=urllib.parse.urlencode({'action':'query','generator':'search','gsrsearch':query,'gsrnamespace':6,'gsrlimit':8,'prop':'imageinfo|info','iiprop':'url|extmetadata','iiurlwidth':1600,'format':'json'})
    data=get_json('https://commons.wikimedia.org/w/api.php?'+params)
    pages=(data.get('query') or {}).get('pages',{})
    for page in pages.values():
        info=(page.get('imageinfo') or [{}])[0]; meta=info.get('extmetadata') or {}
        url=info.get('thumburl') or info.get('url')
        if not url: continue
        license_name=(meta.get('LicenseShortName') or {}).get('value','')
        artist=(meta.get('Artist') or {}).get('value','')
        if license_name and any(x in license_name.lower() for x in ['cc','public domain','pd','free']):
            return {'url':url,'credit':f"Wikimedia Commons{(' / '+artist) if artist else ''}",'license':license_name,'caption':(meta.get('ImageDescription') or {}).get('value','')[:300]}
    return None


def find_unsplash(query):
    if not UNSPLASH_ACCESS_KEY: return None
    params=urllib.parse.urlencode({'query':query,'per_page':8,'orientation':'landscape','content_filter':'high'})
    data=get_json('https://api.unsplash.com/search/photos?'+params, headers={'Authorization':'Client-ID '+UNSPLASH_ACCESS_KEY})
    for x in data.get('results',[]):
        u=x.get('urls',{}).get('regular')
        if u:
            name=((x.get('user') or {}).get('name') or 'Unsplash photographer')
            return {'url':u,'credit':f'Unsplash / {name}','license':'Unsplash License','caption':x.get('alt_description') or x.get('description') or ''}
    return None


def choose(query):
    return find_wikimedia(query) or find_unsplash(query)


def upload(image, key):
    if not MEDIA_BOT_SECRET: raise RuntimeError('MEDIA_BOT_SECRET is not configured.')
    status,_,body=request(f'{MEDIA_WORKER_URL}/bot-media/{key}', method='PUT', data=None, headers={'Authorization':'Bearer '+MEDIA_BOT_SECRET,'X-Image-Source':image['url']}, timeout=60)
    if status>=400: raise RuntimeError('Media worker upload failed: '+body.decode('utf-8','replace')[:500])
    return f'{MEDIA_WORKER_URL}/media/{key}'


def upload_pdf(data, key):
    if not MEDIA_BOT_SECRET: raise RuntimeError('MEDIA_BOT_SECRET is not configured.')
    object_key = str(key or '').replace('\\', '/').lstrip('/')
    if not object_key.startswith('pdfs/'):
        object_key = 'pdfs/' + object_key
    if object_key.count('/') != 1 or not re.match(r'^pdfs/[a-zA-Z0-9._-]+$', object_key):
        raise RuntimeError('Invalid PDF object key.')
    payload = data if isinstance(data, (bytes, bytearray)) else bytes(data)
    if not payload:
        raise RuntimeError('Empty PDF.')
    status, _, body = request(
        f'{MEDIA_WORKER_URL}/bot-media/{object_key}',
        method='PUT',
        data=payload,
        headers={'Authorization': 'Bearer ' + MEDIA_BOT_SECRET, 'Content-Type': 'application/pdf'},
        timeout=60
    )
    if status >= 400:
        raise RuntimeError('Media worker PDF upload failed: ' + body.decode('utf-8', 'replace')[:500])
    return f'{MEDIA_WORKER_URL}/media/{object_key}'
