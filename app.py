"""Boden GameFest 2027 – Intresseformulär.

A small Flask app that:
  * serves an interactive survey form at ``/``
  * stores every submission in a local SQLite database (``survey.db``)
  * shows an admin dashboard at ``/admin`` with counts + all answers
  * exports all responses as CSV at ``/admin/export.csv``

Run with:   .venv/bin/python app.py
Then open: http://127.0.0.1:5000/          (survey)
           http://127.0.0.1:5000/admin     (admin dashboard)
"""

import csv
import hmac
import io
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from flask import (
    Flask,
    Response,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("BGF_DB", os.path.join(BASE_DIR, "survey.db"))

app = Flask(__name__)
app.secret_key = os.environ.get("BGF_SECRET", "bgf-2027-dev-key-change-me")

# Admin gate: all /admin routes require HTTP Basic auth when this is set.
# Empty (default) leaves the admin open for local development.
ADMIN_PASSWORD = os.environ.get("BGF_ADMIN_PASSWORD", "")


# --------------------------------------------------------------------------- #
# Admin authentication (HTTP Basic, checked server-side)
# --------------------------------------------------------------------------- #
@app.before_request
def _require_admin_auth():
    """Require the admin password for every /admin route (incl. CSV export)."""
    if not request.path.startswith("/admin") or not ADMIN_PASSWORD:
        return None

    auth = request.authorization
    provided = ""
    if auth is not None and auth.type == "basic":
        provided = auth.password or ""

    if hmac.compare_digest(
        provided.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8")
    ):
        return None

    response = make_response("Admin authentication required.", 401)
    response.headers["WWW-Authenticate"] = 'Basic realm="BG27 Admin", charset="UTF-8"'
    return response


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #
def get_db() -> sqlite3.Connection:
    """Return a per-request SQLite connection (row access by column name)."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TEXT    NOT NULL,
    age_group         TEXT,
    location          TEXT,
    want_lan          TEXT,
    regular_visitor   TEXT,
    motivation        TEXT,
    motivation_other  TEXT,
    games_played      TEXT,
    tournaments_want  TEXT,
    interests         TEXT,
    travel_distance   TEXT,
    lan_price         TEXT,
    volunteer         TEXT,
    email             TEXT
);

CREATE TABLE IF NOT EXISTS visitors (
    visitor_id  TEXT PRIMARY KEY,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);
"""


def init_db() -> None:
    """Create the tables if they do not exist yet."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Unique-visitor tracking (anonymous cookie, no personal data)
# --------------------------------------------------------------------------- #
VISITOR_COOKIE = "bgf_visitor"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # one year


@app.before_request
def _track_visitor():
    """Count unique visitors to the survey page via an anonymous cookie.

    A random UUID is stored client-side (HttpOnly) and in SQLite; nothing
    personal is collected, consistent with the form's privacy note.
    """
    if request.path != "/":
        return
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    visitor_id = request.cookies.get(VISITOR_COOKIE)
    db = get_db()
    if not visitor_id:
        visitor_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO visitors (visitor_id, first_seen, last_seen) VALUES (?, ?, ?)",
            (visitor_id, now, now),
        )
    else:
        db.execute(
            "UPDATE visitors SET last_seen = ? WHERE visitor_id = ?",
            (now, visitor_id),
        )
    g.visitor_cookie = visitor_id
    db.commit()


@app.after_request
def _set_visitor_cookie(response):
    """Persist the anonymous visitor id back to the browser."""
    if getattr(g, "visitor_cookie", None):
        response.set_cookie(
            VISITOR_COOKIE,
            g.visitor_cookie,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
        )
    return response


# --------------------------------------------------------------------------- #
# Option lists (kept in one place for form + admin counting)
# --------------------------------------------------------------------------- #
AGE_GROUPS = ["Under 15", "15-18", "19-25", "26-35", "36+"]
YES_NO_MAYBE = ["Ja", "Nej", "Kanske"]
MOTIVATION_OPTIONS = [
    "LAN & spela med vänner",
    "E-sport turneringar",
    "Indie games-utställning",
    "Game-dev & nätverkande",
    "Föreläsningar & inspiration",
    "Retro-gaming",
    "Gemenskapen & stämningen",
]
INTEREST_OPTIONS = ["Game-dev (Spelutveckling)", "Föreläsningar", "Indie games", "Retro"]
TRAVEL_OPTIONS = ["Lokalt (Boden/Fyrkanten)", "Inom Norrbotten", "Utanför länet / Längre"]
VOLUNTEER_OPTIONS = ["Ja", "Nej", "Kanske, berätta mer"]


def _clean(value: str) -> str:
    return (value or "").strip()


def _join_multi(values) -> str:
    """Join a list of checkbox values into a comma-separated string."""
    return ",".join(v for v in values if v)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template(
        "survey.html",
        age_groups=AGE_GROUPS,
        yes_no_maybe=YES_NO_MAYBE,
        motivation_options=MOTIVATION_OPTIONS,
        interest_options=INTEREST_OPTIONS,
        travel_options=TRAVEL_OPTIONS,
        volunteer_options=VOLUNTEER_OPTIONS,
    )


@app.route("/submit", methods=["POST"])
def submit():
    db = get_db()

    row = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "age_group": _clean(request.form.get("age_group")),
        "location": _clean(request.form.get("location")),
        "want_lan": _clean(request.form.get("want_lan")),
        "regular_visitor": _clean(request.form.get("regular_visitor")),
        "motivation": _join_multi(request.form.getlist("motivation")),
        "motivation_other": _clean(request.form.get("motivation_other")),
        "games_played": _clean(request.form.get("games_played")),
        "tournaments_want": _clean(request.form.get("tournaments_want")),
        "interests": _join_multi(request.form.getlist("interests")),
        "travel_distance": _clean(request.form.get("travel_distance")),
        "lan_price": _clean(request.form.get("lan_price")),
        "volunteer": _clean(request.form.get("volunteer")),
        "email": _clean(request.form.get("email")),
    }

    columns = ", ".join(row.keys())
    placeholders = ", ".join(f":{k}" for k in row)
    cur = db.execute(
        f"INSERT INTO responses ({columns}) VALUES ({placeholders})", row
    )
    db.commit()
    response_id = cur.lastrowid

    flash("Tack! Dina svar har sparats.", "success")
    return redirect(url_for("thanks", response_id=response_id))


@app.route("/tack/<int:response_id>")
def thanks(response_id):
    return render_template("thanks.html", response_id=response_id)


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #
def _count_choices(db, column: str, options: list[str]) -> dict:
    """Return {option: count} for a single-choice column."""
    counts = {opt: 0 for opt in options}
    total = db.execute(f"SELECT COUNT(*) AS c FROM responses WHERE {column} != ''").fetchone()["c"]
    for opt in options:
        n = db.execute(
            f"SELECT COUNT(*) AS c FROM responses WHERE {column} = ?", (opt,)
        ).fetchone()["c"]
        counts[opt] = n
    return {"total": total, "counts": counts}


def _count_multi(db, column: str, options: list[str]) -> dict:
    """Count how many responses contain each option in a comma-separated column."""
    counts = {opt: 0 for opt in options}
    rows = db.execute(f"SELECT {column} AS v FROM responses").fetchall()
    for row in rows:
        value = row["v"] or ""
        selected = {s.strip() for s in value.split(",") if s.strip()}
        for opt in options:
            if opt in selected:
                counts[opt] += 1
    return {"total": len(rows), "counts": counts}


@app.route("/admin")
def admin():
    db = get_db()
    total = db.execute("SELECT COUNT(*) AS c FROM responses").fetchone()["c"]

    stats = {
        "age_group": _count_choices(db, "age_group", AGE_GROUPS),
        "want_lan": _count_choices(db, "want_lan", YES_NO_MAYBE),
        "regular_visitor": _count_choices(db, "regular_visitor", YES_NO_MAYBE),
        "motivation": _count_multi(db, "motivation", MOTIVATION_OPTIONS),
        "interests": _count_multi(db, "interests", INTEREST_OPTIONS),
        "travel_distance": _count_choices(db, "travel_distance", TRAVEL_OPTIONS),
        "volunteer": _count_choices(db, "volunteer", VOLUNTEER_OPTIONS),
    }

    # Free-text / email summary
    with_email = db.execute(
        "SELECT COUNT(*) AS c FROM responses WHERE email != ''"
    ).fetchone()["c"]

    # Unique-visitor counters (anonymous cookie-based)
    unique_visitors = db.execute("SELECT COUNT(*) AS c FROM visitors").fetchone()["c"]
    visitors_today = db.execute(
        "SELECT COUNT(*) AS c FROM visitors WHERE date(first_seen) = date('now')"
    ).fetchone()["c"]

    responses = db.execute(
        "SELECT * FROM responses ORDER BY id DESC"
    ).fetchall()

    return render_template(
        "admin.html",
        total=total,
        stats=stats,
        with_email=with_email,
        unique_visitors=unique_visitors,
        visitors_today=visitors_today,
        responses=responses,
        age_groups=AGE_GROUPS,
        motivation_options=MOTIVATION_OPTIONS,
        interest_options=INTEREST_OPTIONS,
    )


@app.route("/admin/export.csv")
def export_csv():
    db = get_db()
    rows = db.execute("SELECT * FROM responses ORDER BY id ASC").fetchall()

    buf = io.StringIO()
    if rows:
        fieldnames = rows[0].keys()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fieldnames})

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=bgf2027_responses.csv"},
    )


init_db()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    app.run(host=host, port=port, debug=False)
