# LouieCorp

Premium editorial publication frontend for louiecorp.com.

Included: a newspaper-style homepage, article pages, section desks, archive search, and an admin dashboard that publishes articles with cover images through the existing Supabase schema.

## Publishing workflow

1. Keep the tables already created: `categories`, `profiles`, `articles`, `tags`, `article_tags`.
2. In the SQL editor, run `supabase/schema.sql` once if drafts, tags, authors or storage buckets still need policies. The script is additive and does not delete existing stories.
3. Put the project URL and anon public key in `js/config.js`, or paste them in `admin/index.html`.
4. Sign in, write the story, choose or create an author, add tags, attach a cover, then save, publish, unpublish or delete.
5. Published pieces appear automatically on the front page. Drafts never appear on the public site.

The admin writes to the existing columns: `content`, `cover_image_url`, `category_id`, `author_id`, plus reusable `authors` records via `byline_author_id`. Existing stories without a byline author display as Editorial Desk.

Never put the Supabase service-role key in browser JavaScript. Use the public/anon key with Row Level Security.

Article URLs now use clean Surge routes: `/story/<slug>`. Surge serves `200.html` at unmatched routes, and the article shell reads the slug from the path. Legacy `/s/<slug>` redirects are retained where router rules are available.
