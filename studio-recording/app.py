"""Студия звукозаписи — начальная версия веб-приложения (Flask + SQLite)."""
import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))


def load_env(path=os.path.join(BASE, ".env")):
    """Читает секреты из файла .env (в репозиторий не попадает)."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_env()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE, "studio.db"))

ALBUM_STATUS = {"planned": "В планах", "recording": "Запись", "mixing": "Сведение",
                "done": "Готово", "in_print": "В тираже"}
TRACK_STATUS = {"draft": "Черновик", "in_work": "В работе", "approved": "Утверждён"}
SESSION_STATUS = {"booked": "Забронировано", "done": "Проведена", "cancelled": "Отменена"}
CONTRACT_STATUS = {"draft": "Черновик", "signed": "Подписан", "terminated": "Расторгнут"}
KIND = {"demo": "Демо", "draft": "Черновик", "final_mix": "Финальный микс"}
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


# ---------- работа с БД ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    rows = get_db().execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows


# ---------- авторизация ----------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def load_user():
    g.user = None
    if "user_id" in session:
        g.user = query("""SELECT u.id, u.full_name, r.code AS role, r.title AS role_title
                          FROM users u JOIN roles r ON r.id = u.role_id
                          WHERE u.id = ? AND u.is_active = 1""", (session["user_id"],), one=True)


@app.context_processor
def helpers():
    return dict(ALBUM_STATUS=ALBUM_STATUS, TRACK_STATUS=TRACK_STATUS, SESSION_STATUS=SESSION_STATUS,
                CONTRACT_STATUS=CONTRACT_STATUS, KIND=KIND)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = query("SELECT id, password_hash FROM users WHERE email = ? AND is_active = 1",
                     (email,), one=True)
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Неверный e-mail или пароль", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- доступ к альбомам по ролям ----------
ALBUM_ACCESS = """(? = 'admin' OR a.producer_id = ?
                   OR a.id IN (SELECT album_id FROM album_members WHERE user_id = ?))"""


def access_args():
    return (g.user["role"], g.user["id"], g.user["id"])


# ---------- страницы ----------
@app.route("/")
@login_required
def dashboard():
    stats = {
        "active": query(f"SELECT COUNT(*) FROM albums a WHERE a.status IN ('planned','recording','mixing') AND {ALBUM_ACCESS}",
                        access_args(), one=True)[0],
        "week": query(f"""SELECT COUNT(*) FROM sessions s JOIN albums a ON a.id = s.album_id
                          WHERE s.status = 'booked' AND date(s.starts_at) BETWEEN date('now') AND date('now','+7 day')
                          AND {ALBUM_ACCESS}""", access_args(), one=True)[0],
        "drafts": query("SELECT COUNT(*) FROM contracts WHERE status = 'draft'", one=True)[0],
        "prints": query("SELECT COUNT(*) FROM print_runs WHERE status <> 'shipped'", one=True)[0],
    }
    upcoming = query(f"""SELECT s.*, a.title AS album, r.name AS room, u.full_name AS engineer
                         FROM sessions s JOIN albums a ON a.id = s.album_id
                         JOIN rooms r ON r.id = s.room_id LEFT JOIN users u ON u.id = s.engineer_id
                         WHERE s.status = 'booked' AND s.starts_at >= datetime('now') AND {ALBUM_ACCESS}
                         ORDER BY s.starts_at LIMIT 5""", access_args())
    albums = query(f"""SELECT a.id, a.title, a.status, a.genre,
                         (SELECT COUNT(*) FROM tracks t WHERE t.album_id = a.id) AS tracks,
                         (SELECT COUNT(*) FROM tracks t WHERE t.album_id = a.id AND t.status = 'approved') AS approved
                       FROM albums a WHERE {ALBUM_ACCESS} ORDER BY a.id""", access_args())
    events = query("""SELECT l.action, l.created_at, u.full_name FROM audit_log l
                      LEFT JOIN users u ON u.id = l.user_id ORDER BY l.created_at DESC LIMIT 4""")
    return render_template("dashboard.html", stats=stats, upcoming=upcoming, albums=albums, events=events)


@app.route("/albums")
@login_required
def albums():
    rows = query(f"""SELECT a.id, a.title, a.genre, a.status, c.number AS contract, c.status AS contract_status,
                       p.full_name AS producer,
                       (SELECT COUNT(*) FROM tracks t WHERE t.album_id = a.id) AS tracks,
                       (SELECT COUNT(*) FROM tracks t WHERE t.album_id = a.id AND t.status = 'approved') AS approved
                     FROM albums a JOIN contracts c ON c.id = a.contract_id
                     LEFT JOIN users p ON p.id = a.producer_id
                     WHERE {ALBUM_ACCESS} ORDER BY a.id""", access_args())
    return render_template("albums.html", albums=rows)


@app.route("/albums/<int:album_id>")
@login_required
def album(album_id):
    a = query(f"""SELECT a.*, c.number AS contract, c.status AS contract_status, p.full_name AS producer
                  FROM albums a JOIN contracts c ON c.id = a.contract_id
                  LEFT JOIN users p ON p.id = a.producer_id
                  WHERE a.id = ? AND {ALBUM_ACCESS}""", (album_id,) + access_args(), one=True)
    if a is None:
        flash("Альбом не найден или нет доступа", "error")
        return redirect(url_for("albums"))
    tracks = query("""SELECT t.*, (SELECT MAX(version_no) FROM track_versions v WHERE v.track_id = t.id) AS last_version,
                        (SELECT file_name FROM track_versions v WHERE v.track_id = t.id
                         ORDER BY version_no DESC LIMIT 1) AS last_file
                      FROM tracks t WHERE t.album_id = ? ORDER BY t.position""", (album_id,))
    members = query("""SELECT u.full_name, m.project_role FROM album_members m
                       JOIN users u ON u.id = m.user_id WHERE m.album_id = ?""", (album_id,))
    sessions_ = query("""SELECT s.starts_at, s.ends_at, s.status, r.name AS room FROM sessions s
                         JOIN rooms r ON r.id = s.room_id WHERE s.album_id = ?
                         ORDER BY s.starts_at DESC LIMIT 5""", (album_id,))
    return render_template("album.html", a=a, tracks=tracks, members=members, sessions=sessions_)


@app.route("/schedule")
@login_required
def schedule():
    try:
        start = date.fromisoformat(request.args.get("from", ""))
    except ValueError:
        start = date.today()
    days = [start + timedelta(days=i) for i in range(7)]
    rooms = query("SELECT * FROM rooms ORDER BY id")
    rows = query("""SELECT s.*, a.title AS album, u.full_name AS engineer FROM sessions s
                    JOIN albums a ON a.id = s.album_id LEFT JOIN users u ON u.id = s.engineer_id
                    WHERE s.status <> 'cancelled' AND date(s.starts_at) BETWEEN ? AND ?
                    ORDER BY s.starts_at""", (days[0].isoformat(), days[-1].isoformat()))
    grid = {(d.isoformat(), r["id"]): [] for d in days for r in rooms}
    for s in rows:
        grid[(s["starts_at"][:10], s["room_id"])].append(s)
    my_albums = query(f"SELECT a.id, a.title FROM albums a WHERE {ALBUM_ACCESS} ORDER BY a.title", access_args())
    engineers = query("""SELECT u.id, u.full_name FROM users u JOIN roles r ON r.id = u.role_id
                         WHERE r.code = 'engineer' ORDER BY u.full_name""")
    services = query("SELECT * FROM services ORDER BY id")
    return render_template("schedule.html", days=days, rooms=rooms, grid=grid, weekdays=WEEKDAYS,
                           albums=my_albums, engineers=engineers, services=services,
                           prev=(start - timedelta(days=7)).isoformat(), nxt=(start + timedelta(days=7)).isoformat(),
                           today=date.today().isoformat())


@app.route("/schedule/book", methods=["POST"])
@login_required
def book():
    f = request.form
    db = get_db()
    try:
        starts = f"{f['date']} {f['start']}"
        ends = f"{f['date']} {f['end']}"
        hours = (datetime.fromisoformat(ends) - datetime.fromisoformat(starts)).total_seconds() / 3600
        if hours <= 0:
            raise ValueError("Время окончания должно быть позже времени начала")
        room = query("SELECT hourly_rate FROM rooms WHERE id = ?", (f["room_id"],), one=True)
        service_ids = [int(x) for x in f.getlist("services")]
        cost = hours * room["hourly_rate"]
        for sid in service_ids:
            cost += query("SELECT price FROM services WHERE id = ?", (sid,), one=True)["price"]
        album_ok = query(f"SELECT 1 FROM albums a WHERE a.id = ? AND {ALBUM_ACCESS}",
                         (f["album_id"],) + access_args(), one=True)
        if not album_ok:
            raise ValueError("Нет доступа к выбранному альбому")
        cur = db.execute("""INSERT INTO sessions (album_id, room_id, engineer_id, created_by, starts_at, ends_at, total_cost)
                            VALUES (?,?,?,?,?,?,?)""",
                         (f["album_id"], f["room_id"], f.get("engineer_id") or None, g.user["id"], starts, ends, cost))
        for sid in service_ids:
            db.execute("INSERT INTO session_services (session_id, service_id) VALUES (?,?)", (cur.lastrowid, sid))
        db.execute("INSERT INTO audit_log (user_id, action, entity, entity_id) VALUES (?,?,?,?)",
                   (g.user["id"], "Создано бронирование", "sessions", cur.lastrowid))
        db.commit()
        flash(f"Бронирование создано. Итоговая стоимость: {cost:,.0f} ₽".replace(",", " "), "ok")
    except (sqlite3.IntegrityError, ValueError, KeyError) as exc:
        db.rollback()
        flash(str(exc), "error")   # текст ошибки приходит из триггеров БД
    return redirect(url_for("schedule", **{"from": f.get("date", "")}))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
