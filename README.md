# Boden GameFest 2027 – Intresseformulär

A small web app for the Boden GameFest 2027 interest survey (6–9 maj, Boden).

## What's here

| File / dir            | Purpose |
|-----------------------|---------|
| `index.html`          | Public landing page + survey form (Tailwind, self-contained). Served at `/`; its form posts to `/submit` |
| `app.py`              | Flask backend: serves `index.html`, stores submissions in SQLite, admin dashboard, CSV export |
| `survey.db`           | SQLite database with all submitted responses (auto-created) |
| `templates/`          | Jinja templates: `thanks.html`, `admin.html` (`survey.html` is a legacy form, no longer served) |
| `static/style.css`    | Shared styling (purple BG27 theme, same look as the printed form) |
| `generate_pdf.py`     | Generates the printable A4 PDF version of the survey |
| `output/`             | Generated HTML + PDF of the printed form |
| `Dockerfile`          | Container image for the web app (Flask only) |
| `docker-compose.yml`  | One-command run with a persistent `./data` volume |
| `requirements.txt`    | Python dependencies (`flask`) |
| `.env`                | Admin password + Flask secret (git-ignored, auto-loaded by Compose) |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install flask weasyprint
```

(Already done in this repo — `.venv` exists.)

## Run

```bash
.venv/bin/python app.py
```

- Survey form:   http://127.0.0.1:5000/
- Admin page:    http://127.0.0.1:5000/admin
- CSV export:    http://127.0.0.1:5000/admin/export.csv

Set `PORT` to change the port, `HOST` to change the bind address
(default `127.0.0.1`; Docker sets it to `0.0.0.0`), `BGF_DB` to use a
different database file.

## Run with Docker

```bash
docker compose up --build -d
```

- Survey form:   http://127.0.0.1:3011/
- Admin page:    http://127.0.0.1:3011/admin
- CSV export:    http://127.0.0.1:3011/admin/export.csv

Create a `.env` file next to `docker-compose.yml` first (Compose loads it
automatically):

```dotenv
BGF_ADMIN_PASSWORD=<password for /admin>
BGF_SECRET=<any long random string>
```

The SQLite database lives in `./data/survey.db` on the host (mounted at
`/data`), so responses survive container rebuilds and removals. The existing
`survey.db` was copied into `data/` once — if you ever need to re-import,
`cp survey.db data/survey.db`.

Without compose:

```bash
docker build -t bgf-site .
docker run --rm -p 3011:5000 -v "$PWD/data:/data" bgf-site
```

Stop with `docker compose down`. Note: the image only installs Flask —
`generate_pdf.py` (WeasyPrint) is meant to be run on the host, not in the
container.

## Generate the printable PDF

```bash
.venv/bin/python generate_pdf.py
# -> output/Boden_GameFest_Formular.pdf
```

## How the form connects to the backend

The landing page is the standalone `index.html`. Its survey form posts to
`POST /submit` (via a small `fetch()` in the page; with JavaScript disabled it
falls back to a normal form submit and lands on the `/tack/<id>` page).

The form uses short machine codes for its option values (e.g. `age=under_15`,
`reasons=lan_vanner`, `travel_distance=norrbotten`). `app.py` maps each code to
the human-readable label that is stored in SQLite, shown on the admin dashboard,
and exported as CSV (see the `*_MAP` tables in `app.py`). Free-text fields are
stored as typed. Multi-select checkboxes (`reasons`, `interests`) are joined into
a single comma-separated column. Because the stored values match the option lists
used by the admin charts, existing rows and new submissions aggregate together.

## Database schema (`survey.db`, table `responses`)

| Column             | Question |
|--------------------|----------|
| `id`, `created_at` | auto / UTC timestamp |
| `age_group`        | 1. Ålder/intervall |
| `location`         | 2. Ort (var bor du?) |
| `want_lan`         | 3. Delta på LAN? (Ja/Nej/Kanske) |
| `regular_visitor`  | 4. Vanlig besökare? (Ja/Nej/Kanske) |
| `motivation`       | Viktig fråga – vad får dig att åka? (multi, comma-separated) |
| `motivation_other` | "Annat" free text from the question above |
| `games_played`     | 5. Vilka spel spelar du? |
| `tournaments_want` | 6. Vilka turneringar vill du se? |
| `interests`        | 7. Övrigt intresse (multi, comma-separated) |
| `travel_distance`  | 8. Hur långt skulle du kunna resa? |
| `lan_price`        | 9. Rimligt pris för LAN-pass? |
| `volunteer`        | 10. Funktionär? (Ja/Nej/Kanske, berätta mer) |
| `email`            | 11. E-post (frivilligt) |

Table `visitors` — anonymous unique-visitor counter:

| Column       | Meaning |
|--------------|---------|
| `visitor_id` | random UUID from the `bgf_visitor` cookie (no personal data) |
| `first_seen` | first time this visitor opened the survey page (UTC) |
| `last_seen`  | most recent visit (UTC) |

A new row is created on the first visit to `/`; repeat visits only update
`last_seen`. The admin page shows total unique visitors and today's count.

## Admin page

- KPI cards: totalt inskick, antal med e-post, andel som vill vara funktionär
- Bar charts per question (single- and multi-choice)
- Full table of every response
- "Exportera CSV" button downloads all responses as `bgf2027_responses.csv`

## Admin authentication

When `BGF_ADMIN_PASSWORD` is set, every `/admin` route (dashboard **and**
CSV export) requires HTTP Basic auth — checked server-side before anything
is rendered. The browser pops a native username/password dialog; any
username works, only the password matters:

```bash
curl -u admin:'<password>' http://127.0.0.1:3011/admin
```

Without a password set (empty/absent), the admin is left open for local
development. The survey form at `/` is always public.

> Note: Basic auth sends the password base64-encoded, so serve the site over
> HTTPS in production (e.g. Caddy/nginx with a TLS cert in front). It stores
> email addresses, so treat `survey.db` accordingly (the form's privacy note
> says emails are used for ticket info only and deleted afterwards).
