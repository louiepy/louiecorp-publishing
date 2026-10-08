import json
import time
import urllib.request
import urllib.parse
import urllib.error
from html.parser import HTMLParser
from .config import USER_AGENT


def request(url, method='GET', data=None, headers=None, timeout=25):
    hdr = {'User-Agent': USER_AGENT, 'Accept': '*/*'}
    if headers: hdr.update(headers)
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode('utf-8')
        hdr.setdefault('Content-Type', 'application/json')
    req = urllib.request.Request(url, data=body, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def get_json(url, headers=None, timeout=25):
    status, _, body = request(url, headers=headers, timeout=timeout)
    if status >= 400:
        raise RuntimeError(f'HTTP {status}: {body[:500].decode("utf-8", "replace")}')
    return json.loads(body.decode('utf-8', 'replace'))


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []
        self.title = ''
        self.in_title = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript','svg','nav','footer','header','form'):
            self.skip += 1
        if tag == 'title': self.in_title = True
    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag in ('script','style','noscript','svg','nav','footer','header','form') and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if self.in_title: self.title += ' ' + data
        if not self.skip and data.strip(): self.parts.append(data.strip())


def extract_text(html, limit=12000):
    p = TextParser()
    p.feed(html)
    text = ' '.join(p.parts)
    return ' '.join(text.split())[:limit], ' '.join(p.title.split())[:300]
