if (!window.LouieCorp) {
  throw new Error('LouieCorp client failed to load. Include js/config.js and js/supabase-client.js before admin.js.');
}

const {
  readStoredConfig,
  saveStoredConfig,
  isConfigured,
  getClient,
  slugify,
  uniqueMediaKey,
  uploadMediaFile,
  formatDate,
  escapeHtml,
  publicDesk,
  articleHref,
  siteUrl
} = window.LouieCorp;

const setupPanel = document.getElementById('setupPanel');
const authPanel = document.getElementById('authPanel');
const dashboard = document.getElementById('dashboard');
const libraryView = document.getElementById('libraryView');
const editorView = document.getElementById('editorView');
const notice = document.getElementById('adminNotice');
const editorTitle = document.getElementById('editorTitle');
const editorStatus = document.getElementById('editorStatus');
const coverPreview = document.getElementById('coverPreview');
const authorPreview = document.getElementById('authorPreview');
const authorSelect = document.getElementById('authorSelect');
const tableBody = document.getElementById('articleTableBody');
const cardList = document.getElementById('articleCardList');
const form = document.getElementById('articleForm');
const categorySelect = document.getElementById('category');
const libraryFilter = document.getElementById('libraryFilter');
const signOutBtn = document.getElementById('signOutBtn');
const newStoryBtn = document.getElementById('newStoryBtn');
const changeSetupBtn = document.getElementById('changeSetupBtn');
const backToLibraryBtn = document.getElementById('backToLibraryBtn');
const unpublishBtn = document.getElementById('unpublishBtn');
const deleteBtn = document.getElementById('deleteBtn');
const documentNote = document.getElementById('documentNote');

let client = null;
let currentUser = null;
let currentProfile = null;
let editingId = null;
let existingCoverUrl = '';
let existingAuthorPhotoUrl = '';
let existingDocumentUrl = '';
let categories = [];
let authors = [];
let articlesCache = [];
let busy = false;
let authorsTableReady = true;
let documentColumnReady = true;
let sourceColumnsReady = true;
let extraFlagsReady = true;
let authorTitleReady = true;

function toDatetimeLocal(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromDatetimeLocal(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toISOString();
}

function showNotice(message, kind) {
  notice.textContent = message;
  notice.hidden = !message;
  notice.classList.toggle('error', kind === 'error');
}

function showPanel(name) {
  setupPanel.hidden = name !== 'setup';
  authPanel.hidden = name !== 'auth';
  dashboard.hidden = name !== 'dashboard';
  signOutBtn.hidden = name !== 'dashboard';
}

function fillSetupFields() {
  const stored = readStoredConfig();
  const urlInput = document.getElementById('supabaseUrl');
  const keyInput = document.getElementById('supabaseKey');
  if (urlInput) urlInput.value = stored.url;
  if (keyInput) keyInput.value = stored.key;
}

function showSetupFallback() {
  fillSetupFields();
  showPanel('setup');
}

function applySavedConfig() {
  if (!isConfigured()) {
    showSetupFallback();
    return false;
  }
  showPanel('auth');
  return true;
}

function showLibrary() {
  libraryView.hidden = false;
  editorView.hidden = true;
}

function showEditor() {
  libraryView.hidden = true;
  editorView.hidden = false;
  editorView.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function setBusy(state) {
  busy = state;
  form.querySelectorAll('button, input, select, textarea').forEach((el) => {
    if (el.type === 'file') return;
    el.disabled = state;
  });
  unpublishBtn.disabled = state;
  deleteBtn.disabled = state;
  newStoryBtn.disabled = state;
}

function previewCover(file, url) {
  if (file) {
    const reader = new FileReader();
    reader.onload = () => {
      coverPreview.innerHTML = `<img src="${reader.result}" alt="Cover preview">`;
    };
    reader.readAsDataURL(file);
    return;
  }
  if (url) {
    coverPreview.innerHTML = `<img src="${escapeHtml(url)}" alt="Cover preview">`;
    return;
  }
  coverPreview.innerHTML = '<span>No cover selected yet</span>';
}

function previewAuthor(file, url) {
  if (!authorPreview) return;
  if (file) {
    const reader = new FileReader();
    reader.onload = () => {
      authorPreview.innerHTML = `<img src="${reader.result}" alt="Author preview">`;
    };
    reader.readAsDataURL(file);
    return;
  }
  if (url) {
    authorPreview.innerHTML = `<img src="${escapeHtml(url)}" alt="Author preview">`;
    return;
  }
  authorPreview.innerHTML = '<span>No portrait selected</span>';
}

function fillAuthors(selectedId) {
  if (!authorSelect) return;
  const options = ['<option value="">Sentongo. R. Louis</option>'];
  authors.forEach((item) => {
    options.push(`<option value="${item.id}" ${item.id === selectedId ? 'selected' : ''}>${escapeHtml(item.name)}</option>`);
  });
  options.push('<option value="__new">New author</option>');
  authorSelect.innerHTML = options.join('');
  if (selectedId && authors.some((item) => item.id === selectedId)) {
    authorSelect.value = selectedId;
  }
  applyAuthorSelection();
}

function applyAuthorSelection() {
  if (!authorSelect) return;
  const value = authorSelect.value;
  const nameField = document.getElementById('authorName');
  const bioField = document.getElementById('authorBio');
  if (value && value !== '__new') {
    const author = authors.find((item) => item.id === value);
    if (author) {
      nameField.value = author.name || '';
      bioField.value = author.bio || '';
      if (form.authorTitle) form.authorTitle.value = author.title || '';
      existingAuthorPhotoUrl = author.photo_url || '';
      previewAuthor(null, existingAuthorPhotoUrl);
    }
    return;
  }
  if (value === '__new') {
    nameField.value = '';
    bioField.value = '';
    if (form.authorTitle) form.authorTitle.value = '';
    existingAuthorPhotoUrl = '';
    previewAuthor();
    return;
  }
  nameField.value = 'Sentongo. R. Louis';
  bioField.value = '';
  if (form.authorTitle) form.authorTitle.value = '';
  existingAuthorPhotoUrl = '';
  previewAuthor();
}

function fillCategories(selectedId) {
  if (!categories.length) {
    categorySelect.innerHTML = '<option value="">No categories found</option>';
    return;
  }
  categorySelect.innerHTML = categories.map((item) => (
    `<option value="${item.id}" ${item.id === selectedId ? 'selected' : ''}>${escapeHtml(item.name)}</option>`
  )).join('');
}

function setEditorChrome(status) {
  const label = !editingId
    ? 'Unsaved draft'
    : status === 'published'
      ? 'Published'
      : 'Draft';
  editorStatus.textContent = label;
  editorStatus.classList.toggle('is-live', status === 'published');
  unpublishBtn.hidden = !(editingId && status === 'published');
  deleteBtn.hidden = !editingId;
}

function resetEditor() {
  editingId = null;
  existingCoverUrl = '';
  existingAuthorPhotoUrl = '';
  existingDocumentUrl = '';
  form.reset();
  editorTitle.textContent = 'New Article';
  document.getElementById('statusField').value = 'draft';
  document.getElementById('slugField').value = '';
  form.dataset.publishedAt = '';
  if (form.publishedAt) form.publishedAt.value = '';
  if (form.sourceCredit) form.sourceCredit.value = '';
  if (form.sourceUrl) form.sourceUrl.value = '';
  if (form.authorTitle) form.authorTitle.value = '';
  if (form.featured) form.featured.checked = false;
  if (form.editorsPick) form.editorsPick.checked = false;
  if (form.isBreaking) form.isBreaking.checked = false;
  fillCategories();
  fillAuthors('');
  previewCover();
  previewAuthor();
  if (documentNote) documentNote.textContent = 'Optional. Attach a PDF from the LouieCorp library.';
  setEditorChrome('draft');
}

function openNewArticle() {
  resetEditor();
  showEditor();
}

async function ensureProfile() {
  const fallbackName = currentUser.user_metadata && currentUser.user_metadata.display_name
    ? currentUser.user_metadata.display_name
    : (currentUser.email || 'Editor').split('@')[0];
  const { data, error } = await client
    .from('profiles')
    .select('*')
    .eq('id', currentUser.id)
    .maybeSingle();
  if (error) throw error;
  if (data) {
    currentProfile = data;
    return data;
  }
  const insert = await client.from('profiles').insert({
    id: currentUser.id,
    display_name: fallbackName,
    role: 'admin'
  }).select('*').single();
  if (insert.error) throw insert.error;
  currentProfile = insert.data;
  return insert.data;
}

async function loadCategories() {
  const { data, error } = await client
    .from('categories')
    .select('id, name, slug')
    .order('name');
  if (error) throw error;
  categories = data || [];
  fillCategories();
}

async function loadAuthors() {
  if (!authorsTableReady) {
    authors = [];
    fillAuthors('');
    return;
  }
  const { data, error } = await client
    .from('authors')
    .select('id, name, slug, bio, photo_url, title')
    .order('name');
  if (error && /title/i.test(String(error.message || ''))) {
    authorTitleReady = false;
    const retry = await client
      .from('authors')
      .select('id, name, slug, bio, photo_url')
      .order('name');
    if (!retry.error) {
      authors = retry.data || [];
      fillAuthors(authorSelect ? authorSelect.value : '');
      return;
    }
  }
  if (error) {
    authorsTableReady = false;
    authors = [];
    fillAuthors('');
    showNotice('Author records are not available yet. Run supabase/schema.sql in Supabase to enable reusable bylines.', 'error');
    return;
  }
  authors = data || [];
  fillAuthors(authorSelect ? authorSelect.value : '');
}

function resizeImageFile(file, maxSize) {
  return new Promise((resolve) => {
    if (!file || !/^image\//.test(file.type) || file.type === 'image/gif') {
      resolve(file);
      return;
    }
    const image = new Image();
    const url = URL.createObjectURL(file);
    image.onload = () => {
      URL.revokeObjectURL(url);
      const scale = Math.min(1, maxSize / Math.max(image.width, image.height));
      if (scale >= 1) {
        resolve(file);
        return;
      }
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(image.width * scale);
      canvas.height = Math.round(image.height * scale);
      const ctx = canvas.getContext('2d');
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => {
        if (!blob) {
          resolve(file);
          return;
        }
        resolve(new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg' }));
      }, 'image/jpeg', 0.82);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(file);
    };
    image.src = url;
  });
}

async function uploadToMedia(folder, file, slug, fallbackType) {
  const key = uniqueMediaKey(folder, slug, file, fallbackType);
  return uploadMediaFile(file, key, fallbackType);
}

async function uploadCover(file, slug) {
  if (!file) return existingCoverUrl;
  return uploadToMedia('covers', file, slug, 'image/jpeg');
}

async function uploadAuthorPhoto(file, slug) {
  if (!file) return existingAuthorPhotoUrl;
  const prepared = await resizeImageFile(file, 640);
  return uploadToMedia('authors', prepared, slug, 'image/jpeg');
}

async function uploadDocument(file, slug) {
  if (!file) return existingDocumentUrl;
  return uploadToMedia('sources', file, slug, 'application/pdf');
}

async function generateAndUploadPdf(article) {
  if (!window.LouieCorpPdf || !window.LouieCorpPdf.generateArticlePdf) return '';
  const file = await window.LouieCorpPdf.generateArticlePdf({
    slug: article.slug,
    title: article.title,
    excerpt: article.excerpt,
      body: article.content,
      cover: article.cover_image_url,
      caption: article.image_caption || article.caption || '',
      author: article.authorName,
    date: formatDate(article.published_at),
    desk: publicDesk ? publicDesk(article.desk) : article.desk,
    source: [article.source_credit, article.source_url].filter(Boolean).join(' — ')
  });
  return uploadToMedia('pdfs', file, `${article.slug}-edition`, 'application/pdf');
}

async function resolveBylineAuthor() {
  if (!authorsTableReady) return null;
  const selected = authorSelect ? authorSelect.value : '';
  const name = (document.getElementById('authorName').value || '').trim();
  const bio = (document.getElementById('authorBio').value || '').trim();
  const photoFile = form.authorPhoto && form.authorPhoto.files[0];
  if (!selected && (!name || name === 'Editorial Desk' || name === 'Sentongo. R. Louis') && !photoFile && !bio) return null;

  if (selected && selected !== '__new') {
    const current = authors.find((item) => item.id === selected) || {};
    const photoUrl = await uploadAuthorPhoto(photoFile, current.slug || slugify(name || current.name));
    const payload = {
      name: name || current.name,
      bio: bio || null,
      photo_url: photoUrl || current.photo_url || null
    };
    if (authorTitleReady) payload.title = (form.authorTitle && form.authorTitle.value.trim()) || null;
    const { data, error } = await client.from('authors').update(payload).eq('id', selected).select('*').single();
    if (error) throw error;
    return data;
  }

  if (!name) return null;
  const slug = slugify(name);
  const existing = await client.from('authors').select('*').eq('slug', slug).maybeSingle();
  if (existing.error) throw existing.error;
  const photoUrl = await uploadAuthorPhoto(photoFile, slug);
  if (existing.data) {
    const updatePayload = {
      name,
      bio: bio || existing.data.bio,
      photo_url: photoUrl || existing.data.photo_url
    };
    if (authorTitleReady) updatePayload.title = (form.authorTitle && form.authorTitle.value.trim()) || existing.data.title || null;
    const { data, error } = await client.from('authors').update(updatePayload).eq('id', existing.data.id).select('*').single();
    if (error) throw error;
    return data;
  }
  const createdPayload = {
    name,
    slug,
    bio: bio || null,
    photo_url: photoUrl || null
  };
  if (authorTitleReady) createdPayload.title = (form.authorTitle && form.authorTitle.value.trim()) || null;
  const created = await client.from('authors').insert(createdPayload).select('*').single();
  if (created.error) throw created.error;
  return created.data;
}

function parseTags(value) {
  const seen = new Set();
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter((item) => {
      const key = item.toLowerCase();
      if (!item || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

async function syncTags(articleId, names) {
  const { error: clearError } = await client
    .from('article_tags')
    .delete()
    .eq('article_id', articleId);
  if (clearError) throw clearError;
  if (!names.length) return;

  const rows = [];
  for (const name of names) {
    const slug = slugify(name);
    const existing = await client.from('tags').select('id').eq('slug', slug).maybeSingle();
    if (existing.error) throw existing.error;
    let tagId = existing.data && existing.data.id;
    if (!tagId) {
      const created = await client.from('tags').insert({ name, slug }).select('id').single();
      if (created.error) {
        const retry = await client.from('tags').select('id').eq('slug', slug).maybeSingle();
        if (retry.error || !retry.data) throw created.error;
        tagId = retry.data.id;
      } else {
        tagId = created.data.id;
      }
    }
    rows.push({ article_id: articleId, tag_id: tagId });
  }
  if (rows.length) {
    const { error } = await client.from('article_tags').insert(rows);
    if (error) throw error;
  }
}

function filteredArticles() {
  const filter = libraryFilter.value;
  return articlesCache.filter((item) => filter === 'all' || item.status === filter);
}

function actionButtons(item) {
  const publishLabel = item.status === 'published' ? 'Unpublish' : 'Publish';
  const publishAction = item.status === 'published' ? 'unpublish' : 'publish';
  return `
    <div class="row-actions">
      <button type="button" data-action="edit" data-id="${item.id}">Edit</button>
      <button type="button" data-action="${publishAction}" data-id="${item.id}">${publishLabel}</button>
      <button type="button" class="danger" data-action="delete" data-id="${item.id}">Delete</button>
    </div>
  `;
}

function renderTable() {
  const rows = filteredArticles();
  if (!rows.length) {
    const message = articlesCache.length ? 'No stories in this filter.' : 'No stories yet. Use New Article to write the first one.';
    tableBody.innerHTML = `<tr><td colspan="6" class="list-empty">${message}</td></tr>`;
    cardList.innerHTML = `<p class="list-empty">${message}</p>`;
    return;
  }
  tableBody.innerHTML = rows.map((item) => {
    const desk = item.categories ? item.categories.name : 'Unassigned';
    const byline = (item.authors && item.authors.name) || 'Sentongo. R. Louis';
    const dateLabel = item.published_at ? formatDate(item.published_at) : formatDate(item.updated_at) || 'Not published';
    return `
      <tr data-id="${item.id}">
        <td>
          <strong>${escapeHtml(item.title)}</strong>
        </td>
        <td>${escapeHtml(desk)}</td>
        <td>${escapeHtml(byline)}</td>
        <td><span class="status-pill ${item.status}">${escapeHtml(item.status)}</span></td>
        <td>${escapeHtml(dateLabel)}</td>
        <td>${actionButtons(item)}</td>
      </tr>
    `;
  }).join('');
  cardList.innerHTML = rows.map((item) => {
    const desk = item.categories ? item.categories.name : 'Unassigned';
    const byline = (item.authors && item.authors.name) || 'Sentongo. R. Louis';
    const dateLabel = item.published_at ? formatDate(item.published_at) : formatDate(item.updated_at) || 'Not published';
    return `
      <article class="story-mobile-card" data-id="${item.id}">
        <p class="story-tag">${escapeHtml(desk)}</p>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(byline)}</p>
        <p><span class="status-pill ${item.status}">${escapeHtml(item.status)}</span> ${escapeHtml(dateLabel)}</p>
        ${actionButtons(item)}
      </article>
    `;
  }).join('');
}

async function loadArticles() {
  tableBody.innerHTML = '<tr><td colspan="6" class="list-empty">Loading stories...</td></tr>';
  cardList.innerHTML = '<p class="list-empty">Loading stories...</p>';
  let query = client
    .from('articles')
     .select('id, title, status, published_at, updated_at, cover_image_url, byline_author_id, view_count, featured, editors_pick, is_breaking, categories(name), authors:byline_author_id(name)')
    .eq('author_id', currentUser.id)
    .order('updated_at', { ascending: false });
  let { data, error } = await query;
  if (error && /view_count|featured|editors_pick|is_breaking/i.test(String(error.message || ''))) {
    extraFlagsReady = false;
    const retryFlags = await client
      .from('articles')
      .select('id, title, status, published_at, updated_at, cover_image_url, byline_author_id, categories(name), authors:byline_author_id(name)')
      .eq('author_id', currentUser.id)
      .order('updated_at', { ascending: false });
    data = retryFlags.data;
    error = retryFlags.error;
  }
  if (error && /authors|byline_author/i.test(String(error.message || ''))) {
    authorsTableReady = false;
    const retry = await client
      .from('articles')
      .select('id, title, status, published_at, updated_at, cover_image_url, categories(name)')
      .eq('author_id', currentUser.id)
      .order('updated_at', { ascending: false });
    data = retry.data;
    error = retry.error;
  }
  if (error) throw error;
  articlesCache = data || [];
  renderStats();
  renderTable();
}

function renderStats() {
  const root = document.getElementById('newsroomStats');
  if (!root) return;
  const published = articlesCache.filter((item) => item.status === 'published');
  const drafts = articlesCache.filter((item) => item.status !== 'published');
  const views = published.reduce((sum, item) => sum + Number(item.view_count || 0), 0);
  const mostRead = published
    .filter((item) => Number(item.view_count) > 0)
    .sort((a, b) => Number(b.view_count || 0) - Number(a.view_count || 0))
    .slice(0, 3);
  const desks = {};
  published.forEach((item) => {
    const desk = item.categories ? item.categories.name : 'Unassigned';
    desks[desk] = (desks[desk] || 0) + 1;
  });
  const authors = {};
  published.forEach((item) => {
    const name = (item.authors && item.authors.name) || 'Sentongo. R. Louis';
    authors[name] = (authors[name] || 0) + 1;
  });
  const deskLine = Object.keys(desks).sort((a, b) => desks[b] - desks[a]).slice(0, 4)
    .map((name) => `${name} ${desks[name]}`).join(' · ') || 'None yet';
  const authorLine = Object.keys(authors).sort((a, b) => authors[b] - authors[a]).slice(0, 4)
    .map((name) => `${name} ${authors[name]}`).join(' · ') || 'None yet';
  root.hidden = false;
  root.innerHTML = `
    <article><p class="kicker">Published</p><p class="stat-value">${published.length}</p></article>
    <article><p class="kicker">Drafts</p><p class="stat-value">${drafts.length}</p></article>
    <article><p class="kicker">Views</p><p class="stat-value">${views || '—'}</p><p class="stat-note">${views ? 'From recorded article opens' : 'No view data yet'}</p></article>
    <article><p class="kicker">Most-read</p><p class="stat-note">${mostRead.length ? mostRead.map((item) => `${escapeHtml(item.title)} (${item.view_count})`).join(' · ') : 'No view data yet'}</p></article>
    <article><p class="kicker">Desks</p><p class="stat-note">${escapeHtml(deskLine)}</p></article>
    <article><p class="kicker">Authors</p><p class="stat-note">${escapeHtml(authorLine)}</p></article>
  `;
}

async function editArticle(id) {
  showNotice('Loading story...');
  const { data, error } = await client
    .from('articles')
    .select('*, article_tags(tags(name))')
    .eq('id', id)
    .single();
  if (error) throw error;
  editingId = data.id;
  existingCoverUrl = data.cover_image_url || '';
  existingDocumentUrl = data.document_url || '';
  editorTitle.textContent = 'Edit article';
  form.title.value = data.title;
  form.excerpt.value = data.excerpt || '';
  form.body.value = data.content || '';
  form.status.value = data.status === 'archived' ? 'draft' : data.status;
  fillAuthors(data.byline_author_id || '');
  if (documentNote) {
    documentNote.textContent = existingDocumentUrl
      ? 'A source document is attached. Upload a new PDF to replace it.'
      : 'Optional. Attach a PDF from the LouieCorp library.';
  }
  document.getElementById('slugField').value = data.slug || '';
  form.dataset.publishedAt = data.published_at || '';
  if (form.publishedAt) form.publishedAt.value = toDatetimeLocal(data.published_at);
  if (form.sourceCredit) form.sourceCredit.value = data.source_credit || '';
  if (form.sourceUrl) form.sourceUrl.value = data.source_url || '';
  if (form.featured) form.featured.checked = Boolean(data.featured);
  if (form.editorsPick) form.editorsPick.checked = Boolean(data.editors_pick);
  if (form.isBreaking) form.isBreaking.checked = Boolean(data.is_breaking);
  const tagNames = (data.article_tags || [])
    .map((row) => row.tags && row.tags.name)
    .filter(Boolean);
  form.tags.value = tagNames.join(', ');
  fillCategories(data.category_id);
  previewCover(null, data.cover_image_url);
  setEditorChrome(form.status.value);
  showEditor();
  showNotice('Story loaded.');
}

async function saveArticle(status) {
  if (busy) return;
  if (!currentProfile) await ensureProfile();
  const title = form.title.value.trim();
  const slugField = document.getElementById('slugField');
  const slug = slugField.value || slugify(title);
  const file = form.cover.files[0];
  const documentFile = form.document && form.document.files[0];
  setBusy(true);
  showNotice(status === 'published' ? 'Publishing...' : 'Saving draft...');
  try {
    const coverUrl = await uploadCover(file, slug);
    if (status === 'published' && !coverUrl) {
      throw new Error('Attach a cover image before publishing.');
    }
    let bylineAuthor = null;
    try {
      bylineAuthor = await resolveBylineAuthor();
    } catch (error) {
      authorsTableReady = false;
      bylineAuthor = null;
    }
    let documentUrl = existingDocumentUrl;
    if (documentFile) {
      try {
        documentUrl = await uploadDocument(documentFile, slug);
      } catch (error) {
        throw new Error('Could not upload the PDF. Sign in again and retry.');
      }
    }
    const payload = {
      slug,
      title,
      excerpt: form.excerpt.value.trim(),
      content: form.body.value.trim(),
      category_id: categorySelect.value || null,
      author_id: currentUser.id,
      status,
      cover_image_url: coverUrl || null
    };
    if (authorsTableReady) payload.byline_author_id = bylineAuthor ? bylineAuthor.id : null;
    if (documentColumnReady && documentUrl) payload.document_url = documentUrl;
    if (extraFlagsReady) {
      payload.featured = Boolean(form.featured && form.featured.checked);
      payload.editors_pick = Boolean(form.editorsPick && form.editorsPick.checked);
      payload.is_breaking = Boolean(form.isBreaking && form.isBreaking.checked);
    }
    if (sourceColumnsReady) {
      const credit = form.sourceCredit ? form.sourceCredit.value.trim() : '';
      const sourceUrl = form.sourceUrl ? form.sourceUrl.value.trim() : '';
      payload.source_credit = credit || null;
      payload.source_url = sourceUrl || null;
    }
    if (status === 'published') {
      payload.published_at = fromDatetimeLocal(form.publishedAt && form.publishedAt.value)
        || form.dataset.publishedAt
        || new Date().toISOString();
    } else {
      payload.published_at = null;
    }
    let result;
    if (editingId) {
      result = await client.from('articles').update(payload).eq('id', editingId).select('id').single();
    } else {
      result = await client.from('articles').insert(payload).select('id').single();
      if (result.error && String(result.error.message || '').toLowerCase().includes('duplicate')) {
        payload.slug = `${slug}-${Date.now().toString().slice(-4)}`;
        result = await client.from('articles').insert(payload).select('id').single();
      }
    }
    if (result.error) {
      if (/byline_author/i.test(String(result.error.message || ''))) {
        authorsTableReady = false;
        delete payload.byline_author_id;
        result = editingId
          ? await client.from('articles').update(payload).eq('id', editingId).select('id').single()
          : await client.from('articles').insert(payload).select('id').single();
      }
      if (result.error && /document_url/i.test(String(result.error.message || ''))) {
        documentColumnReady = false;
        delete payload.document_url;
        result = editingId
          ? await client.from('articles').update(payload).eq('id', editingId).select('id').single()
          : await client.from('articles').insert(payload).select('id').single();
      }
      if (result.error && /source_credit|source_url/i.test(String(result.error.message || ''))) {
        sourceColumnsReady = false;
        delete payload.source_credit;
        delete payload.source_url;
        result = editingId
          ? await client.from('articles').update(payload).eq('id', editingId).select('id').single()
          : await client.from('articles').insert(payload).select('id').single();
      }
      if (result.error && /featured|editors_pick|is_breaking/i.test(String(result.error.message || ''))) {
        extraFlagsReady = false;
        delete payload.featured;
        delete payload.editors_pick;
        delete payload.is_breaking;
        result = editingId
          ? await client.from('articles').update(payload).eq('id', editingId).select('id').single()
          : await client.from('articles').insert(payload).select('id').single();
      }
    }
    if (result.error) throw result.error;
    editingId = result.data.id;
    await syncTags(editingId, parseTags(form.tags.value));
    existingCoverUrl = coverUrl;
    existingDocumentUrl = documentUrl || existingDocumentUrl;
    if (status === 'published') {
      try {
        showNotice('Generating newspaper PDF...');
        const pdfUrl = await generateAndUploadPdf({
          slug: payload.slug,
          title,
          excerpt: payload.excerpt,
          content: payload.content,
          cover_image_url: coverUrl,
          source_credit: payload.source_credit,
          source_url: payload.source_url,
          published_at: payload.published_at,
          desk: (categories.find((item) => item.id === payload.category_id) || {}).name,
          authorName: bylineAuthor ? bylineAuthor.name : 'Sentongo. R. Louis'
        });
        if (pdfUrl) {
          const pdfUpdate = await client.from('articles').update({ pdf_url: pdfUrl }).eq('id', editingId);
          if (pdfUpdate.error && /pdf_url/i.test(String(pdfUpdate.error.message || ''))) {
            await client.from('articles').update({ document_url: pdfUrl }).eq('id', editingId);
            existingDocumentUrl = pdfUrl;
          }
        }
      } catch (error) {
        showNotice('Story published. PDF generation can be retried from the editor.', 'error');
      }
    }
    if (bylineAuthor) {
      const idx = authors.findIndex((item) => item.id === bylineAuthor.id);
      if (idx >= 0) authors[idx] = bylineAuthor;
      else authors.push(bylineAuthor);
      fillAuthors(bylineAuthor.id);
    }
    form.cover.value = '';
    if (form.authorPhoto) form.authorPhoto.value = '';
    if (form.document) form.document.value = '';
    form.status.value = status;
    slugField.value = payload.slug;
    form.dataset.publishedAt = payload.published_at || '';
    if (form.publishedAt) form.publishedAt.value = toDatetimeLocal(payload.published_at);
    editorTitle.textContent = 'Edit article';
    setEditorChrome(status);
    showNotice(status === 'published' ? 'Story published with cover image.' : 'Draft saved. It will not appear on the public site.');
    await loadArticles();
    showLibrary();
  } finally {
    setBusy(false);
  }
}

async function setArticleStatus(id, status) {
  setBusy(true);
  showNotice(status === 'published' ? 'Publishing...' : 'Unpublishing...');
  try {
    const payload = {
      status,
      published_at: status === 'published' ? new Date().toISOString() : null
    };
    let story = null;
    if (status === 'published') {
      let loaded = await client
        .from('articles')
        .select('cover_image_url, published_at, slug, title, excerpt, content, source_credit, source_url, category_id, byline_author_id, categories(name), authors:byline_author_id(name)')
        .eq('id', id)
        .single();
      if (loaded.error && /authors|byline_author/i.test(String(loaded.error.message || ''))) {
        loaded = await client
          .from('articles')
          .select('cover_image_url, published_at, slug, title, excerpt, content, source_credit, source_url, category_id, categories(name)')
          .eq('id', id)
          .single();
      }
      if (loaded.error) throw loaded.error;
      if (!loaded.data.cover_image_url) throw new Error('Attach a cover image before publishing.');
      if (loaded.data.published_at) payload.published_at = loaded.data.published_at;
      story = loaded.data;
    }
    const { error } = await client.from('articles').update(payload).eq('id', id);
    if (error) throw error;
    if (status === 'published' && story) {
      try {
        showNotice('Generating newspaper PDF...');
        const pdfUrl = await generateAndUploadPdf({
          slug: story.slug,
          title: story.title,
          excerpt: story.excerpt,
          content: story.content,
          cover_image_url: story.cover_image_url,
          source_credit: story.source_credit,
          source_url: story.source_url,
          published_at: payload.published_at,
          desk: story.categories && story.categories.name,
          authorName: (story.authors && story.authors.name) || 'Sentongo. R. Louis'
        });
        if (pdfUrl) {
          const pdfUpdate = await client.from('articles').update({ pdf_url: pdfUrl }).eq('id', id);
          if (pdfUpdate.error && /pdf_url/i.test(String(pdfUpdate.error.message || ''))) {
            await client.from('articles').update({ document_url: pdfUrl }).eq('id', id);
          }
        }
      } catch (pdfError) {
        showNotice('Story published. PDF generation can be retried from the editor.', 'error');
      }
    }
    if (editingId === id) {
      form.status.value = status;
      form.dataset.publishedAt = payload.published_at || '';
      if (form.publishedAt) form.publishedAt.value = toDatetimeLocal(payload.published_at);
      setEditorChrome(status);
    }
    showNotice(status === 'published' ? 'Story published.' : 'Story unpublished. It is no longer public.');
    await loadArticles();
  } finally {
    setBusy(false);
  }
}

async function unpublishArticle() {
  if (!editingId) return;
  await setArticleStatus(editingId, 'draft');
}

async function deleteArticleById(id) {
  const confirmed = window.confirm('Delete this story permanently? This cannot be undone.');
  if (!confirmed) return;
  setBusy(true);
  showNotice('Deleting...');
  try {
    const { error } = await client.from('articles').delete().eq('id', id);
    if (error) throw error;
    showNotice('Story deleted.');
    if (editingId === id) resetEditor();
    await loadArticles();
    showLibrary();
  } finally {
    setBusy(false);
  }
}

async function deleteArticle() {
  if (!editingId) return;
  await deleteArticleById(editingId);
}

async function handleLibraryAction(event) {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const { action, id } = button.dataset;
  try {
    if (action === 'edit') await editArticle(id);
    if (action === 'publish') await setArticleStatus(id, 'published');
    if (action === 'unpublish') await setArticleStatus(id, 'draft');
    if (action === 'delete') await deleteArticleById(id);
  } catch (error) {
    showNotice(error.message, 'error');
  }
}

async function refreshSession() {
  if (!applySavedConfig()) return;
  try {
    client = getClient();
  } catch (error) {
    showNotice(error.message, 'error');
    showPanel('auth');
    return;
  }
  let session = null;
  try {
    const { data } = await client.auth.getSession();
    session = data && data.session;
  } catch (error) {
    showNotice(error.message, 'error');
    showPanel('auth');
    return;
  }
  currentUser = session ? session.user : null;
  if (!currentUser) {
    showPanel('auth');
    return;
  }
  await ensureProfile();
  await loadCategories();
  await loadAuthors();
  showPanel('dashboard');
  resetEditor();
  showLibrary();
  try {
    await loadArticles();
  } catch (error) {
    tableBody.innerHTML = `<tr><td colspan="6" class="list-empty">Could not load stories. ${escapeHtml(error.message)}</td></tr>`;
    cardList.innerHTML = `<p class="list-empty">Could not load stories. ${escapeHtml(error.message)}</p>`;
    showNotice(error.message, 'error');
  }
}

document.getElementById('setupForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    saveStoredConfig(
      document.getElementById('supabaseUrl').value,
      document.getElementById('supabaseKey').value
    );
    showNotice('Project connected. Sign in with your admin account.');
    await refreshSession();
  } catch (error) {
    showNotice(error.message, 'error');
  }
});

document.getElementById('loginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    client = getClient();
    const email = document.getElementById('adminEmail').value.trim();
    const password = document.getElementById('adminPassword').value;
    const { error } = await client.auth.signInWithPassword({ email, password });
    if (error) throw error;
    showNotice('Signed in.');
    await refreshSession();
  } catch (error) {
    showNotice(error.message, 'error');
  }
});

signOutBtn.addEventListener('click', async () => {
  if (client) await client.auth.signOut();
  currentUser = null;
  currentProfile = null;
  resetEditor();
  showPanel('auth');
});

changeSetupBtn.addEventListener('click', () => {
  showSetupFallback();
});

newStoryBtn.addEventListener('click', openNewArticle);
backToLibraryBtn.addEventListener('click', () => {
  showLibrary();
});
libraryFilter.addEventListener('change', renderTable);
unpublishBtn.addEventListener('click', () => unpublishArticle().catch((error) => showNotice(error.message, 'error')));
deleteBtn.addEventListener('click', () => deleteArticle().catch((error) => showNotice(error.message, 'error')));

form.cover.addEventListener('change', () => {
  const file = form.cover.files[0];
  previewCover(file, existingCoverUrl);
});
if (form.authorPhoto) {
  form.authorPhoto.addEventListener('change', () => {
    previewAuthor(form.authorPhoto.files[0], existingAuthorPhotoUrl);
  });
}
if (authorSelect) {
  authorSelect.addEventListener('change', applyAuthorSelection);
}

tableBody.addEventListener('click', handleLibraryAction);
cardList.addEventListener('click', handleLibraryAction);

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const status = event.submitter && event.submitter.dataset.status
    ? event.submitter.dataset.status
    : form.status.value;
  try {
    await saveArticle(status);
  } catch (error) {
    showNotice(error.message, 'error');
  }
});

applySavedConfig();
refreshSession().catch((error) => {
  if (isConfigured()) {
    showPanel(currentUser ? 'dashboard' : 'auth');
  } else {
    showSetupFallback();
  }
  showNotice(error.message, 'error');
});
