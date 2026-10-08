import re, urllib.parse, xml.etree.ElementTree as ET
from .config import RSS_FEEDS
from .http import request


def discover():
    out=[]
    for publisher, url, track in RSS_FEEDS:
        try:
            status, _, body = request(url, timeout=20)
            if status >= 400: continue
            root=ET.fromstring(body)
            for item in root.findall('.//item')[:25]:
                title=' '.join((item.findtext('title') or '').split())
                link=(item.findtext('link') or '').strip()
                desc=' '.join(re.sub('<[^>]+>',' ',item.findtext('description') or '').split())
                pub=(item.findtext('pubDate') or '').strip()
                if title and link: out.append({'title':title,'url':link,'description':desc[:1000],'published':pub,'track':track,'feed':publisher})
        except Exception: continue
    seen=set(); unique=[]
    for x in out:
        key=re.sub(r'[^a-z0-9]+',' ',x['title'].lower()).strip()
        if key not in seen:
            seen.add(key); unique.append(x)
    return unique
