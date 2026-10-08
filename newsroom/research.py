import re, urllib.parse, xml.etree.ElementTree as ET
from .http import request, extract_text


def research(candidate, max_sources=6):
    sources=[candidate]
    query=urllib.parse.quote(candidate['title'])
    # Use Google News RSS rather than scraping a search-results page. This gives us
    # actual feed items from multiple publishers and avoids brittle HTML parsing.
    feed_url=f'https://news.google.com/rss/search?q={query}&hl=en-US&gl=UG&ceid=UG:en'
    try:
        status,_,body=request(feed_url, timeout=20)
        if status<400:
            root=ET.fromstring(body)
            for item in root.findall('.//item'):
                title=' '.join((item.findtext('title') or '').split())
                url=(item.findtext('link') or '').strip()
                desc=' '.join(re.sub('<[^>]+>',' ',item.findtext('description') or '').split())
                source_node=item.find('{http://search.yahoo.com/mrss/}source')
                publisher=(source_node.text.strip() if source_node is not None and source_node.text else 'News source')
                if url and title and url not in [x['url'] for x in sources]:
                    sources.append({'title':title,'url':url,'description':desc,'published':item.findtext('pubDate') or '','track':candidate.get('track','news'),'feed':publisher})
                if len(sources)>=max_sources: break
    except Exception: pass
    # GDELT is a second independent discovery path and is free to query.
    try:
        gd='https://api.gdeltproject.org/api/v2/doc/doc?query='+query+'&mode=ArtList&maxrecords=10&format=json&sort=HybridRel'
        data=__import__('json').loads(request(gd, timeout=20)[2].decode('utf-8','replace'))
        for item in data.get('articles',[]):
            url=item.get('url','')
            if url and url not in [x['url'] for x in sources]:
                sources.append({'title':item.get('title','Related source'),'url':url,'description':item.get('snippet',''),'published':item.get('seendate',''),'track':candidate.get('track','news'),'feed':item.get('domain','GDELT')})
            if len(sources)>=max_sources: break
    except Exception: pass
    packet=[]; seen=set()
    for src in sources[:max_sources]:
        if src['url'] in seen: continue
        seen.add(src['url'])
        try:
            status,headers,body=request(src['url'], timeout=20)
            if status>=400: continue
            text,title=extract_text(body.decode('utf-8','replace'))
            if len(text)<300: continue
            packet.append({'title':title or src['title'],'url':src['url'],'publisher':src.get('feed','Source'),'retrieved_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'text':text[:9000]})
        except Exception: continue
    return packet
