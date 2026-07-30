# Telegram → AI Product Automation

Send a product to your Telegram bot. It arrives in the admin panel fully
prepared. You pick a **Category** and **Sub Category**, click **Approve**, and
it goes live.

Nothing is published automatically.

---

## 1. Setup

### Rotate the bot token first

If a token has ever been pasted into a chat, an email, or a commit, treat it as
compromised: message **@BotFather** → `/revoke` → pick the bot → copy the new
token. Anyone holding a bot token has full control of that bot.

### Install the dependency

```bash
pip install -r requirements.txt      # adds: anthropic
```

### Configure `.env`

```ini
TELEGRAM_BOT_TOKEN=123456789:AA...            # from @BotFather
TELEGRAM_ALLOWED_CHAT_IDS=-1001234567890      # optional, recommended
ANTHROPIC_API_KEY=sk-ant-...                  # optional but strongly advised
AUTOMATION_AI_MODEL=claude-opus-5
AUTOMATION_AI_EFFORT=medium
```

`.env` is already in `.gitignore`. Never hardcode the token in source.

**Finding your chat ID:** leave `TELEGRAM_ALLOWED_CHAT_IDS` empty, send one
message to the bot, open `/admin-panel/product-drafts/`, and read the draft's
`source_chat_id` in the Django admin. Then set the value and restart.

**If the bot reads a channel** rather than direct messages, add it to the
channel as an administrator — otherwise Telegram will not deliver posts to it.

### Migrate

```bash
python manage.py migrate
```

---

## 2. Running

Two long-running processes sit alongside the web server:

```bash
python manage.py telegram_product_bot        # message intake
python manage.py process_product_drafts      # AI + image pipeline
```

They are deliberately separate: a slow model call can never stall message
intake, and either can be restarted without losing work.

Both also support one-shot mode if you would rather drive them from Windows
Task Scheduler or cron than keep them resident:

```bash
python manage.py telegram_product_bot --once
python manage.py process_product_drafts --once
```

This project already has `startup_manager.py` and `watchdog.py` supervising
long-running processes — these two commands fit that pattern.

---

## 3. What happens to a message

```
Telegram post
   │  telegram_product_bot
   ▼
ProductDraft (RECEIVED)          album parts merge into one draft
   │  process_product_drafts
   ▼
rule-based parse   →  prices, sizes, fabrics, SKU  (deterministic)
image analysis     →  main / gallery / description, colour, alt text
AI extraction      →  name, description, highlights, attributes, SEO, category
image pipeline     →  de-duplicate, compress, SEO-rename
duplicate check    →  SKU / image hash / name / price / description
   ▼
PENDING  (or DUPLICATE)
   │  you pick Category + Sub Category, click Approve
   ▼
Product + ProductImage + ProductVariant + ProductSEO      ← one transaction
```

If any step of publishing fails, the whole transaction rolls back and the draft
stays pending. No half-built products.

---

## 4. Where the data lands

The automation writes into your **existing** models — nothing was replaced.

| Extracted | Stored in |
|---|---|
| Name, price, MRP, discount, stock, SKU, brand, weight, dimensions | `Product` |
| Description + highlights + specification block | `Product.description` (safe HTML) |
| Fabric, material, wash care, package contents | `Product.care_info` |
| Sizes / colours (display strings) | `Product.size` / `Product.color` |
| Tags, search terms | `Product.tags` |
| Main / gallery / description images, per colour | `ProductImage` (`image_role`, `color`) |
| Colour and size variants | `ProductVariant` |
| Meta title, description, keywords, OG, Twitter | `ProductSEO` |
| Everything else (sleeve type, occasion, fit, work type…) | `ProductDraft.parsed`, shown on the review screen |

### A note on the extended attributes

Your `Product` model has no columns for `sleeve_type`, `neck_type`, `occasion`,
`fit`, `work_type`, `stitch_type` and similar. Rather than migrate ~15 new
columns onto your core table — which no existing template renders — those are
extracted, kept verbatim on the draft, displayed during review, and folded into
the fields that do exist (specification block, `care_info`, `tags`).

If you later want them as first-class columns, the extraction already produces
them; only `publisher.py` needs to change.

---

## 4b. Supplier code strips

Wholesale suppliers (Meesho and similar) print a catalogue code on a plain band
below the product photo — `s-558186268` in the bottom-left corner.

The pipeline detects that band automatically and pre-fills a crop. On the
review screen each image shows a **Crop … px** box, and the preview above it is
clipped live so you see exactly what will be published.

* **Re-apply** / **Keep full images** set every image at once.
* Type any pixel value to fine-tune, or `0` to keep the full photo.
* **Save Crop Only** persists without publishing, so you can iterate.

The crop is stored as *intent*, not baked into the staged file, so it stays
adjustable right up until you approve. The publisher applies it when copying
images onto the live product; the original staged file is never destroyed.

Detection is skipped for images classified as `description` (size charts and
fabric cards are legitimately text on a plain background), and a crop that
would remove more than 60% of an image's height is refused.

---

## 5. Running without an Anthropic key

The pipeline still works. It falls back to the rule-based extractor, which
reliably handles prices (`₹799`, `1299/-`, `MRP Rs. 2,499`), sizes
(`M L XL`, `M-38`, `Free Size`), fabric blocks (`Top / Bottom / Dupatta`), SKU,
stock and colours.

What you lose: generated descriptions, SEO copy, category suggestions, and
image role/colour classification (images fall back to "first one is the hero").
Drafts are marked with a warning so you know which path ran.

---

## 6. Reliability

* **Idempotent intake** — `(source, source_message_id)` is unique, so a
  redelivered Telegram update cannot create a second product.
* **Album grouping** — a six-photo post is one draft, not six. The worker waits
  `AUTOMATION_ALBUM_SETTLE_SECONDS` (default 10) after the last part arrives.
* **Retries** — 1m → 5m → 15m → 60m, then `FAILED`. Configurable via
  `AUTOMATION_MAX_ATTEMPTS`.
* **Crash recovery** — a draft claimed by a worker that dies is reclaimed after
  30 minutes.
* **Audit trail** — every stage appends to `ProductDraft.events`, shown at the
  bottom of the review screen.

### Why no Celery

This project runs on SQLite with no broker installed. The draft table *is* the
queue — `status` + `next_attempt_at` + `attempts` give at-least-once delivery,
backoff and crash recovery with no new infrastructure to deploy or supervise on
a Windows host.

`pipeline.process_draft(draft)` is a plain function. If throughput outgrows
this, point a Celery task at it and nothing else changes.

---

## 7. Adding another source later

`Hub/automation/sources/base.py` defines the contract. A new channel is one
subclass plus a management command:

```python
class WhatsAppSource(ProductSource):
    name = ProductDraft.SOURCE_WHATSAPP

    def poll(self):
        for message in self.fetch_new_messages():
            yield IncomingProduct(
                source=self.name,
                message_id=message['id'],
                text=message['body'],
                media=[IncomingMedia(data=..., filename=...)],
                group_id=message.get('album_id', ''),
            )
```

Parsing, AI, images, duplicate detection, approval and publishing are all
shared — `ProductDraft.SOURCE_CHOICES` already has entries for WhatsApp, CSV,
Excel and supplier APIs.

---

## 8. Files

```
Hub/models_product_automation.py        ProductDraft, ProductDraftImage
Hub/automation/
  ingest.py                             message -> draft (idempotent, album-aware)
  pipeline.py                           queue claiming, retries, orchestration
  images.py                             dHash, de-duplication, compression, SEO names
  duplicates.py                         weighted multi-signal duplicate scoring
  publisher.py                          draft -> live catalogue (atomic)
  sources/base.py                       ProductSource contract
  sources/telegram_bot.py               Bot API long-polling
  parsing/rules.py                      deterministic price/size/fabric extraction
  ai/client.py                          Anthropic wrapper, retries, JSON schema
  ai/schema.py                          output contract
  ai/prompts.py                         system prompts
  ai/extraction.py                      rules + AI merge
  ai/vision.py                          image role / colour / alt text
Hub/views_product_automation.py         approval screens
Hub/templates/admin_panel/
  product_drafts.html                   queue
  review_product_draft.html             review + approve
Hub/management/commands/
  telegram_product_bot.py
  process_product_drafts.py
```
