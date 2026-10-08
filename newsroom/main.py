import argparse, datetime as dt, re, traceback, urllib.parse
from .config import MAX_DAILY_AUTOMATED, MIN_IMPORTANCE, AUTO_PUBLISH, MAX_SOURCES
from .discovery import discover
from .rank import score, knowledge_topics, is_uganda
from .research import research
from .ai import generate
from .images import choose, upload, upload_pdf
from .supabase import automated_today, find_duplicate, find_author, category_id, insert_article, log_run, log_candidate, log_sources, uganda_done_today, set_pdf_url


def clean_html(value):
    import re as _re
    text=str(value or '')
    text=_re.sub(r'<\s*(script|style|iframe|object|embed)[^>]*>.*?<\s*/\s*\1\s*>','',text,flags=_re.I|_re.S)
    def tag(m):
        closing=m.group(1)
        name=m.group(2).lower()
        if name not in {'p','h2','h3','blockquote','ul','ol','li','strong','em','br','a'}: return ''
        if name=='a' and not closing:
            href=_re.search(r'href=[\"\'](https?://[^\"\']+)',m.group(0),_re.I)
            return '<a href="'+href.group(1).replace('"','%22')+'" rel="nofollow noopener" target="_blank">' if href else ''
        return '</'+name+'>' if closing else '<'+name+'>'
    return _re.sub(r'<\s*(/?)\s*([a-zA-Z0-9]+)(?:\s+[^>]*)?>',tag,text)

def slugify(s): return re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',s.lower())).strip('-')[:110]

def choose_track(mode, runs, uganda_needed=False):
    if uganda_needed:
        return 'news'
    if mode in ('news','knowledge'): return mode
    knowledge_done=any(r.get('track')=='knowledge' and r.get('success') for r in runs)
    if not knowledge_done: return 'knowledge'
    return 'news'


def uganda_candidates(discovered):
    preferred=[c for c in discovered if is_uganda(c)]
    if preferred:
        return preferred
    return [c for c in discovered if str(c.get('track') or '').lower()=='uganda']

def utc_day_seed():
    return dt.datetime.now(dt.timezone.utc).timetuple().tm_yday

def topic_text(candidate):
    return (candidate.get('title','')+' '+candidate.get('description','')).lower()

def matches_topic(candidate, topic):
    hay=topic_text(candidate)
    field=str(topic or '').lower().strip()
    if not field: return False
    if field in hay: return True
    words=[w for w in re.split(r'[^a-z0-9]+', field) if len(w)>3]
    return bool(words) and all(w in hay for w in words)

def knowledge_focus():
    topics=knowledge_topics(utc_day_seed())
    return topics[0], topics

def knowledge_candidates(discovered):
    primary, topics = knowledge_focus()
    pool=[c for c in discovered if c.get('track')=='knowledge']
    preferred=[]
    for topic in topics[:6]:
        for candidate in pool:
            if candidate in preferred: continue
            if matches_topic(candidate, topic): preferred.append(candidate)
    if preferred: return preferred, primary
    if pool: return pool, primary
    query=urllib.parse.quote(primary)
    return [{
        'title': primary,
        'url': f'https://news.google.com/rss/search?q={query}&hl=en-US&gl=UG&ceid=UG:en',
        'description': f'An original Knowledge & Society publication on {primary}.',
        'published': '',
        'track': 'knowledge',
        'feed': 'LouieCorp Knowledge Desk'
    }], primary

def rank_key(candidate, track, topics):
    value=score(candidate, track)
    if track=='knowledge':
        hay=topic_text(candidate)
        for index, topic in enumerate(topics[:6]):
            if matches_topic(candidate, topic) or str(topic or '').lower() in hay:
                value += 12 - index
                break
    return max(0, min(100, value))

def attach_published_pdf(row, article, image, sources, published_at, desk, cover_url):
    try:
        from .pdf import generate_article_pdf, DEFAULT_AUTHOR
        pdf_bytes=generate_article_pdf({
            'slug': row.get('slug') or slugify(article.get('title') or 'article'),
            'title': article.get('title') or '',
            'excerpt': article.get('excerpt') or '',
            'body': article.get('content_html') or '',
            'cover': cover_url or row.get('cover_image_url') or '',
            'caption': article.get('image_caption') or image.get('caption') or '',
            'author': DEFAULT_AUTHOR,
            'date': '',
            'published_at': published_at,
            'desk': desk,
            'source': ' — '.join(part for part in [image.get('credit') or '', (sources[0] or {}).get('url') or ''] if part)
        })
        key=f"pdfs/newsroom-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{slugify(article.get('title') or row.get('slug') or 'article')[:50]}-edition.pdf"
        pdf_url=upload_pdf(pdf_bytes, key)
        set_pdf_url(row['id'], pdf_url)
        print('PDF uploaded:', pdf_url)
    except Exception as error:
        print('PDF generation skipped:', error)


def main(mode='auto'):
    runs=automated_today()
    successful=[r for r in runs if r.get('success')]
    if len(successful)>=MAX_DAILY_AUTOMATED:
        print('Daily automated ceiling reached.'); return 0
    uganda_needed=not uganda_done_today(runs)
    remaining=MAX_DAILY_AUTOMATED-len(successful)
    if uganda_needed and remaining<=0:
        print('Daily automated ceiling reached without a Uganda story.'); return 0
    track=choose_track(mode,runs,uganda_needed)
    run=log_run({'track':track,'success':False,'mode':mode,'started_at':dt.datetime.now(dt.timezone.utc).isoformat()})
    try:
        candidates=discover()
        topics=[]
        focus=''
        if uganda_needed:
            candidates=uganda_candidates(candidates)
            print('Uganda daily requirement: selecting a Uganda story.')
            if not candidates: raise RuntimeError('No Uganda candidate was found for the required daily Uganda story.')
        elif track=='knowledge':
            candidates, focus = knowledge_candidates(candidates)
            topics=knowledge_topics(utc_day_seed())
            print('Knowledge desk focus:', focus)
        else:
            candidates=[c for c in candidates if c.get('track')!='knowledge']
        ranked=sorted(candidates,key=lambda c:rank_key(c,track,topics),reverse=True)
        selected=None
        for c in ranked[:30]:
            c['importance_score']=rank_key(c,track,topics)
            if uganda_needed and not is_uganda(c): continue
            if c['importance_score']<MIN_IMPORTANCE: continue
            dup=find_duplicate(c['title'],[c['url']])
            if dup: continue
            selected=c; break
        if not selected:
            if uganda_needed:
                raise RuntimeError('No sufficiently important, non-duplicate Uganda candidate found.')
            raise RuntimeError('No sufficiently important, non-duplicate candidate found.')
        cand=log_candidate({'title':selected['title'],'url':selected['url'],'track':track,'importance_score':selected['importance_score'],'status':'researching'})
        sources=research(selected,MAX_SOURCES)
        if len(sources)<2: raise RuntimeError('Fewer than two usable sources were found.')
        packet={'candidate':selected,'sources':sources,'rules':['Do not invent or guess facts, quotes, statistics or dates.','Use multiple independent sources for consequential claims.']}
        if track=='knowledge' and focus:
            packet['knowledge_focus']=focus
            packet['knowledge_rotation']=topics[:6]
        article=generate(packet,track)
        article['content_html']=clean_html(article.get('content_html',''))
        if len(re.sub(r'<[^>]+>',' ',article['content_html']).split()) < 500: raise RuntimeError('Generated article is too short for publication.')
        image=choose(article.get('image_query') or article['title'])
        if not image: raise RuntimeError('No properly licensed real photograph was found. No AI image will be generated.')
        key=f"covers/newsroom-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{slugify(article['title'])[:70]}.jpg"
        cover_url=upload(image,key)
        category=category_id(article.get('category') or ('Knowledge & Society' if track=='knowledge' else 'World'))
        author=find_author()
        slug=slugify(article['title'])
        existing=find_duplicate(article['title'],[s['url'] for s in sources])
        if existing: raise RuntimeError('Duplicate detected after writing.')
        if uganda_needed and not is_uganda(selected):
            raise RuntimeError('Selected story does not satisfy the required daily Uganda publication.')
        status='published' if AUTO_PUBLISH and selected['importance_score']>=MIN_IMPORTANCE and len(sources)>=2 else 'draft'
        published_at=dt.datetime.now(dt.timezone.utc).isoformat() if status=='published' else None
        provenance_track='uganda' if uganda_needed or is_uganda(selected) else track
        row=insert_article({'slug':slug,'title':article['title'],'excerpt':article['excerpt'],'content':article['content_html'],'category_id':category,'author_id':__import__('os').getenv('NEWSROOM_EDITOR_USER_ID') or None,'byline_author_id':author,'status':status,'published_at':published_at,'cover_image_url':cover_url,'source_credit':image['credit'],'source_url':sources[0]['url'],'image_caption':article.get('image_caption') or image.get('caption') or '', 'image_license':image.get('license',''), 'image_source_url':image.get('url',''), 'newsroom_track':provenance_track, 'newsroom_importance_score':selected['importance_score'], 'review_status':'auto-published' if status=='published' else 'pending', 'featured':False,'editors_pick':False,'is_breaking':False})
        if status=='published':
            attach_published_pdf(row, article, image, sources, published_at, article.get('category') or ('Knowledge & Society' if track=='knowledge' else 'World'), cover_url)
        log_sources([{'run_id':run['id'],'candidate_id':cand['id'],'url':s['url'],'title':s['title'],'publisher':s['publisher'],'retrieved_at':s['retrieved_at'],'notes':'Research source used for verification.'} for s in sources])
        # Candidate/run updates are intentionally simple and safe.
        from .supabase import rest
        rest('newsroom_candidates',f'id=eq.{cand["id"]}',method='PATCH',data={'status':'draft_created','article_id':row['id']})
        rest('newsroom_runs',f'id=eq.{run["id"]}',method='PATCH',data={'success':True,'article_id':row['id'],'finished_at':dt.datetime.now(dt.timezone.utc).isoformat()})
        print(f"Created {status}: {article['title']}")
        return 0
    except Exception as e:
        from .supabase import rest
        rest('newsroom_runs',f'id=eq.{run["id"]}',method='PATCH',data={'success':False,'error_message':str(e)[:1000],'finished_at':dt.datetime.now(dt.timezone.utc).isoformat()})
        print('NEWSROOM ERROR:',e)
        traceback.print_exc()
        return 1

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--mode',choices=['auto','news','knowledge'],default='auto'); args=ap.parse_args(); raise SystemExit(main(args.mode))
