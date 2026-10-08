import html as htmlmod
import os
import re
import struct
import tempfile
from html.parser import HTMLParser
from .http import request

DEFAULT_AUTHOR = 'Sentongo. R. Louis'
PLACEHOLDER_AUTHOR = re.compile(r'^(editorial desk|louiecorp editorial(?:\s+desk)?|ai writer|admin|louiecorp)$', re.I)
FONT_DIR = os.path.join(tempfile.gettempdir(), 'louiecorp-fonts')
UNIFRAKTUR_URLS = [
    'https://github.com/google/fonts/raw/main/ofl/unifrakturmaguntia/UnifrakturMaguntia-Book.ttf',
    'https://github.com/google/fonts/raw/main/ofl/unifrakturmaguntia/UnifrakturMaguntia-Regular.ttf',
]


def public_desk(name):
    if not name:
        return 'Analysis'
    if name == 'Christianity':
        return 'Faith'
    if name in ('Ideas', 'History'):
        return 'Analysis'
    if name == 'Law & Governance':
        return 'Governance'
    if name in ('Public life', 'Public Life'):
        return 'Politics'
    return name


def display_author(name):
    value = str(name or '').strip()
    if not value or PLACEHOLDER_AUTHOR.match(value):
        return DEFAULT_AUTHOR
    return value


def pdf_text(value):
    text = str(value or '')
    replacements = {
        '\u2014': '-', '\u2013': '-', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u00a0': ' ',
        '\u2022': '-', '\u00b7': '-',
    }
    for source, dest in replacements.items():
        text = text.replace(source, dest)
    return text.encode('latin-1', 'replace').decode('latin-1')


def _format_date(value):
    if not value:
        return ''
    text = str(value)
    try:
        import datetime as dt
        parsed = dt.datetime.fromisoformat(text.replace('Z', '+00:00'))
        return f'{parsed.day} {parsed.strftime("%B %Y")}'
    except Exception:
        return text[:32]


def collapse_space(value):
    return re.sub(r'\s+', ' ', str(value or '').replace('\xa0', ' ')).strip()


def looks_like_html(value):
    return bool(re.search(r'<\/?(p|h[1-6]|blockquote|ul|ol|li|figure|img|div|br)\b', str(value or ''), re.I))


class BlockParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self._stack = []
        self._buf = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ('script', 'style'):
            self._skip += 1
            return
        if tag in ('h1', 'h2', 'h3', 'h4', 'blockquote', 'li', 'p', 'figcaption'):
            self._stack.append(tag)
            self._buf = []
        elif tag in ('ul', 'ol', 'figure'):
            self._stack.append(tag)
        elif tag == 'br':
            self._buf.append(' ')
        elif tag == 'img':
            src = dict(attrs).get('src') or ''
            if src:
                self.blocks.append({'type': 'image', 'src': src, 'caption': ''})

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('script', 'style') and self._skip:
            self._skip -= 1
            return
        if tag in ('h1', 'h2'):
            self._push('h2')
        elif tag in ('h3', 'h4'):
            self._push('h3')
        elif tag == 'blockquote':
            self._push('quote')
        elif tag == 'li':
            self._push('li')
        elif tag == 'p':
            self._push('p')
        elif tag == 'figcaption' and self.blocks and self.blocks[-1].get('type') == 'image':
            self.blocks[-1]['caption'] = collapse_space(htmlmod.unescape(''.join(self._buf)))
            self._buf = []
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

    def handle_data(self, data):
        if not self._skip:
            self._buf.append(data)

    def _push(self, kind):
        text = collapse_space(htmlmod.unescape(''.join(self._buf)))
        self._buf = []
        if text:
            self.blocks.append({'type': kind, 'text': text})


def blocks_from_html(raw):
    parser = BlockParser()
    try:
        parser.feed(str(raw or ''))
        parser.close()
    except Exception:
        pass
    leftover = collapse_space(htmlmod.unescape(''.join(parser._buf)))
    if leftover:
        parser.blocks.append({'type': 'p', 'text': leftover})
    return parser.blocks


def blocks_from_markdown(text):
    out = []
    for block in re.split(r'\n{2,}', str(text or '').replace('\r\n', '\n')):
        block = block.strip()
        if not block:
            continue
        if block.startswith('## '):
            out.append({'type': 'h2', 'text': block[3:]})
        elif block.startswith('# '):
            out.append({'type': 'h2', 'text': block[2:]})
        elif block.startswith('> '):
            out.append({'type': 'quote', 'text': re.sub(r'^>\s?', '', block, flags=re.M)})
        else:
            out.append({'type': 'p', 'text': block})
    return out


def article_blocks(article):
    body = str(article.get('body') or article.get('content') or '')
    blocks = blocks_from_html(body) if looks_like_html(body) else blocks_from_markdown(body)
    title = collapse_space(article.get('title') or '')
    filtered = []
    for index, block in enumerate(blocks):
        if block.get('type') != 'p':
            filtered.append(block)
            continue
        text = collapse_space(block.get('text'))
        if index < 3 and title and text == title:
            continue
        lowered = re.sub(r'^by\s+', '', text, flags=re.I)
        if index < 3 and re.match(r'^by\s+', text, re.I) and PLACEHOLDER_AUTHOR.match(lowered):
            continue
        if index < 3 and re.match(r'^by\s+sentongo', text, re.I):
            continue
        filtered.append(block)
    return filtered


def _write_file(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as handle:
        handle.write(body)
    return path


def blackletter_path():
    for url in UNIFRAKTUR_URLS:
        name = os.path.basename(url.split('?')[0]) or 'UnifrakturMaguntia.ttf'
        dest = os.path.join(FONT_DIR, name)
        if os.path.isfile(dest) and os.path.getsize(dest) > 4000:
            return dest
        try:
            status, _, body = request(url, timeout=30)
        except Exception:
            continue
        if status >= 400 or not body or len(body) < 4000:
            continue
        if body[:4] not in (b'\x00\x01\x00\x00', b'OTTO', b'true'):
            continue
        return _write_file(dest, body)
    return ''


def fetch_image(url):
    if not url:
        return ''
    try:
        status, headers, body = request(url, timeout=30)
    except Exception:
        return ''
    if status >= 400 or not body:
        return ''
    ctype = ''
    if headers is not None:
        try:
            ctype = str(headers.get('Content-Type') or '').lower()
        except Exception:
            ctype = ''
    if body[:2] == b'\xff\xd8':
        ext = '.jpg'
    elif body[:8] == b'\x89PNG\r\n\x1a\n':
        ext = '.png'
    elif 'jpeg' in ctype or 'jpg' in ctype:
        ext = '.jpg'
    elif 'png' in ctype:
        ext = '.png'
    else:
        return ''
    dest = os.path.join(tempfile.gettempdir(), 'louiecorp-img-%s%s' % (abs(hash(url)) % (10 ** 10), ext))
    path = _write_file(dest, body)
    try:
        from PIL import Image
        image = Image.open(path)
        image.load()
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
            jpeg_path = os.path.splitext(path)[0] + '.jpg'
            image.save(jpeg_path, 'JPEG', quality=70)
            return jpeg_path
        max_w = 1400
        if image.width > max_w:
            height = max(1, round(image.height * (max_w / image.width)))
            image = image.resize((max_w, height))
            jpeg_path = os.path.splitext(path)[0] + '-fit.jpg'
            image.convert('RGB').save(jpeg_path, 'JPEG', quality=70)
            return jpeg_path
    except Exception:
        pass
    return path


def image_size(path):
    try:
        from PIL import Image
        with Image.open(path) as image:
            return image.width, image.height
    except Exception:
        pass
    with open(path, 'rb') as handle:
        data = handle.read(24)
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            handle.seek(16)
            width, height = struct.unpack('>II', handle.read(8))
            return width, height
        if data[:2] != b'\xff\xd8':
            return 0, 0
        handle.seek(2)
        while True:
            marker = handle.read(4)
            if len(marker) < 4:
                return 0, 0
            code, length = struct.unpack('>2sH', marker)
            if code[0] != 0xFF:
                return 0, 0
            if code[1] in (0xC0, 0xC1, 0xC2):
                sof = handle.read(length - 2)
                if len(sof) < 5:
                    return 0, 0
                height, width = struct.unpack('>xHH', sof[:5])
                return width, height
            handle.seek(length - 2, os.SEEK_CUR)


class LouieCorpArticlePDF:
    def __init__(self, article):
        from fpdf import FPDF

        class Doc(FPDF):
            def header(inner):
                if inner.page_no() == 1:
                    return
                inner.set_draw_color(17)
                inner.set_line_width(0.35)
                inner.line(self.margin, 12, inner.w - self.margin, 12)
                inner.set_font('Times', 'I', 8)
                inner.set_text_color(60)
                inner.text(self.margin, 9, 'LouieCorp Publishing')
                running = pdf_text(str(self.article.get('title') or '')[:70])
                inner.text(inner.w - self.margin - inner.get_string_width(running), 9, running)
                inner.set_text_color(0)

            def footer(inner):
                inner.set_draw_color(17)
                inner.set_line_width(0.2)
                inner.line(self.margin, inner.h - 12, inner.w - self.margin, inner.h - 12)
                inner.set_font('Helvetica', '', 8)
                inner.set_text_color(60)
                inner.text(self.margin, inner.h - 7.8, 'LouieCorp Publishing  ·  louiecorp.com')
                label = str(inner.page_no())
                inner.text(inner.w - self.margin - inner.get_string_width(label), inner.h - 7.8, label)
                inner.set_text_color(0)

        self.article = article
        self.doc = Doc(unit='mm', format='A4')
        self.doc.set_auto_page_break(auto=False)
        self.doc.set_compression(True)
        self.margin = 18
        self.page_width = self.doc.w
        self.page_height = self.doc.h
        self.max_width = self.page_width - self.margin * 2
        self.content_bottom = self.page_height - 18
        self.y = 0
        self.masthead_font = ''
        self._register_fonts()

    def _register_fonts(self):
        path = blackletter_path()
        if not path:
            return
        try:
            self.doc.add_font('LouieMasthead', '', path)
            self.masthead_font = 'LouieMasthead'
        except Exception:
            self.masthead_font = ''

    def _font(self, family, style='', size=10.5):
        mapping = {
            'times': 'Times',
            'serif': 'Times',
            'helvetica': 'Helvetica',
            'LouieMasthead': 'LouieMasthead',
        }
        name = mapping.get(family, family)
        try:
            self.doc.set_font(name, style, size)
        except Exception:
            fallback = 'Times' if name in ('Times', 'LouieMasthead') else 'Helvetica'
            self.doc.set_font(fallback, style if style in ('', 'B', 'I', 'BI') else '', size)

    def _lines(self, text, line_height):
        text = str(text or '')
        if not text:
            return []
        try:
            return self.doc.multi_cell(self.max_width, line_height, text, dry_run=True, output='LINES')
        except TypeError:
            return self.doc.multi_cell(self.max_width, line_height, text, split_only=True)

    def start_page(self):
        self.doc.add_page()
        self.y = 20

    def ensure_space(self, needed):
        if self.y + needed > self.content_bottom:
            self.start_page()

    def write_lines(self, lines, line_height):
        for line in lines:
            self.ensure_space(line_height)
            self.doc.text(self.margin, self.y, line)
            self.y += line_height

    def write_paragraph(self, text, font='times', style='', size=10.5, line_height=4.55, after=2.2, keep_with_next=0):
        self._font(font, style, size)
        lines = self._lines(pdf_text(text), line_height)
        if not lines:
            return
        preview = min(len(lines), 3) * line_height + keep_with_next
        if self.y + preview > self.content_bottom:
            self.start_page()
            self._font(font, style, size)
            lines = self._lines(text, line_height)
        self.write_lines(lines, line_height)
        self.y += after

    def draw_masthead(self):
        if self.masthead_font:
            self.doc.set_font(self.masthead_font, '', 22)
        else:
            self._font('times', 'B', 22)
        self.doc.set_text_color(17)
        title = 'LouieCorp'
        self.doc.text((self.page_width - self.doc.get_string_width(title)) / 2, 18, title)
        self._font('times', '', 6.5)
        self.doc.set_text_color(51)
        tag = 'INDEPENDENT NEWS  ·  PUBLIC AFFAIRS  ·  LOUIECORP.COM'
        self.doc.text((self.page_width - self.doc.get_string_width(tag)) / 2, 24.2, tag)
        self.doc.set_text_color(0)
        self.doc.set_draw_color(17)
        self.doc.set_line_width(0.55)
        self.doc.line(self.margin, 28.2, self.page_width - self.margin, 28.2)
        self.doc.set_line_width(0.18)
        self.doc.line(self.margin, 29.3, self.page_width - self.margin, 29.3)

    def add_cover(self, url, caption, max_height=58):
        path = fetch_image(url)
        if not path:
            return
        width, height = image_size(path)
        if not width or not height:
            return
        img_w = self.max_width
        img_h = min(max_height, (height / width) * img_w)
        self.ensure_space(img_h + 8)
        try:
            self.doc.image(path, self.margin, self.y, img_w, img_h)
        except Exception:
            return
        self.y += img_h + 3
        if caption:
            self.write_paragraph(caption, font='times', style='I', size=8, line_height=3.5, after=4)
        else:
            self.y += 3

    def build(self):
        article = self.article
        self.doc.add_page()
        self.draw_masthead()
        self.y = 36
        raw_desk = str(article.get('desk') or '').strip()
        if raw_desk:
            desk = public_desk(raw_desk)
            self._font('helvetica', 'B', 8)
            self.doc.set_text_color(90, 20, 24)
            self.doc.text(self.margin, self.y, pdf_text(desk.upper()))
            self.doc.set_text_color(0)
            self.y += 6
        self.write_paragraph(article.get('title') or '', font='times', style='B', size=16, line_height=6.4, after=2.6)
        if article.get('excerpt'):
            self.write_paragraph(article.get('excerpt'), font='times', style='I', size=10.5, line_height=4.7, after=3)
        self.doc.set_draw_color(180)
        self.doc.set_line_width(0.15)
        self.doc.line(self.margin, self.y, self.page_width - self.margin, self.y)
        self.y += 5
        author_name = display_author(article.get('author'))
        date = article.get('date') or _format_date(article.get('published_at'))
        byline = '   ·   '.join(part for part in [f'By {author_name}', 'LouieCorp Publishing', date] if part)
        self.write_paragraph(byline, font='helvetica', style='', size=8.5, line_height=3.8, after=4)
        if article.get('cover'):
            self.add_cover(article.get('cover'), article.get('caption') or '', 58)
        for block in article_blocks(article):
            kind = block.get('type')
            if kind == 'h2':
                self.y += 1.5
                self.write_paragraph(block.get('text'), font='times', style='B', size=12, line_height=5.2, after=2.4, keep_with_next=10)
            elif kind == 'h3':
                self.y += 1
                self.write_paragraph(block.get('text'), font='times', style='B', size=11, line_height=4.8, after=2, keep_with_next=9)
            elif kind == 'quote':
                self.y += 1
                self.write_paragraph(block.get('text'), font='times', style='I', size=10.5, line_height=4.6, after=3.2)
            elif kind == 'li':
                self.write_paragraph('•  %s' % block.get('text'), font='times', style='', size=10.5, line_height=4.5, after=1.4)
            elif kind == 'image' and block.get('src'):
                self.add_cover(block.get('src'), block.get('caption') or '', 48)
            elif block.get('text'):
                self.write_paragraph(block.get('text'), font='times', style='', size=10.5, line_height=4.55, after=2.15)
        if article.get('source'):
            self.y += 3
            if self.y + 14 > self.content_bottom:
                self.start_page()
            self.doc.set_draw_color(180)
            self.doc.set_line_width(0.15)
            self.doc.line(self.margin, self.y, self.page_width - self.margin, self.y)
            self.y += 5
            self.write_paragraph('Sources / references', font='helvetica', style='B', size=8, line_height=3.6, after=1.6)
            self.write_paragraph(article.get('source'), font='times', style='I', size=9, line_height=4.1, after=1)

    def bytes(self):
        output = self.doc.output()
        return bytes(output)


def generate_article_pdf(article):
    builder = LouieCorpArticlePDF(article)
    builder.build()
    return builder.bytes()
