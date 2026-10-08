import json, re, time
from urllib.parse import quote
from .config import GEMINI_API_KEY, GEMINI_FALLBACK_MODEL, GEMINI_MODEL
from .http import body_text, request

SYSTEM='''You are the senior writer for LouieCorp Publishing. Write like a careful human journalist and educator. Never invent facts, quotes, statistics, studies, dates, people, institutions, or events. Use only evidence supplied in the research packet. If a claim cannot be supported, omit it. Do not copy source wording. No em dashes or en dashes. Do not use a generic AI voice. Attribute consequential claims to their sources. For knowledge articles, explain difficult concepts clearly for university students and general readers while maintaining scholarly accuracy.''' 

SCHEMA={"type":"object","properties":{
"title":{"type":"string"},"excerpt":{"type":"string"},"category":{"type":"string"},"tags":{"type":"array","items":{"type":"string"}},"content_html":{"type":"string"},"image_query":{"type":"string"},"image_caption":{"type":"string"},"image_alt":{"type":"string"},"source_credit":{"type":"string"}},"required":["title","excerpt","category","tags","content_html","image_query","image_caption","image_alt","source_credit"]}

GEMINI_API_ROOT = 'https://generativelanguage.googleapis.com/v1beta/models'
TRANSIENT_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
INITIAL_BACKOFF_SECONDS = 2


def model_name(value=None):
    name = str(value if value is not None else GEMINI_MODEL or '').strip()
    if name.lower().startswith('models/'):
        name = name.split('/', 1)[1]
    return name


def generate_url(api_key=None, model=None):
    key = api_key if api_key is not None else GEMINI_API_KEY
    return (
        GEMINI_API_ROOT
        + '/'
        + quote(model_name(model), safe='.-')
        + ':generateContent?key='
        + quote(str(key or ''), safe='')
    )


def parse_article(raw, headers):
    data=json.loads(body_text(raw, headers))
    text=data['candidates'][0]['content']['parts'][0]['text'].strip()
    text=re.sub(r'^```json\s*|\s*```$','',text,flags=re.I).strip()
    return json.loads(text)


def generate_with_model(model, body):
    url=generate_url(model=model)
    last_status = 0
    last_detail = ''
    for attempt in range(MAX_ATTEMPTS):
        status, headers, raw = request(url, method='POST', data=body, headers={'Content-Type':'application/json'}, timeout=60)
        last_status = status
        last_detail = body_text(raw, headers, 800)
        if status and status < 400:
            return parse_article(raw, headers)
        if status not in TRANSIENT_STATUSES:
            raise RuntimeError(f'Gemini {status} ({model_name(model)}): {last_detail}')
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(INITIAL_BACKOFF_SECONDS * (2 ** attempt))
    raise RuntimeError(
        f'Gemini remained temporarily unavailable after {MAX_ATTEMPTS} attempts '
        f'on {model_name(model)} (HTTP {last_status}): {last_detail}'
    )


def generate(packet, track):
    if not GEMINI_API_KEY: raise RuntimeError('GEMINI_API_KEY is not configured.')
    prompt=f'''{SYSTEM}\n\nTRACK: {track}\n\nRESEARCH PACKET:\n{json.dumps(packet, ensure_ascii=False, indent=2)}\n\nReturn ONLY valid JSON matching this schema:\n{json.dumps(SCHEMA)}\n\nFor news: report the verified event, context, implications, and what happens next.\nFor knowledge: produce an original explanatory publication connected to the evidence, with a clear thesis, sections, examples, limitations, and why the subject matters to students and society. It must not pretend to be breaking news.\n\nThe image_query must describe a real photographic subject that could be found in Wikimedia Commons or Unsplash. Never request an AI generated image.'''
    body={"contents":[{"role":"user","parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.25,"responseMimeType":"application/json"}}
    primary = model_name()
    fallback = model_name(GEMINI_FALLBACK_MODEL)
    try:
        return generate_with_model(primary, body)
    except RuntimeError as primary_error:
        message = str(primary_error)
        if 'temporarily unavailable' not in message:
            raise
        if not fallback or fallback == primary:
            raise
        try:
            return generate_with_model(fallback, body)
        except RuntimeError as fallback_error:
            raise RuntimeError(
                f'Gemini primary {primary} failed: {primary_error}; '
                f'fallback {fallback} failed: {fallback_error}'
            ) from fallback_error
