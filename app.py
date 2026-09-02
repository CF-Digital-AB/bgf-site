"""Boden GameFest 2027 – Intresseformulär.

A small Flask app that:
  * serves an interactive survey form at ``/``
  * stores every submission in a local SQLite database (``survey.db``)
  * shows an admin dashboard at ``/admin`` with counts + all answers
  * exports all responses as CSV at ``/admin/export.csv``
  * deletes an individual response from the admin dashboard (``/admin/delete/<id>``)

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
    send_from_directory,
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
    participation     TEXT,
    motivation        TEXT,
    motivation_other  TEXT,
    games_played      TEXT,
    tournaments_want  TEXT,
    interests         TEXT,
    travel_distance   TEXT,
    lan_price         TEXT,
    volunteer         TEXT,
    email             TEXT,
    utm_source        TEXT,
    completion_token  TEXT,
    completed_at      TEXT
);

CREATE TABLE IF NOT EXISTS visitors (
    visitor_id  TEXT PRIMARY KEY,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    utm_source  TEXT
);
"""


def init_db() -> None:
    """Create the tables if they do not exist yet, and migrate old ones."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        # Migrations for databases created before utm_source tracking: add the
        # missing column in place so existing rows are preserved.
        visitor_cols = {row[1] for row in conn.execute("PRAGMA table_info(visitors)")}
        if "utm_source" not in visitor_cols:
            conn.execute("ALTER TABLE visitors ADD COLUMN utm_source TEXT")
        response_cols = {row[1] for row in conn.execute("PRAGMA table_info(responses)")}
        if "utm_source" not in response_cols:
            conn.execute("ALTER TABLE responses ADD COLUMN utm_source TEXT")
        if "completion_token" not in response_cols:
            conn.execute("ALTER TABLE responses ADD COLUMN completion_token TEXT")
        if "participation" not in response_cols:
            conn.execute("ALTER TABLE responses ADD COLUMN participation TEXT")
        if "completed_at" not in response_cols:
            conn.execute("ALTER TABLE responses ADD COLUMN completed_at TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS responses_completion_token "
            "ON responses(completion_token)"
        )
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
    personal is collected, consistent with the form's privacy note. The
    ``utm_source`` query parameter (e.g. ``?utm_source=reddit``) is recorded
    for ad-attribution stats.
    """
    if request.path != "/":
        return
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    visitor_id = request.cookies.get(VISITOR_COOKIE)
    utm_source = (request.args.get("utm_source") or "").strip() or None
    db = get_db()
    if not visitor_id:
        visitor_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO visitors (visitor_id, first_seen, last_seen, utm_source) "
            "VALUES (?, ?, ?, ?)",
            (visitor_id, now, now, utm_source),
        )
    else:
        db.execute(
            "UPDATE visitors SET last_seen = ? WHERE visitor_id = ?",
            (now, visitor_id),
        )
        if utm_source:
            # First-touch attribution: remember the source only if we have none yet.
            db.execute(
                "UPDATE visitors SET utm_source = ? "
                "WHERE visitor_id = ? AND (utm_source IS NULL OR utm_source = '')",
                (utm_source, visitor_id),
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
PARTICIPATION_OPTIONS = [
    "Spela på LAN",
    "Komma som besökare",
    "Både LAN och besökare",
    "Utställare - Spel",
    "Utställare - Övrigt",
    "Inte säker ännu",
]

# --------------------------------------------------------------------------- #
# Value maps for the standalone index.html form.
#
# The landing page's <form> posts short machine codes (e.g. age=under_15,
# reasons=lan_vanner). These tables translate each code into the same
# human-readable label that the admin dashboard counts against and that is
# written to SQLite / exported as CSV. Keeping the stored values identical to
# the option lists above means existing rows and the admin charts stay correct.
# --------------------------------------------------------------------------- #
AGE_MAP = {
    "under_15": "Under 15",
    "15_18": "15-18",
    "19_25": "19-25",
    "26_35": "26-35",
    "36_plus": "36+",
}
YES_NO_MAP = {"ja": "Ja", "nej": "Nej", "kanske": "Kanske"}
MOTIVATION_MAP = {
    "lan_vanner": "LAN & spela med vänner",
    "esport": "E-sport turneringar",
    "indie": "Indie games-utställning",
    "gamedev": "Game-dev & nätverkande",
    "lectures": "Föreläsningar & inspiration",
    "retro": "Retro-gaming",
    "gemenskap": "Gemenskapen & stämningen",
}
INTEREST_MAP = {
    "gamedev": "Game-dev (Spelutveckling)",
    "forelasningar": "Föreläsningar",
    "indie": "Indie games",
    "retro": "Retro",
}
TRAVEL_MAP = {
    "lokalt": "Lokalt (Boden/Fyrkanten)",
    "norrbotten": "Inom Norrbotten",
    "sverige": "Utanför länet / Längre",
}
VOLUNTEER_MAP = {"ja": "Ja", "nej": "Nej", "kanske": "Kanske, berätta mer"}


def _clean(value: str) -> str:
    return (value or "").strip()


def _join_multi(values) -> str:
    """Join a list of checkbox values into a comma-separated string."""
    return ",".join(v for v in values if v)


def _map(value, mapping: dict) -> str:
    """Translate an index.html form code into its stored label.

    Empty values map to "" and unknown codes pass through unchanged, so free
    text (and any future option not yet in the table) round-trips losslessly.
    """
    value = _clean(value)
    return mapping.get(value, value)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    # The public landing page (with the embedded survey form) is the standalone
    # index.html. Serve it verbatim so its inline Tailwind/JS/CSS stay intact —
    # no Jinja templating needed, and nothing in the file gets accidentally
    # parsed as a template expression.
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/submit", methods=["POST"])
def submit():
    db = get_db()

    # Field names below are the `name` attributes of index.html's form. Single
    # choice + multi-choice values are mapped through the *_MAP tables so they
    # land in SQLite as the same labels the admin dashboard expects.
    participation = _clean(request.form.get("participation"))
    participation_values = {
        # participation code -> (want_lan, regular_visitor, participation label)
        "lan": ("Ja", "Nej", "Spela på LAN"),
        "visitor": ("Nej", "Ja", "Komma som besökare"),
        "both": ("Ja", "Ja", "Både LAN och besökare"),
        "exhibitor_games": ("Nej", "Nej", "Utställare - Spel"),
        "exhibitor_other": ("Nej", "Nej", "Utställare - Övrigt"),
        "unsure": ("Kanske", "Kanske", "Inte säker ännu"),
    }
    age = _clean(request.form.get("age"))
    email = _clean(request.form.get("email"))
    if age not in AGE_MAP or participation not in participation_values or not email:
        return "Fyll i alla tre frågorna med giltiga svar.", 400
    want_lan, regular_visitor, participation_label = participation_values[participation]
    row = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "age_group": _map(age, AGE_MAP),
        "location": _clean(request.form.get("location")),
        "want_lan": want_lan,
        "regular_visitor": regular_visitor,
        "participation": participation_label,
        "motivation": _join_multi(
            [_map(v, MOTIVATION_MAP) for v in request.form.getlist("reasons")]
        ),
        "motivation_other": _clean(request.form.get("reason_other")),
        "games_played": _clean(request.form.get("games")),
        "tournaments_want": _clean(request.form.get("tournaments")),
        "interests": _join_multi(
            [_map(v, INTEREST_MAP) for v in request.form.getlist("interests")]
        ),
        "travel_distance": _map(request.form.get("travel_distance"), TRAVEL_MAP),
        "lan_price": _clean(request.form.get("price")),
        "volunteer": _map(request.form.get("volunteer"), VOLUNTEER_MAP),
        "email": email,
        "utm_source": _clean(request.form.get("utm_source")),
        "completion_token": uuid.uuid4().hex,
        "completed_at": None,
    }

    columns = ", ".join(row.keys())
    placeholders = ", ".join(f":{k}" for k in row)
    db.execute(f"INSERT INTO responses ({columns}) VALUES ({placeholders})", row)
    db.commit()
    flash("Tack! Dina svar har sparats.", "success")
    return redirect(url_for("thanks", token=row["completion_token"]))


@app.route("/tack/<token>")
def thanks(token):
    response = get_db().execute(
        "SELECT id, completion_token, completed_at FROM responses WHERE completion_token = ?",
        (token,),
    ).fetchone()
    if response is None:
        return "Anmälan hittades inte.", 404
    return render_template("thanks.html", response=response)


@app.route("/komplettera/<token>", methods=["GET", "POST"])
def complete_response(token):
    db = get_db()
    response = db.execute(
        "SELECT * FROM responses WHERE completion_token = ?", (token,)
    ).fetchone()
    if response is None:
        return "Anmälan hittades inte.", 404
    if request.method == "GET":
        return render_template("followup.html", response=response)

    values = {
        "location": _clean(request.form.get("location")),
        "motivation": _join_multi(
            [_map(v, MOTIVATION_MAP) for v in request.form.getlist("reasons")]
        ),
        "motivation_other": _clean(request.form.get("reason_other")),
        "games_played": _clean(request.form.get("games")),
        "tournaments_want": _clean(request.form.get("tournaments")),
        "interests": _join_multi(
            [_map(v, INTEREST_MAP) for v in request.form.getlist("interests")]
        ),
        "travel_distance": _map(request.form.get("travel_distance"), TRAVEL_MAP),
        "lan_price": _clean(request.form.get("price")),
        "volunteer": _map(request.form.get("volunteer"), VOLUNTEER_MAP),
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "completion_token": token,
    }
    db.execute(
        """UPDATE responses SET location=:location, motivation=:motivation,
        motivation_other=:motivation_other, games_played=:games_played,
        tournaments_want=:tournaments_want, interests=:interests,
        travel_distance=:travel_distance, lan_price=:lan_price,
        volunteer=:volunteer, completed_at=:completed_at
        WHERE completion_token=:completion_token""",
        values,
    )
    db.commit()
    return redirect(url_for("thanks", token=token, completed="1"))


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
        "participation": _count_choices(db, "participation", PARTICIPATION_OPTIONS),
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
    completed = db.execute(
        "SELECT COUNT(*) AS c FROM responses WHERE completed_at IS NOT NULL"
    ).fetchone()["c"]

    # Unique-visitor counters (anonymous cookie-based)
    unique_visitors = db.execute("SELECT COUNT(*) AS c FROM visitors").fetchone()["c"]
    visitors_today = db.execute(
        "SELECT COUNT(*) AS c FROM visitors WHERE date(first_seen) = date('now')"
    ).fetchone()["c"]

    # Campaign-attribution stats (utm_source query param, e.g. Reddit ads or QR)
    reddit_visitors = db.execute(
        "SELECT COUNT(*) AS c FROM visitors WHERE lower(trim(utm_source)) = 'reddit'"
    ).fetchone()["c"]
    reddit_responses = db.execute(
        "SELECT COUNT(*) AS c FROM responses WHERE lower(trim(utm_source)) = 'reddit'"
    ).fetchone()["c"]
    qr_visitors = db.execute(
        "SELECT COUNT(*) AS c FROM visitors WHERE lower(trim(utm_source)) = 'qr'"
    ).fetchone()["c"]
    qr_responses = db.execute(
        "SELECT COUNT(*) AS c FROM responses WHERE lower(trim(utm_source)) = 'qr'"
    ).fetchone()["c"]
    utm_breakdown = {"counts": {}, "total": 0}
    for row in db.execute(
        "SELECT utm_source AS src, COUNT(*) AS c FROM visitors "
        "WHERE utm_source IS NOT NULL AND utm_source != '' "
        "GROUP BY utm_source ORDER BY c DESC"
    ).fetchall():
        label = row["src"] or "Övrigt"
        utm_breakdown["counts"][label] = row["c"]
        utm_breakdown["total"] += row["c"]

    responses = db.execute(
        "SELECT * FROM responses ORDER BY id DESC"
    ).fetchall()

    return render_template(
        "admin.html",
        total=total,
        stats=stats,
        with_email=with_email,
        completed=completed,
        unique_visitors=unique_visitors,
        visitors_today=visitors_today,
        reddit_visitors=reddit_visitors,
        reddit_responses=reddit_responses,
        qr_visitors=qr_visitors,
        qr_responses=qr_responses,
        utm_breakdown=utm_breakdown,
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


@app.route("/admin/delete/<int:response_id>", methods=["POST"])
def admin_delete(response_id):
    """Delete a single survey response by id (admin only)."""
    db = get_db()
    cur = db.execute("DELETE FROM responses WHERE id = ?", (response_id,))
    db.commit()
    if cur.rowcount:
        flash(f"Svar #{response_id} raderades.", "success")
    else:
        flash(f"Hittade inget svar med id #{response_id}.", "error")
    return redirect(url_for("admin"))


init_db()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    app.run(host=host, port=port, debug=False)
