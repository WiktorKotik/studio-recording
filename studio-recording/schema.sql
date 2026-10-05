-- Схема БД «Студия звукозаписи» (SQLite 3)
-- Запуск: python init_db.py
PRAGMA foreign_keys = ON;

-- ---------- Справочники и пользователи ----------
CREATE TABLE roles (
    id    INTEGER PRIMARY KEY,
    code  TEXT NOT NULL UNIQUE,              -- admin, producer, artist, engineer, outlet
    title TEXT NOT NULL
);

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    role_id       INTEGER NOT NULL REFERENCES roles(id),
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    phone         TEXT,
    password_hash TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE rooms (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    room_type   TEXT NOT NULL CHECK (room_type IN ('control', 'live')),
    hourly_rate NUMERIC NOT NULL CHECK (hourly_rate >= 0)
);

CREATE TABLE services (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE,
    price NUMERIC NOT NULL CHECK (price >= 0)
);

-- ---------- Договоры и оплата ----------
CREATE TABLE contracts (
    id              INTEGER PRIMARY KEY,
    number          TEXT NOT NULL UNIQUE,
    client_id       INTEGER NOT NULL REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'signed', 'terminated')),
    prepayment      NUMERIC NOT NULL DEFAULT 0 CHECK (prepayment >= 0),
    royalty_percent NUMERIC NOT NULL DEFAULT 0 CHECK (royalty_percent BETWEEN 0 AND 100),
    signed_at       TEXT,
    valid_until     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE payments (
    id          INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    amount      NUMERIC NOT NULL CHECK (amount > 0),
    kind        TEXT NOT NULL CHECK (kind IN ('prepayment', 'session', 'other')),
    paid_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- Альбомы, треки, версии файлов ----------
CREATE TABLE albums (
    id          INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contracts(id),
    producer_id INTEGER REFERENCES users(id),
    title       TEXT NOT NULL,
    genre       TEXT,
    status      TEXT NOT NULL DEFAULT 'planned'
                CHECK (status IN ('planned', 'recording', 'mixing', 'done', 'in_print')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE album_members (
    album_id     INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    project_role TEXT NOT NULL,
    PRIMARY KEY (album_id, user_id)
);

CREATE TABLE tracks (
    id       INTEGER PRIMARY KEY,
    album_id INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    title    TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    status   TEXT NOT NULL DEFAULT 'draft'
             CHECK (status IN ('draft', 'in_work', 'approved')),
    UNIQUE (album_id, position)
);

CREATE TABLE track_versions (
    id          INTEGER PRIMARY KEY,
    track_id    INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    version_no  INTEGER NOT NULL CHECK (version_no > 0),
    kind        TEXT NOT NULL CHECK (kind IN ('demo', 'draft', 'final_mix')),
    file_name   TEXT NOT NULL,
    uploaded_by INTEGER NOT NULL REFERENCES users(id),
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    comment     TEXT,
    UNIQUE (track_id, version_no)           -- жёсткая нумерация версий
);

-- ---------- Расписание ----------
CREATE TABLE sessions (
    id          INTEGER PRIMARY KEY,
    album_id    INTEGER NOT NULL REFERENCES albums(id),
    room_id     INTEGER NOT NULL REFERENCES rooms(id),
    engineer_id INTEGER REFERENCES users(id),
    created_by  INTEGER NOT NULL REFERENCES users(id),
    starts_at   TEXT NOT NULL,              -- 'YYYY-MM-DD HH:MM'
    ends_at     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'booked'
                CHECK (status IN ('booked', 'done', 'cancelled')),
    total_cost  NUMERIC NOT NULL DEFAULT 0 CHECK (total_cost >= 0),
    CHECK (ends_at > starts_at)
);

CREATE TABLE session_services (
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services(id),
    quantity   INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    PRIMARY KEY (session_id, service_id)
);

-- ---------- Тиражирование и дистрибуция ----------
CREATE TABLE outlets (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    contact_email TEXT NOT NULL,
    address       TEXT,
    rep_user_id   INTEGER REFERENCES users(id)
);

CREATE TABLE print_runs (
    id           INTEGER PRIMARY KEY,
    album_id     INTEGER NOT NULL REFERENCES albums(id),
    medium       TEXT NOT NULL CHECK (medium IN ('CD', 'vinyl', 'digital')),
    total_copies INTEGER NOT NULL CHECK (total_copies > 0),
    status       TEXT NOT NULL DEFAULT 'planned'
                 CHECK (status IN ('planned', 'printing', 'shipped')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE print_run_items (
    id              INTEGER PRIMARY KEY,
    print_run_id    INTEGER NOT NULL REFERENCES print_runs(id) ON DELETE CASCADE,
    outlet_id       INTEGER NOT NULL REFERENCES outlets(id),
    copies          INTEGER NOT NULL CHECK (copies > 0),
    delivery_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (delivery_status IN ('pending', 'sent', 'received')),
    act_number      TEXT,
    UNIQUE (print_run_id, outlet_id)
);

-- ---------- Журнал действий ----------
CREATE TABLE audit_log (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action     TEXT NOT NULL,
    entity     TEXT NOT NULL,
    entity_id  INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- Индексы ----------
CREATE INDEX idx_sessions_room_time ON sessions (room_id, starts_at, ends_at);
CREATE INDEX idx_tracks_album       ON tracks (album_id);
CREATE INDEX idx_albums_contract    ON albums (contract_id);
CREATE INDEX idx_versions_track     ON track_versions (track_id);

-- ---------- Бизнес-правила (триггеры) ----------
-- 1. Бронирование запрещено, пока договор не переведён в статус «Подписан»
CREATE TRIGGER trg_sessions_contract_signed
BEFORE INSERT ON sessions
WHEN (SELECT c.status FROM albums a JOIN contracts c ON c.id = a.contract_id
      WHERE a.id = NEW.album_id) <> 'signed'
BEGIN
    SELECT RAISE(ABORT, 'Договор не подписан: бронирование недоступно');
END;

-- 2. Одно помещение нельзя забронировать дважды на пересекающееся время
CREATE TRIGGER trg_sessions_no_overlap
BEFORE INSERT ON sessions
WHEN EXISTS (SELECT 1 FROM sessions s
             WHERE s.room_id = NEW.room_id AND s.status <> 'cancelled'
               AND NEW.starts_at < s.ends_at AND NEW.ends_at > s.starts_at)
BEGIN
    SELECT RAISE(ABORT, 'Слот занят: помещение уже забронировано на это время');
END;

-- 3. Альбом можно отправить в тираж, только если все его треки утверждены
CREATE TRIGGER trg_album_to_print
BEFORE UPDATE OF status ON albums
WHEN NEW.status = 'in_print'
 AND ((SELECT COUNT(*) FROM tracks WHERE album_id = NEW.id) = 0
   OR (SELECT COUNT(*) FROM tracks WHERE album_id = NEW.id AND status <> 'approved') > 0)
BEGIN
    SELECT RAISE(ABORT, 'Не все треки утверждены: отправка в тираж невозможна');
END;

-- 4. Сумма копий по торговым точкам не может превышать общий тираж
CREATE TRIGGER trg_print_items_sum
BEFORE INSERT ON print_run_items
WHEN (SELECT COALESCE(SUM(copies), 0) FROM print_run_items
      WHERE print_run_id = NEW.print_run_id) + NEW.copies
     > (SELECT total_copies FROM print_runs WHERE id = NEW.print_run_id)
BEGIN
    SELECT RAISE(ABORT, 'Сумма копий по точкам превышает общий тираж');
END;
