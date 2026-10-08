const {
  isConfigured,
  getClient,
  formatDate,
  formatDateTime,
  isoDate,
  escapeHtml,
  renderBody,
  publicDesk,
  articleHref,
  authorHref,
  articleDocumentUrl,
  authorFromArticle,
  authorInitials,
  applyArticleHead,
  excerptFrom,
  readingTime,
  readArticleSlug,
  shareTargets,
  shareCardUrl,
  siteUrl,
  PUBLISHER_NAME,
  DEFAULT_AUTHOR_NAME,
  publicImageUrl
} = window.LouieCorp;

const SECTION_ORDER = ['Politics', 'Business', 'Technology', 'Africa', 'World', 'Society', 'Culture', 'Opinion', 'Investigations', 'Governance', 'Analysis'];

function articleDesk(article) {
  return publicDesk(article.categories && article.categories.name);
}

const SELECT_WITH_AUTHORS = 'id, slug, title, excerpt, cover_image_url, published_at, updated_at, featured, editors_pick, is_breaking, view_count, pdf_url, categories(name, slug), profiles(display_name, bio, avatar_url), authors:byline_author_id(id, name, slug, bio, photo_url, title)';
const SELECT_BASIC = 'id, slug, title, excerpt, cover_image_url, published_at, updated_at, featured, categories(name, slug), profiles(display_name, bio, avatar_url)';
let authorsJoinReady = true;
let extraColumnsReady = true;

function articleAuthor(article) {
  return authorFromArticle(article).name;
}

function authorAvatarHtml(author) {
  const initials = escapeHtml(authorInitials(author.name));
  if (!author.photo) {
    return `<span class="author-fallback" aria-hidden="true">${initials}</span>`;
  }
  return `<img class="author-avatar" src="${escapeHtml(author.photo)}" alt="${escapeHtml(author.name)}" data-fallback="${initials}" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'author-fallback',textContent:this.dataset.fallback}))">`;
}

function articleCover(article) {
  return article.cover_image_url || '';
}

function storyUrl(article) {
  return articleHref(article.slug);
}

function authorLinkHtml(article) {
  const author = authorFromArticle(article);
  if (author.slug) {
    return `<a href="${escapeHtml(authorHref(author.slug))}">${escapeHtml(author.name)}</a>`;
  }
  return escapeHtml(author.name);
}

function bylineHtml(article) {
  const when = formatDateTime(article.published_at) || formatDate(article.published_at);
  return `${authorLinkHtml(article)}<span class="meta-dot"></span>${escapeHtml(when)}`;
}

function emptyEdition(title, copy) {
  return `
    <div class="front-empty">
      <p class="kicker">The newsroom</p>
      <h1>${escapeHtml(title)}</h1>
      <p class="deck">${escapeHtml(copy)}</p>
    </div>
  `;
}

function breakingRibbon(article) {
  return article && article.is_breaking
    ? '<p class="breaking-kicker">Breaking News</p>'
    : '';
}

function leadHtml(article) {
  const cover = articleCover(article);
  const desk = articleDesk(article);
  return `
    <article class="lead-story${cover ? '' : ' no-image'}${article.is_breaking ? ' is-breaking' : ''}">
      ${cover ? `
         <a class="lead-media" href="${storyUrl(article)}">
           <img src="${escapeHtml(cover)}" alt="${escapeHtml(article.title)}" fetchpriority="high">
         </a>` : ''}
      <div class="lead-copy">
        ${breakingRibbon(article)}
        <p class="kicker"><a href="section.html?desk=${encodeURIComponent(desk)}">${escapeHtml(desk)}</a></p>
        <h1><a href="${storyUrl(article)}">${escapeHtml(article.title)}</a></h1>
        ${article.excerpt ? `<p class="deck">${escapeHtml(article.excerpt)}</p>` : ''}
        <p class="byline">${bylineHtml(article)}</p>
      </div>
    </article>
  `;
}

function secondaryHtml(article) {
  const cover = articleCover(article);
  const desk = articleDesk(article);
  return `
    <article class="secondary-story${cover ? '' : ' no-image'}">
      ${cover ? `
        <a class="secondary-media" href="${storyUrl(article)}">
          <img src="${escapeHtml(cover)}" alt="${escapeHtml(article.title)}" loading="lazy">
        </a>` : ''}
      <div>
        ${breakingRibbon(article)}
        <p class="kicker"><a href="section.html?desk=${encodeURIComponent(desk)}">${escapeHtml(desk)}</a></p>
        <h2><a href="${storyUrl(article)}">${escapeHtml(article.title)}</a></h2>
        ${article.excerpt ? `<p class="summary">${escapeHtml(article.excerpt)}</p>` : ''}
         <p class="byline">${authorLinkHtml(article)}<span class="meta-dot"></span>${escapeHtml(formatDate(article.published_at))}</p>
      </div>
    </article>
  `;
}

function railCardHtml(article) {
  const cover = articleCover(article);
  const desk = articleDesk(article);
  const author = authorFromArticle(article);
  const when = formatDate(article.published_at);
  return `
    <article class="rail-card">
      ${cover ? `
        <a class="rail-media" href="${storyUrl(article)}">
          <img src="${escapeHtml(cover)}" alt="${escapeHtml(article.title)}" loading="lazy">
        </a>` : `<a class="rail-media rail-media-empty" href="${storyUrl(article)}" aria-hidden="true"></a>`}
      <p class="kicker"><a href="section.html?desk=${encodeURIComponent(desk)}">${escapeHtml(desk)}</a></p>
      <h3><a href="${storyUrl(article)}">${escapeHtml(article.title)}</a></h3>
      <p class="byline">${author.slug ? `<a href="${escapeHtml(authorHref(author.slug))}">${escapeHtml(author.name)}</a>` : escapeHtml(author.name)}${when ? `<span class="meta-dot"></span>${escapeHtml(when)}` : ''}</p>
    </article>
  `;
}

function storyRailHtml(id, title, articles, moreHref, moreLabel) {
  if (!articles || !articles.length) return '';
  const count = articles.length;
  const mode = count === 1 ? 'is-one is-static' : (count === 2 ? 'is-few is-static' : '');
  const controls = count > 2 ? `
    <div class="rail-controls">
      <button type="button" class="rail-btn" data-rail-prev="${id}" aria-label="Previous stories">Prev</button>
      <button type="button" class="rail-btn" data-rail-next="${id}" aria-label="Next stories">Next</button>
    </div>` : '';
  const more = moreHref ? `<a class="section-more" href="${moreHref}">${escapeHtml(moreLabel || 'All stories')}</a>` : '';
  return `
    <section class="story-rail ${mode}" data-rail="${id}">
      <div class="section-head">
        <h2>${moreHref ? `<a href="${moreHref}">${escapeHtml(title)}</a>` : escapeHtml(title)}</h2>
        <div class="rail-head-tools">${more}${controls}</div>
      </div>
      <div class="rail-viewport">
        <div class="rail-track" id="${id}">
          ${articles.map(railCardHtml).join('')}
        </div>
      </div>
    </section>
  `;
}

function bindRails(root) {
  const scope = root || document;
  scope.querySelectorAll('[data-rail-prev], [data-rail-next]').forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', () => {
      const id = btn.dataset.railPrev || btn.dataset.railNext;
      const track = document.getElementById(id);
      if (!track) return;
      const card = track.querySelector('.rail-card');
      const delta = card ? card.getBoundingClientRect().width + 18 : 280;
      track.scrollBy({ left: btn.dataset.railNext ? delta : -delta, behavior: 'smooth' });
    });
  });
}

function resultItemHtml(article) {
  const desk = articleDesk(article);
  const cover = articleCover(article);
  return `
    <article class="result-item${cover ? ' has-image' : ''}">
      ${cover ? `<a class="result-media" href="${storyUrl(article)}"><img src="${escapeHtml(cover)}" alt="${escapeHtml(article.title)}" loading="lazy"></a>` : ''}
      <div>
        ${breakingRibbon(article)}
        <p class="kicker"><a href="section.html?desk=${encodeURIComponent(desk)}">${escapeHtml(desk)}</a></p>
        <h2><a href="${storyUrl(article)}">${escapeHtml(article.title)}</a></h2>
        ${article.excerpt ? `<p>${escapeHtml(article.excerpt)}</p>` : ''}
        <p class="byline">${authorLinkHtml(article)} · ${escapeHtml(formatDate(article.published_at))}</p>
      </div>
    </article>
  `;
}

function groupByDesk(articles) {
  const groups = {};
  articles.forEach((article) => {
    const desk = articleDesk(article);
    if (!groups[desk]) groups[desk] = [];
    groups[desk].push(article);
  });
  const extras = Object.keys(groups).filter((desk) => !SECTION_ORDER.includes(desk));
  return SECTION_ORDER.concat(extras).filter((desk) => groups[desk] && groups[desk].length).map((desk) => ({
    desk,
    stories: groups[desk]
  }));
}

function renderFront(articles) {
  const root = document.getElementById('frontPage');
  if (!root) return;
  const breaking = articles.find((item) => item.is_breaking);
  const featuredPool = articles.filter((item) => item.featured);
  const lead = breaking || featuredPool[0] || articles[0];
  const secondary = articles.filter((item) => item.slug !== lead.slug).slice(0, 3);
  const latest = articles.slice(0, 12);
  const featured = (featuredPool.length ? featuredPool : articles.slice(0, 6)).slice(0, 12);
  const picks = articles.filter((item) => item.editors_pick).slice(0, 12);
  const trending = articles
    .filter((item) => Number(item.view_count) > 0)
    .sort((a, b) => Number(b.view_count || 0) - Number(a.view_count || 0))
    .slice(0, 8);
  const used = new Set([lead.slug, ...secondary.map((item) => item.slug)]);
  const remainder = articles.filter((item) => !used.has(item.slug));
  const sectionSource = remainder.length ? remainder : articles.slice(1);
  const sections = groupByDesk(sectionSource);

  const secondaryMarkup = secondary.length ? `
    <div class="secondary-col">
      ${secondary.map(secondaryHtml).join('')}
    </div>
  ` : '';

  const featuredMarkup = featured.length
    ? storyRailHtml('featuredRail', 'Featured Story', featured)
    : '';
  const latestMarkup = latest.length
    ? storyRailHtml('latestRail', 'Latest Stories', latest)
    : '';
  const trendingMarkup = trending.length
    ? storyRailHtml('trendingRail', 'Trending', trending)
    : '';
  const picksMarkup = picks.length
    ? storyRailHtml('picksRail', 'Editor’s Picks', picks)
    : '';
  const sectionMarkup = sections.map(({ desk, stories }) => (
    storyRailHtml(
      `desk-${desk.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
      desk,
      stories.slice(0, 12),
      `section.html?desk=${encodeURIComponent(desk)}`,
      `All ${desk}`
    )
  )).join('');

  root.innerHTML = `
    <div class="front-grid${secondary.length ? '' : ' solo'}">
      ${leadHtml(lead)}
      ${secondaryMarkup}
    </div>
    ${featuredMarkup}
    ${latestMarkup}
    ${trendingMarkup}
    ${picksMarkup}
    ${sectionMarkup}
  `;
  bindRails(root);
}

async function fetchPublished(limit) {
  const client = getClient();
  const select = authorsJoinReady ? SELECT_WITH_AUTHORS : SELECT_BASIC;
  let query = client
    .from('articles')
    .select(select)
    .eq('status', 'published')
    .order('published_at', { ascending: false });
  if (limit) query = query.limit(limit);
  const { data, error } = await query;
  if (error) {
    const message = String(error.message || error.details || '');
    if (authorsJoinReady && /authors|byline_author/i.test(message)) {
      authorsJoinReady = false;
      return fetchPublished(limit);
    }
    extraColumnsReady = !/editors_pick|is_breaking|view_count|pdf_url/i.test(message);
    if (/featured|updated_at|editors_pick|is_breaking|view_count|pdf_url|, title/i.test(message)) {
      const trimmed = (authorsJoinReady ? SELECT_WITH_AUTHORS : SELECT_BASIC)
        .replace(', featured', '')
        .replace(', updated_at', '')
        .replace(', editors_pick', '')
        .replace(', is_breaking', '')
        .replace(', view_count', '')
        .replace(', pdf_url', '')
        .replace(', title', '');
      const fallback = await client
        .from('articles')
        .select(trimmed)
        .eq('status', 'published')
        .order('published_at', { ascending: false })
        .limit(limit || 80);
      if (fallback.error) throw fallback.error;
      return fallback.data || [];
    }
    throw error;
  }
  return data || [];
}

async function loadHomeStories() {
  const root = document.getElementById('frontPage');
  if (!root) return;
  if (!isConfigured()) {
    root.innerHTML = emptyEdition(
      'Connect the newsroom',
      'Add the Supabase project URL and anon key in Admin to load published essays.'
    );
    return;
  }
  try {
    const data = await fetchPublished(80);
    if (!data.length) {
      root.innerHTML = emptyEdition(
        'No published stories yet',
        'Drafts stay private until an editor publishes them from the newsroom.'
      );
      return;
    }
    renderFront(data);
  } catch (error) {
    root.innerHTML = emptyEdition(
      'Stories could not be loaded',
      'Check the project connection in Admin, then refresh this page.'
    );
  }
}

function setArticleState(page, state) {
  page.classList.toggle('is-loading', state === 'loading');
  page.classList.toggle('is-empty', state === 'empty' || state === 'error');
}

function documentControl(article) {
  const pdfUrl = article.pdf_url || articleDocumentUrl(article);
  if (!pdfUrl) return '';
  return `
    <div class="document-panel">
      <p class="kicker">Print edition</p>
      <p class="document-copy">Download a newspaper-style PDF of this LouieCorp article, or print the page directly.</p>
      <div class="document-actions">
        <a class="doc-btn" href="${escapeHtml(pdfUrl)}" target="_blank" rel="noopener noreferrer" download>Download PDF</a>
        <button class="doc-btn ghost" type="button" onclick="window.print()">Print</button>
      </div>
    </div>
  `;
}

function shareBarHtml(article) {
  const url = siteUrl(articleHref(article.slug));
  const cardUrl = shareCardUrl(article.slug) || url;
  const shares = shareTargets(url, article.title, { cardUrl });
  return `
    <div class="share-bar" role="group" aria-label="Share this article">
      <p class="kicker">Share</p>
      <div class="share-actions">
        <a class="share-btn" href="${shares.x}" target="_blank" rel="noopener noreferrer">X</a>
        <a class="share-btn" href="${shares.facebook}" target="_blank" rel="noopener noreferrer">Facebook</a>
        <a class="share-btn" href="${shares.whatsapp}" target="_blank" rel="noopener noreferrer">WhatsApp</a>
        <button class="share-btn" type="button" data-copy-link="${escapeHtml(url)}">Copy Link</button>
      </div>
    </div>
  `;
}

function bindShareBar(root) {
  const button = root && root.querySelector('[data-copy-link]');
  if (!button || button.dataset.bound) return;
  button.dataset.bound = '1';
  button.addEventListener('click', async () => {
    const value = button.getAttribute('data-copy-link');
    try {
      await navigator.clipboard.writeText(value);
      button.textContent = 'Copied';
      setTimeout(() => { button.textContent = 'Copy Link'; }, 1600);
    } catch (error) {
      window.prompt('Copy this link', value);
    }
  });
}

async function recordArticleView(slug) {
  if (!slug) return;
  try {
    const client = getClient();
    await client.rpc('increment_article_views', { article_slug: slug });
  } catch (error) {
    /* Views remain optional if the function is not yet applied. */
  }
}

function articleSourceNote(article) {
  const credit = String(article.source_credit || article.source || article.attribution || '').trim();
  const url = String(article.source_url || '').trim();
  const isHttp = /^https?:\/\//i.test(url);
  if (!credit && !isHttp) return '';
  const label = escapeHtml(credit || 'Source');
  if (isHttp) {
    const host = (() => {
      try { return new URL(url).hostname.replace(/^www\./, ''); } catch (error) { return url; }
    })();
    return `<p class="source-note">Source: ${credit ? `${label}` : ''}${credit && host ? ' — ' : ''}<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(credit ? host : url)}</a></p>`;
  }
  return `<p class="source-note">Source: ${label}</p>`;
}

function authorNameHtml(author) {
  const name = escapeHtml(author.name);
  if (author.slug) {
    return `<a href="${escapeHtml(authorHref(author.slug))}" itemprop="url"><span itemprop="name">${name}</span></a>`;
  }
  return `<span itemprop="name">${name}</span>`;
}

async function loadRelated(current, desk) {
  const wrap = document.getElementById('relatedStories');
  if (!wrap) return;
  try {
    const stories = await fetchPublished(16);
    const related = stories.filter((item) => item.slug !== current && articleDesk(item) === desk);
    const fill = related.concat(stories.filter((item) => item.slug !== current && !related.includes(item))).slice(0, 8);
    if (!fill.length) return;
    wrap.hidden = false;
    wrap.innerHTML = storyRailHtml('relatedRail', 'More from LouieCorp', fill);
    bindRails(wrap);
  } catch (error) {
    wrap.hidden = true;
  }
}

function stripRepeatedHeadline(html, title) {
  const value = String(html || '');
  const headline = String(title || '').trim();
  if (!headline || !value) return value;
  const wrap = document.createElement('div');
  wrap.innerHTML = value;
  const first = wrap.querySelector('p');
  if (!first) return value;
  const text = (first.textContent || '').replace(/\s+/g, ' ').trim();
  const bylineLike = /^(by\s+)/i.test(text);
  if (text === headline || bylineLike && /editorial|louiecorp|sentongo/i.test(text)) {
    first.remove();
  }
  const second = wrap.querySelector('p');
  if (second) {
    const secondText = (second.textContent || '').replace(/\s+/g, ' ').trim();
    if (/^by\s+/i.test(secondText) && /editorial|louiecorp|sentongo/i.test(secondText)) {
      second.remove();
    }
  }
  return wrap.innerHTML;
}

async function loadArticlePage() {
  const page = document.querySelector('.story-page');
  if (!page) return;
  document.body.classList.add('has-story');
  const slug = readArticleSlug();
  const categoryEl = page.querySelector('.category');
  const titleEl = page.querySelector('h1');
  const deckEl = page.querySelector('.article-deck');
  const meta = page.querySelector('.article-meta');
  const coverWrap = page.querySelector('.article-cover');
  const cover = page.querySelector('.article-cover img');
  const caption = page.querySelector('.article-caption');
  const prose = page.querySelector('.prose');
  const tagsEl = page.querySelector('.article-tags');
  const docEl = page.querySelector('.article-document');
  const sourceEl = document.getElementById('articleSource');
  const authorPanel = document.getElementById('authorPanel');

  function emptyStory(title, copy) {
    setArticleState(page, 'empty');
    document.title = `${title} — LouieCorp`;
    const robots = document.querySelector('meta[name="robots"]');
    if (robots) robots.setAttribute('content', 'noindex,follow');
    categoryEl.textContent = 'Library';
    titleEl.textContent = title;
    deckEl.hidden = false;
    deckEl.textContent = copy;
    meta.innerHTML = '';
    prose.innerHTML = '';
    if (tagsEl) tagsEl.innerHTML = '';
    if (coverWrap) coverWrap.hidden = true;
    if (docEl) {
      docEl.hidden = true;
      docEl.innerHTML = '';
    }
    if (sourceEl) {
      sourceEl.hidden = true;
      sourceEl.innerHTML = '';
    }
    if (authorPanel) {
      authorPanel.hidden = true;
      authorPanel.innerHTML = '';
    }
  }

  if (!slug) {
    emptyStory('Story not found', 'Open a published essay from the LouieCorp front page.');
    return;
  }
  if (!isConfigured()) {
    emptyStory('Newsroom not connected', 'Add the Supabase project URL and anon key in Admin.');
    return;
  }

  setArticleState(page, 'loading');
  categoryEl.textContent = 'Loading';
  titleEl.textContent = 'Opening story';
  deckEl.hidden = false;
  deckEl.textContent = 'Fetching the published essay.';
  meta.innerHTML = '';
  prose.innerHTML = '<p>Loading...</p>';

  try {
    const client = getClient();
    let query = client
      .from('articles')
      .select('*, categories(name, slug), profiles(display_name, bio, avatar_url), authors:byline_author_id(id, name, slug, bio, photo_url, title), article_tags(tags(name))')
      .eq('slug', slug)
      .eq('status', 'published')
      .single();
    let { data, error } = await query;
    if (error && /authors|byline_author/i.test(String(error.message || ''))) {
      authorsJoinReady = false;
      const retry = await client
        .from('articles')
        .select('*, categories(name, slug), profiles(display_name, bio, avatar_url), article_tags(tags(name))')
        .eq('slug', slug)
        .eq('status', 'published')
        .single();
      data = retry.data;
      error = retry.error;
    }
    if (error) throw error;
    const desk = publicDesk(data.categories && data.categories.name);
    const author = authorFromArticle(data);
    const tags = (data.article_tags || []).map((row) => row.tags && row.tags.name).filter(Boolean);
    const publishedLabel = formatDate(data.published_at) || formatDate(data.updated_at) || formatDateTime(data.published_at);
    const updatedLabel = data.updated_at && isoDate(data.updated_at) !== isoDate(data.published_at)
      ? formatDate(data.updated_at)
      : '';
    const publishedIso = isoDate(data.published_at) || isoDate(data.updated_at);
    const updatedIso = isoDate(data.updated_at) || publishedIso;
    const summary = excerptFrom(data);
    applyArticleHead(data, author, { desk, tags });
    if (data.is_breaking) page.classList.add('is-breaking');
    categoryEl.innerHTML = `${data.is_breaking ? '<span class="breaking-kicker">Breaking News</span> ' : ''}<a href="section.html?desk=${encodeURIComponent(desk)}">${escapeHtml(desk)}</a>`;
    categoryEl.setAttribute('itemprop', 'articleSection');
    titleEl.textContent = data.title;
    deckEl.textContent = data.excerpt || summary;
    deckEl.hidden = !deckEl.textContent;
    const minutes = readingTime(data.content);
    const updatedLine = updatedLabel
      ? `<p class="byline-updated">Updated <time datetime="${escapeHtml(updatedIso)}" itemprop="dateModified">${escapeHtml(updatedLabel)}</time></p>`
      : (updatedIso ? `<meta itemprop="dateModified" content="${escapeHtml(updatedIso)}">` : '');
    const publishedLine = publishedLabel
      ? `<p class="byline-date">Published <time datetime="${escapeHtml(publishedIso)}" itemprop="datePublished">${escapeHtml(publishedLabel)}</time></p>`
      : '';
    const roleLine = author.title ? `<p class="byline-role">${escapeHtml(author.title)}</p>` : '';
    meta.innerHTML = `
      <div class="author-lockup">
        ${authorAvatarHtml(author)}
        <div>
          <p class="byline-author">By <span itemprop="author" itemscope itemtype="https://schema.org/Person">${authorNameHtml(author)}</span></p>
          ${roleLine}
          <p class="byline-publisher"><span itemprop="publisher" itemscope itemtype="https://schema.org/NewsMediaOrganization"><span itemprop="name">${escapeHtml(PUBLISHER_NAME)}</span></span></p>
          ${publishedLine}
          ${updatedLine}
          <p class="byline-read">${minutes} min read</p>
        </div>
      </div>
    `;
    if (data.cover_image_url) {
      coverWrap.hidden = false;
      cover.src = publicImageUrl(data.cover_image_url);
      cover.alt = data.title;
      if (caption) {
        const credit = data.image_caption || data.caption || '';
        caption.textContent = credit;
        caption.hidden = !credit;
      }
    } else {
      coverWrap.hidden = true;
    }
    const docMarkup = documentControl(data);
    if (docEl) {
      docEl.innerHTML = `${shareBarHtml(data)}${docMarkup}`;
      docEl.hidden = false;
      bindShareBar(docEl);
    }
    prose.innerHTML = stripRepeatedHeadline(renderBody(data.content), data.title);
    if (tagsEl) {
      tagsEl.innerHTML = tags.map((tag) => `<a class="topic-tag" href="search.html?q=${encodeURIComponent(tag)}">${escapeHtml(tag)}</a>`).join('');
    }
    if (sourceEl) {
      const sourceMarkup = articleSourceNote(data);
      sourceEl.innerHTML = sourceMarkup;
      sourceEl.hidden = !sourceMarkup;
    }
    if (authorPanel) {
      authorPanel.hidden = false;
      const profileLink = author.slug
        ? `<p class="author-more"><a href="${escapeHtml(authorHref(author.slug))}">More from ${escapeHtml(author.name)}</a></p>`
        : '';
      authorPanel.innerHTML = `
        ${authorAvatarHtml(author)}
        <div>
          <p class="kicker">The author</p>
          <h2>${author.slug ? `<a href="${escapeHtml(authorHref(author.slug))}">${escapeHtml(author.name)}</a>` : escapeHtml(author.name)}</h2>
          ${author.title ? `<p class="byline-role">${escapeHtml(author.title)}</p>` : ''}
          ${author.bio ? `<p>${escapeHtml(author.bio)}</p>` : `<p>${escapeHtml(author.name)} writes for ${escapeHtml(PUBLISHER_NAME)}.</p>`}
          ${profileLink}
        </div>
      `;
    }
    setArticleState(page, 'ready');
    recordArticleView(slug);
    loadRelated(slug, desk);
  } catch (error) {
    emptyStory('Story not found', 'This article is unpublished, deleted, or the link is incomplete.');
  }
}

function matchesQuery(article, query) {
  const hay = [
    article.title,
    article.excerpt,
    article.content,
    articleDesk(article),
    articleAuthor(article),
    ((article.article_tags || []).map((row) => row.tags && row.tags.name).filter(Boolean).join(' '))
  ].join(' ').toLowerCase();
  return hay.includes(query);
}

async function loadSearchPage() {
  const results = document.getElementById('searchResults');
  const status = document.getElementById('searchStatus');
  const field = document.getElementById('searchField');
  if (!results || !status) return;
  const params = new URLSearchParams(window.location.search);
  const query = (params.get('q') || '').trim();
  if (field) field.value = query;
  const mast = document.getElementById('mastSearch');
  if (mast && query) mast.value = query;
  if (!query) {
    status.textContent = 'Enter a term to search published articles.';
    results.innerHTML = '';
    return;
  }
  document.title = `Search: ${query} — LouieCorp`;
  if (!isConfigured()) {
    status.textContent = 'Add the Supabase project URL and anon key in Admin to search the library.';
    return;
  }
  status.textContent = `Searching for “${query}”...`;
  try {
    const client = getClient();
    let data = [];
    try {
      const searchSelect = (authorsJoinReady ? SELECT_WITH_AUTHORS : SELECT_BASIC) + ', content, article_tags(tags(name))';
      const searched = await client
        .from('articles')
        .select(searchSelect)
        .eq('status', 'published')
        .order('published_at', { ascending: false })
        .limit(120);
      if (searched.error) throw searched.error;
      data = searched.data || [];
    } catch (error) {
      data = await fetchPublished(80);
    }
    const needle = query.toLowerCase();
    const matches = data.filter((article) => matchesQuery(article, needle));
    if (!matches.length) {
      status.textContent = `No published stories matched “${query}”.`;
      results.innerHTML = '';
      return;
    }
    status.textContent = `${matches.length} stor${matches.length === 1 ? 'y' : 'ies'} matching “${query}”.`;
    results.innerHTML = matches.map(resultItemHtml).join('');
  } catch (error) {
    status.textContent = 'Search could not be completed. Check the newsroom connection in Admin.';
  }
}

const SECTION_INTRO = {
  Politics: 'Power, institutions and the contest for public office.',
  Business: 'Markets, work and the economic decisions that shape public life.',
  Technology: 'The systems, companies and ideas remaking public and private life.',
  Africa: 'Politics, society and development across the continent.',
  World: 'Diplomacy, conflict and the forces shaping international affairs.',
  Society: 'The ordinary lives, institutions and questions that hold a nation together.',
  Culture: 'Arts, letters, faith and the stories a society tells about itself.',
  Opinion: 'Arguments from LouieCorp contributors, published in their own names.',
  Investigations: 'Reported inquiries into power, money and the public record.',
  Governance: 'How authority is exercised, constrained and held to account.',
  Analysis: 'Explainers, history and reporting that outlast the news cycle.',
  Faith: 'Belief, ethics and the public witness of religious communities.',
  Ideas: 'Essays, philosophy and arguments that reward attention.'
};

async function loadSectionPage() {
  const titleEl = document.getElementById('sectionTitle');
  const lede = document.getElementById('sectionLede');
  const kicker = document.getElementById('sectionKicker');
  const lead = document.getElementById('sectionLead');
  const results = document.getElementById('sectionResults');
  if (!titleEl || !results) return;
  const params = new URLSearchParams(window.location.search);
  const requested = (params.get('desk') || 'Politics').trim();
  const desk = publicDesk(requested);
  titleEl.textContent = desk;
  if (kicker) kicker.textContent = 'Section';
  document.title = `${desk} — LouieCorp`;
  document.querySelectorAll('.nav-links a').forEach((link) => {
    const href = link.getAttribute('href') || '';
    link.classList.toggle('is-current', href.toLowerCase().includes(`desk=${desk.toLowerCase()}`));
  });
  if (!isConfigured()) {
    lede.textContent = 'Add the Supabase project URL and anon key in Admin to load this desk.';
    return;
  }
  lede.textContent = SECTION_INTRO[desk] || 'Published stories from this desk.';
  try {
    const data = await fetchPublished(80);
    const stories = data.filter((article) => articleDesk(article).toLowerCase() === desk.toLowerCase());
    if (!stories.length) {
      lede.textContent = `No published stories in ${desk} yet.`;
      lead.innerHTML = '';
      results.innerHTML = '';
      return;
    }
    const feature = stories[0];
    lead.innerHTML = leadHtml(feature);
    const rest = stories.slice(1);
    results.innerHTML = rest.length
      ? storyRailHtml('sectionRail', `More in ${desk}`, rest)
      : '';
    bindRails(results);
  } catch (error) {
    lede.textContent = 'This section could not be loaded.';
  }
}

async function loadAuthorPage() {
  const page = document.getElementById('authorPage');
  if (!page) return;
  const nameEl = document.getElementById('authorName');
  const bioEl = document.getElementById('authorBio');
  const hero = document.getElementById('authorHero');
  const list = document.getElementById('authorStories');
  const params = new URLSearchParams(window.location.search);
  const slug = (params.get('slug') || '').trim();
  const { upsertMeta, upsertLink, setJsonLd, authorCanonicalUrl, siteUrl } = window.LouieCorp;

  function emptyAuthor(title, copy) {
    document.title = `${title} — LouieCorp`;
    const robots = document.querySelector('meta[name="robots"]');
    if (robots) robots.setAttribute('content', 'noindex,follow');
    if (nameEl) nameEl.textContent = title;
    if (bioEl) bioEl.textContent = copy;
    if (list) list.innerHTML = '';
  }

  if (!slug) {
    emptyAuthor('Author not found', 'Open an author page from a published LouieCorp article.');
    return;
  }
  if (!isConfigured()) {
    emptyAuthor('Newsroom not connected', 'Add the Supabase project URL and anon key in Admin.');
    return;
  }

  try {
    const client = getClient();
    let authorQuery = await client
      .from('authors')
      .select('id, name, slug, bio, photo_url, title')
      .eq('slug', slug)
      .maybeSingle();
    if (authorQuery.error && /title/i.test(String(authorQuery.error.message || ''))) {
      authorQuery = await client
        .from('authors')
        .select('id, name, slug, bio, photo_url')
        .eq('slug', slug)
        .maybeSingle();
    }
    const { data: author, error } = authorQuery;
    if (error) throw error;
    if (!author) {
      emptyAuthor('Author not found', 'This author page is missing or the link is incomplete.');
      return;
    }
    let stories = [];
    const select = authorsJoinReady ? SELECT_WITH_AUTHORS : SELECT_BASIC;
    let authored = await client
      .from('articles')
      .select(select)
      .eq('status', 'published')
      .eq('byline_author_id', author.id)
      .order('published_at', { ascending: false });
    if (authored.error && /byline_author/i.test(String(authored.error.message || ''))) {
      stories = (await fetchPublished(80)).filter((item) => authorFromArticle(item).name === author.name);
    } else if (authored.error) {
      throw authored.error;
    } else {
      stories = authored.data || [];
    }
    const pageUrl = authorCanonicalUrl(author.slug);
    const description = author.bio
      ? excerptFrom({ excerpt: author.bio })
      : `${author.name} writes for ${PUBLISHER_NAME}.`;
    document.title = `${author.name} — LouieCorp`;
    upsertMeta('name', 'robots', 'index,follow');
    upsertMeta('name', 'description', description);
    upsertMeta('name', 'author', author.name);
    upsertLink('canonical', pageUrl);
    upsertMeta('property', 'og:site_name', PUBLISHER_NAME);
    upsertMeta('property', 'og:title', `${author.name} — LouieCorp`);
    upsertMeta('property', 'og:description', description);
    upsertMeta('property', 'og:type', 'profile');
    upsertMeta('property', 'og:url', pageUrl);
    if (author.photo_url) upsertMeta('property', 'og:image', author.photo_url);
    upsertMeta('name', 'twitter:card', author.photo_url ? 'summary_large_image' : 'summary');
    upsertMeta('name', 'twitter:title', `${author.name} — LouieCorp`);
    upsertMeta('name', 'twitter:description', description);
    if (author.photo_url) upsertMeta('name', 'twitter:image', author.photo_url);
    setJsonLd('authorJsonLd', {
      '@context': 'https://schema.org',
      '@type': 'Person',
      name: author.name,
      description,
      image: author.photo_url || undefined,
      url: pageUrl,
      worksFor: {
        '@type': 'NewsMediaOrganization',
        name: PUBLISHER_NAME,
        url: siteUrl('/')
      }
    });
    if (hero) {
      hero.innerHTML = `
        <div class="author-hero-lockup">
          ${authorAvatarHtml({ name: author.name, photo: author.photo_url || '' })}
          <div>
            <p class="kicker">The author</p>
            <h1 id="authorName">${escapeHtml(author.name)}</h1>
            <p class="archive-lede" id="authorBio">${escapeHtml(author.bio || `${author.name} writes for ${PUBLISHER_NAME}.`)}</p>
            ${author.title ? `<p class="byline-role">${escapeHtml(author.title)}</p>` : ''}
            <p class="byline-publisher">${escapeHtml(PUBLISHER_NAME)}</p>
          </div>
        </div>
      `;
    }
    if (!stories.length) {
      upsertMeta('name', 'robots', 'noindex,follow');
      if (list) list.innerHTML = '<p class="archive-lede">No published LouieCorp articles by this author yet.</p>';
      return;
    }
    if (list) {
      list.innerHTML = stories.map((article) => `
        <article class="result-item">
          <p class="kicker"><a href="section.html?desk=${encodeURIComponent(articleDesk(article))}">${escapeHtml(articleDesk(article))}</a></p>
          <h2><a href="${storyUrl(article)}">${escapeHtml(article.title)}</a></h2>
          ${article.excerpt ? `<p>${escapeHtml(article.excerpt)}</p>` : ''}
          <p class="byline">Published ${escapeHtml(formatDate(article.published_at))}</p>
        </article>
      `).join('');
    }
  } catch (error) {
    emptyAuthor('Author not found', 'This author page could not be loaded.');
  }
}

async function loadSitemapPage() {
  const root = document.getElementById('sitemapRoot');
  const status = document.getElementById('sitemapStatus');
  if (!root) return;
  if (!isConfigured()) {
    if (status) status.textContent = 'Add the Supabase project URL and anon key in Admin to load the published index.';
    return;
  }
  try {
    const articles = await fetchPublished(200);
    const authors = [];
    const seen = new Set();
    articles.forEach((article) => {
      const author = authorFromArticle(article);
      if (author.slug && !seen.has(author.slug)) {
        seen.add(author.slug);
        authors.push(author);
      }
    });
    const sections = SECTION_ORDER.map((desk) => (
      `<li><a href="section.html?desk=${encodeURIComponent(desk)}">${escapeHtml(desk)}</a></li>`
    )).join('');
    const authorLinks = authors.map((author) => (
      `<li><a href="${escapeHtml(authorHref(author.slug))}">${escapeHtml(author.name)}</a></li>`
    )).join('');
    const storyLinks = articles.map((article) => `
      <li>
        <a href="${storyUrl(article)}">${escapeHtml(article.title)}</a>
        <span class="sitemap-meta">${escapeHtml(articleAuthor(article))} · ${escapeHtml(formatDate(article.published_at))}</span>
      </li>
    `).join('');
    if (status) {
      status.textContent = articles.length
        ? `${articles.length} published ${articles.length === 1 ? 'article' : 'articles'}. Drafts, deleted stories and the newsroom are not listed.`
        : 'No published articles yet. Drafts stay out of the public index.';
    }
    root.innerHTML = `
      <section class="sitemap-block">
        <h2>The publication</h2>
        <ul class="sitemap-list">
          <li><a href="index.html">Home</a></li>
          <li><a href="about.html">About</a></li>
          <li><a href="editorial-policy.html">Editorial Policy</a></li>
          <li><a href="corrections.html">Corrections</a></li>
          <li><a href="contact.html">Contact Newsroom</a></li>
          <li><a href="submit.html">Submit a Story</a></li>
          <li><a href="search.html">Search</a></li>
          <li><a href="privacy.html">Privacy</a></li>
          <li><a href="terms.html">Terms</a></li>
          <li><a href="advertising.html">Advertising</a></li>
          <li><a href="rss.xml">RSS</a></li>
        </ul>
      </section>
      <section class="sitemap-block">
        <h2>Sections</h2>
        <ul class="sitemap-list">${sections}</ul>
      </section>
      ${authors.length ? `<section class="sitemap-block"><h2>Authors</h2><ul class="sitemap-list">${authorLinks}</ul></section>` : ''}
      <section class="sitemap-block">
        <h2>Published articles</h2>
        <ul class="sitemap-list sitemap-articles">${storyLinks || '<li>No published articles.</li>'}</ul>
      </section>
    `;
  } catch (error) {
    if (status) status.textContent = 'The published index could not be loaded.';
  }
}

loadHomeStories();
loadArticlePage();
loadSearchPage();
loadSectionPage();
loadAuthorPage();
loadSitemapPage();
