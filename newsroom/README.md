# LouieCorp automated newsroom

This is a server-side newsroom runner. It is intentionally separate from the public JavaScript.

## Editorial model

- Maximum of **3 automated publications per UTC day**.
- Each UTC day must include **at least one automated Uganda story**. This is a hard requirement. If that story has not yet succeeded, the runner selects Uganda news before any other track.
- After the Uganda requirement is met, the next unused slot prefers a **Knowledge & Society** piece whenever a suitable topic can be researched.
- Remaining automated slots are current-affairs news.
- Three is a ceiling, not a quota. The runner skips a slot when it cannot meet the research, verification, originality, importance, or real-image requirements.
- Manual publishing from `/admin` is independent and is **not counted** against the automated ceiling.
- Automated covers must come from an approved real-photo source. AI image generation is not used.
- When `AUTO_PUBLISH=true`, a successful publication also generates the newspaper PDF, uploads it to R2 through `/bot-media/pdfs/`, and stores `pdf_url`. PDF failure does not roll back the article.
- The initial workflow creates **drafts only**. `AUTO_PUBLISH=true` can be enabled later after real-world testing.

## Required GitHub Actions secrets

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `NEWSROOM_EDITOR_USER_ID` (the existing Supabase Auth user ID used as the article editor identity)
- `GEMINI_API_KEY`
- `MEDIA_WORKER_URL`
- `MEDIA_BOT_SECRET`
- `UNSPLASH_ACCESS_KEY` (optional; Wikimedia Commons is tried first)

Never put any of these secrets in browser JavaScript or commit them to Git.

## Supabase setup

Run `supabase/migrations/20261008_newsroom.sql` once. It adds the newsroom audit tables and article provenance fields without deleting existing article data.

## Cloudflare setup

Set the production Worker secret once, using the exact same value as the GitHub Actions secret `MEDIA_BOT_SECRET`:

```
npx wrangler secret put MEDIA_BOT_SECRET --name louiecorp
```

Then redeploy the Worker from `worker/`:

```
npx wrangler deploy
```

A missing Worker secret now fails closed with HTTP 500 (`MEDIA_BOT_SECRET is not configured on the Worker.`). A present but mismatched secret still returns HTTP 401 (`Bot authentication failed.`). Never put the value in `wrangler.toml` or browser JavaScript.

## First test

Use GitHub Actions > LouieCorp Newsroom > Run workflow. The first successful run of a UTC day should satisfy the Uganda requirement and create a draft. Inspect the draft in `/admin` before enabling automatic publication. The Worker must be redeployed so `/bot-media/pdfs/` accepts bot PDF uploads.
