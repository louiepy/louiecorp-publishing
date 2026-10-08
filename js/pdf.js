(function initLouieCorpPdf(global) {
  const DEFAULT_AUTHOR = 'Sentongo. R. Louis';
  const PLACEHOLDER_AUTHOR = /^(editorial desk|louiecorp editorial(?:\s+desk)?|ai writer|admin|louiecorp)$/i;

  function loadImage(url) {
    return new Promise((resolve) => {
      if (!url) {
        resolve(null);
        return;
      }
      const image = new Image();
      image.crossOrigin = 'anonymous';
      image.onload = () => resolve(image);
      image.onerror = () => resolve(null);
      image.src = url;
    });
  }

  function canvasToJpeg(canvas, quality) {
    return canvas.toDataURL('image/jpeg', quality || 0.68);
  }

  function displayAuthor(name) {
    const value = String(name || '').trim();
    if (!value || PLACEHOLDER_AUTHOR.test(value)) return DEFAULT_AUTHOR;
    return value;
  }

  async function mastheadDataUrl() {
    try {
      if (document.fonts && document.fonts.load) {
        await document.fonts.load('72px UnifrakturMaguntia');
      }
    } catch (error) {
      /* continue with whatever is available */
    }
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 1600;
    canvas.height = 180;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#111111';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = '78px UnifrakturMaguntia';
    ctx.fillText('LouieCorp', canvas.width / 2, canvas.height / 2 - 10);
    ctx.font = '15px Times New Roman, serif';
    ctx.fillStyle = '#333333';
    ctx.fillText('INDEPENDENT NEWS  ·  PUBLIC AFFAIRS  ·  LOUIECORP.COM', canvas.width / 2, canvas.height - 22);
    return canvas.toDataURL('image/png');
  }

  async function coverDataUrl(url) {
    const image = await loadImage(url);
    if (!image) return null;
    const maxW = 1400;
    const scale = Math.min(1, maxW / Math.max(image.width, 1));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(image.width * scale));
    canvas.height = Math.max(1, Math.round(image.height * scale));
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    return {
      data: canvasToJpeg(canvas, 0.7),
      width: canvas.width,
      height: canvas.height
    };
  }

  function decodeEntities(value) {
    const textarea = document.createElement('textarea');
    textarea.innerHTML = String(value || '');
    return textarea.value;
  }

  function collapseSpace(value) {
    return String(value || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
  }

  function looksLikeHtml(value) {
    return /<\/?(p|h[1-6]|blockquote|ul|ol|li|figure|img|div|br)\b/i.test(String(value || ''));
  }

  function blocksFromHtml(html) {
    const wrap = document.createElement('div');
    wrap.innerHTML = String(html || '');
    const blocks = [];
    function pushText(type, text) {
      const clean = collapseSpace(decodeEntities(text));
      if (clean) blocks.push({ type, text: clean });
    }
    Array.from(wrap.childNodes).forEach((node) => {
      if (node.nodeType === 3) {
        pushText('p', node.textContent);
        return;
      }
      if (node.nodeType !== 1) return;
      const tag = node.tagName.toLowerCase();
      if (tag === 'h1' || tag === 'h2') {
        pushText('h2', node.textContent);
      } else if (tag === 'h3' || tag === 'h4') {
        pushText('h3', node.textContent);
      } else if (tag === 'blockquote') {
        pushText('quote', node.textContent);
      } else if (tag === 'ul' || tag === 'ol') {
        Array.from(node.querySelectorAll('li')).forEach((li) => {
          pushText('li', li.textContent);
        });
      } else if (tag === 'figure') {
        const img = node.querySelector('img');
        const caption = node.querySelector('figcaption');
        if (img && img.getAttribute('src')) {
          blocks.push({ type: 'image', src: img.getAttribute('src'), caption: collapseSpace(caption && caption.textContent) });
        } else {
          pushText('p', node.textContent);
        }
      } else if (tag === 'img' && node.getAttribute('src')) {
        blocks.push({ type: 'image', src: node.getAttribute('src'), caption: '' });
      } else {
        pushText('p', node.textContent);
      }
    });
    return blocks;
  }

  function blocksFromMarkdown(text) {
    return String(text || '')
      .replace(/\r\n/g, '\n')
      .split(/\n{2,}/)
      .map((block) => block.trim())
      .filter(Boolean)
      .map((block) => {
        if (block.startsWith('## ')) return { type: 'h2', text: block.slice(3) };
        if (block.startsWith('# ')) return { type: 'h2', text: block.slice(2) };
        if (block.startsWith('> ')) return { type: 'quote', text: block.replace(/^>\s?/gm, '') };
        return { type: 'p', text: block };
      });
  }

  function articleBlocks(article) {
    const body = String(article.body || '');
    const blocks = looksLikeHtml(body) ? blocksFromHtml(body) : blocksFromMarkdown(body);
    const title = collapseSpace(article.title || '');
    return blocks.filter((block, index) => {
      if (block.type !== 'p') return true;
      const text = collapseSpace(block.text);
      if (index < 3 && title && text === title) return false;
      if (index < 3 && /^by\s+/i.test(text) && PLACEHOLDER_AUTHOR.test(text.replace(/^by\s+/i, ''))) return false;
      if (index < 3 && /^by\s+sentongo/i.test(text)) return false;
      return true;
    });
  }

  async function generateArticlePdf(article) {
    if (!global.jspdf || !global.jspdf.jsPDF) {
      throw new Error('PDF library is not loaded.');
    }
    const { jsPDF } = global.jspdf;
    const doc = new jsPDF({
      unit: 'mm',
      format: 'a4',
      compress: true
    });
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 18;
    const maxWidth = pageWidth - margin * 2;
    const footerY = pageHeight - 12;
    const contentBottom = pageHeight - 18;
    let page = 1;
    let y = 0;

    function drawHeaderRule() {
      if (page === 1) return;
      doc.setDrawColor(17);
      doc.setLineWidth(0.35);
      doc.line(margin, 12, pageWidth - margin, 12);
      doc.setFont('times', 'italic');
      doc.setFontSize(8);
      doc.setTextColor(60);
      doc.text('LouieCorp Publishing', margin, 9);
      const running = String(article.title || '').slice(0, 70);
      doc.text(running, pageWidth - margin, 9, { align: 'right' });
      doc.setTextColor(0);
    }

    function footer() {
      doc.setDrawColor(17);
      doc.setLineWidth(0.2);
      doc.line(margin, footerY, pageWidth - margin, footerY);
      doc.setFont('times', 'normal');
      doc.setFontSize(8);
      doc.setTextColor(60);
      doc.text('LouieCorp Publishing  ·  louiecorp.com', margin, footerY + 4.2);
      doc.text(String(page), pageWidth - margin, footerY + 4.2, { align: 'right' });
      doc.setTextColor(0);
    }

    function startPage() {
      page += 1;
      doc.addPage();
      drawHeaderRule();
      y = 20;
    }

    function ensureSpace(needed) {
      if (y + needed > contentBottom) startPage();
    }

    function writeLines(lines, lineHeight) {
      lines.forEach((line) => {
        ensureSpace(lineHeight);
        doc.text(line, margin, y);
        y += lineHeight;
      });
    }

    function writeParagraph(text, options) {
      const opts = options || {};
      doc.setFont(opts.font || 'times', opts.style || 'normal');
      doc.setFontSize(opts.size || 10.5);
      const lineHeight = opts.lineHeight || 4.55;
      const lines = doc.splitTextToSize(String(text || ''), maxWidth);
      const keepWithNext = opts.keepWithNext || 0;
      if (y + (Math.min(lines.length, 3) * lineHeight) + keepWithNext > contentBottom) {
        startPage();
      }
      writeLines(lines, lineHeight);
      y += opts.after || 2.2;
    }

    const masthead = await mastheadDataUrl();
    doc.addImage(masthead, 'PNG', margin, 8, maxWidth, 18);
    doc.setDrawColor(17);
    doc.setLineWidth(0.55);
    doc.line(margin, 28.2, pageWidth - margin, 28.2);
    doc.setLineWidth(0.18);
    doc.line(margin, 29.3, pageWidth - margin, 29.3);

    y = 36;
    const desk = String(article.desk || '').trim();
    if (desk) {
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8);
      doc.setTextColor(90, 20, 24);
      doc.text(desk.toUpperCase(), margin, y);
      doc.setTextColor(0);
      y += 6;
    }

    writeParagraph(article.title || '', {
      font: 'times',
      style: 'bold',
      size: 16,
      lineHeight: 6.4,
      after: 2.6
    });

    if (article.excerpt) {
      writeParagraph(article.excerpt, {
        font: 'times',
        style: 'italic',
        size: 10.5,
        lineHeight: 4.7,
        after: 3
      });
    }

    doc.setDrawColor(180);
    doc.setLineWidth(0.15);
    doc.line(margin, y, pageWidth - margin, y);
    y += 5;
    const authorName = displayAuthor(article.author);
    const byline = [`By ${authorName}`, 'LouieCorp Publishing', article.date || '']
      .filter(Boolean)
      .join('   ·   ');
    writeParagraph(byline, {
      font: 'helvetica',
      style: 'normal',
      size: 8.5,
      lineHeight: 3.8,
      after: 4
    });

    if (article.cover) {
      const cover = await coverDataUrl(article.cover);
      if (cover) {
        const imgW = maxWidth;
        const imgH = Math.min(58, (cover.height / cover.width) * imgW);
        ensureSpace(imgH + 8);
        doc.addImage(cover.data, 'JPEG', margin, y, imgW, imgH, undefined, 'FAST');
        y += imgH + 3;
        if (article.caption) {
          writeParagraph(article.caption, {
            font: 'times',
            style: 'italic',
            size: 8,
            lineHeight: 3.5,
            after: 4
          });
        } else {
          y += 3;
        }
      }
    }

    const blocks = articleBlocks(article);
    for (const block of blocks) {
      if (block.type === 'h2') {
        y += 1.5;
        writeParagraph(block.text, {
          font: 'times',
          style: 'bold',
          size: 12,
          lineHeight: 5.2,
          after: 2.4,
          keepWithNext: 10
        });
      } else if (block.type === 'h3') {
        y += 1;
        writeParagraph(block.text, {
          font: 'times',
          style: 'bold',
          size: 11,
          lineHeight: 4.8,
          after: 2,
          keepWithNext: 9
        });
      } else if (block.type === 'quote') {
        y += 1;
        writeParagraph(block.text, {
          font: 'times',
          style: 'italic',
          size: 10.5,
          lineHeight: 4.6,
          after: 3.2
        });
      } else if (block.type === 'li') {
        writeParagraph(`•  ${block.text}`, {
          font: 'times',
          style: 'normal',
          size: 10.5,
          lineHeight: 4.5,
          after: 1.4
        });
      } else if (block.type === 'image' && block.src) {
        const inline = await coverDataUrl(block.src);
        if (inline) {
          const imgW = maxWidth;
          const imgH = Math.min(48, (inline.height / inline.width) * imgW);
          ensureSpace(imgH + 10);
          doc.addImage(inline.data, 'JPEG', margin, y, imgW, imgH, undefined, 'FAST');
          y += imgH + 2.5;
          if (block.caption) {
            writeParagraph(block.caption, {
              font: 'times',
              style: 'italic',
              size: 8,
              lineHeight: 3.4,
              after: 3.5
            });
          } else {
            y += 3;
          }
        }
      } else if (block.text) {
        writeParagraph(block.text, {
          font: 'times',
          style: 'normal',
          size: 10.5,
          lineHeight: 4.55,
          after: 2.15
        });
      }
    }

    if (article.source) {
      y += 3;
      if (y + 14 > contentBottom) startPage();
      doc.setDrawColor(180);
      doc.setLineWidth(0.15);
      doc.line(margin, y, pageWidth - margin, y);
      y += 5;
      writeParagraph('Sources / references', {
        font: 'helvetica',
        style: 'bold',
        size: 8,
        lineHeight: 3.6,
        after: 1.6
      });
      writeParagraph(article.source, {
        font: 'times',
        style: 'italic',
        size: 9,
        lineHeight: 4.1,
        after: 1
      });
    }

    const total = doc.internal.getNumberOfPages();
    for (let i = 1; i <= total; i += 1) {
      doc.setPage(i);
      page = i;
      footer();
    }

    const blob = doc.output('blob', { compression: 'FAST' });
    return new File([blob], `${article.slug || 'article'}.pdf`, { type: 'application/pdf' });
  }

  global.LouieCorpPdf = { generateArticlePdf };
}(window));
