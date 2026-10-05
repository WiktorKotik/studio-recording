"""Создаёт файл БД studio.db: схема + демонстрационные данные.
Запуск: python init_db.py [путь_к_бд]
"""
import os
import sqlite3
import sys
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "studio.db")
DEMO_PASSWORD = "demo1234"  # только для демонстрационных учётных записей


def dt(days, hh, mm=0):
    d = date.today() + timedelta(days=days)
    return f"{d.isoformat()} {hh:02d}:{mm:02d}"


def build(db_path=DB_PATH):
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    with open(os.path.join(BASE, "schema.sql"), encoding="utf-8") as f:
        con.executescript(f.read())
    def ph():  # у каждого пользователя своя «соль» хеша
        return generate_password_hash(DEMO_PASSWORD)
    many = con.executemany

    many("INSERT INTO roles (id, code, title) VALUES (?,?,?)", [
        (1, "admin", "Администратор студии"), (2, "producer", "Музыкальный продюсер"),
        (3, "artist", "Исполнитель"), (4, "engineer", "Звукорежиссёр"),
        (5, "outlet", "Представитель торговой точки")])

    many("INSERT INTO users (id, role_id, full_name, email, phone, password_hash) VALUES (?,?,?,?,?,?)", [
        (1, 1, "Крылова Анна Сергеевна", "admin@studio.example", "+7 913 000-11-01", ph()),
        (2, 2, "Левина Марина Андреевна", "producer@studio.example", "+7 913 000-11-02", ph()),
        (3, 3, "Волков Артём Игоревич", "artist@studio.example", "+7 913 000-11-03", ph()),
        (4, 3, "Соколов Дмитрий Павлович", "sokolov@studio.example", "+7 913 000-11-04", ph()),
        (5, 4, "Назаров Игорь Олегович", "engineer@studio.example", "+7 913 000-11-05", ph()),
        (6, 4, "Фомина Елена Викторовна", "fomina@studio.example", "+7 913 000-11-06", ph()),
        (7, 3, "Громов Кирилл Алексеевич", "gromov@studio.example", "+7 913 000-11-07", ph()),
        (8, 5, "Петров Сергей Николаевич", "outlet@studio.example", "+7 383 000-22-08", ph()),
        (9, 5, "Исаева Ольга Романовна", "isaeva@studio.example", "+7 383 000-22-09", ph())])

    many("INSERT INTO rooms (id, name, room_type, hourly_rate) VALUES (?,?,?,?)", [
        (1, "Зал А (тон-зал)", "live", 2500), (2, "Зал Б (контрольная комната)", "control", 1800),
        (3, "Зал В (вокальная кабина)", "live", 1200)])

    many("INSERT INTO services (id, name, price) VALUES (?,?,?)", [
        (1, "Микрофон Neumann U87", 500), (2, "Ламповый предусилитель", 700),
        (3, "Барабанная установка", 900), (4, "Услуги ассистента", 600)])

    many("""INSERT INTO contracts (id, number, client_id, status, prepayment, royalty_percent, signed_at, valid_until)
            VALUES (?,?,?,?,?,?,?,?)""", [
        (1, "СЗ-2026/001", 3, "signed", 30000, 15, "2026-08-20", "2027-08-20"),
        (2, "СЗ-2026/002", 4, "signed", 45000, 12, "2026-07-02", "2027-07-02"),
        (3, "СЗ-2026/003", 7, "draft", 20000, 10, None, None),
        (4, "СЗ-2026/004", 3, "signed", 60000, 15, "2026-03-11", "2027-03-11"),
        (5, "СЗ-2026/005", 4, "signed", 80000, 12, "2026-04-05", "2027-04-05")])

    many("INSERT INTO payments (contract_id, amount, kind, paid_at) VALUES (?,?,?,?)", [
        (1, 30000, "prepayment", "2026-08-21 11:05"), (2, 45000, "prepayment", "2026-07-03 15:40"),
        (4, 60000, "prepayment", "2026-03-12 10:12"), (5, 80000, "prepayment", "2026-04-06 09:30"),
        (1, 12500, "session", "2026-09-14 18:20")])

    many("INSERT INTO albums (id, contract_id, producer_id, title, genre, status) VALUES (?,?,?,?,?,?)", [
        (1, 1, 2, "Ночной эфир", "Инди-поп", "recording"),
        (2, 2, 2, "Северный ветер", "Рок", "mixing"),
        (3, 3, 2, "Первый свет", "Электроника", "planned"),
        (4, 4, 2, "Городские огни", "Синтипоп", "recording"),
        (5, 5, 2, "Сибирский винил", "Фолк-рок", "recording")])

    many("INSERT INTO album_members (album_id, user_id, project_role) VALUES (?,?,?)", [
        (1, 3, "Исполнитель"), (1, 5, "Звукорежиссёр"), (2, 4, "Исполнитель"), (2, 6, "Звукорежиссёр"),
        (3, 7, "Исполнитель"), (4, 3, "Исполнитель"), (4, 5, "Звукорежиссёр"),
        (5, 4, "Исполнитель"), (5, 6, "Звукорежиссёр")])

    tracks = [
        (1, 1, "Ночной эфир", 1, "in_work"), (2, 1, "Свет в окне", 2, "in_work"),
        (3, 1, "Радиоволна", 3, "draft"), (4, 1, "Холодный кофе", 4, "draft"),
        (5, 2, "Северный ветер", 1, "approved"), (6, 2, "Над рекой", 2, "in_work"),
        (7, 2, "Дорога домой", 3, "in_work"),
        (8, 3, "Первый свет", 1, "draft"),
        (9, 4, "Городские огни", 1, "approved"), (10, 4, "Неоновый дождь", 2, "approved"),
        (11, 4, "Последний трамвай", 3, "approved"),
        (12, 5, "Сибирский винил", 1, "approved"), (13, 5, "Тайга", 2, "approved")]
    many("INSERT INTO tracks (id, album_id, title, position, status) VALUES (?,?,?,?,?)", tracks)

    many("""INSERT INTO track_versions (track_id, version_no, kind, file_name, uploaded_by, uploaded_at, comment)
            VALUES (?,?,?,?,?,?,?)""", [
        (1, 1, "demo", "nochnoy_efir_demo_v1.wav", 3, "2026-08-25 12:10", "Первая демо-запись"),
        (1, 2, "draft", "nochnoy_efir_draft_v2.wav", 5, "2026-09-10 17:45", "Записан вокал"),
        (1, 3, "draft", "nochnoy_efir_draft_v3.wav", 5, "2026-09-28 19:02", "Добавлены синтезаторы"),
        (2, 1, "demo", "svet_v_okne_demo_v1.wav", 3, "2026-08-26 13:00", None),
        (2, 2, "draft", "svet_v_okne_draft_v2.wav", 5, "2026-09-18 16:30", "Перезаписаны гитары"),
        (5, 1, "demo", "severny_veter_demo_v1.wav", 4, "2026-07-08 11:20", None),
        (5, 2, "final_mix", "severny_veter_mix_v2.wav", 6, "2026-09-22 20:15", "Финальный микс утверждён"),
        (9, 1, "final_mix", "gorodskie_ogni_mix_v1.wav", 5, "2026-03-30 18:00", "Финальный микс"),
        (12, 1, "final_mix", "sibirsky_vinil_mix_v1.wav", 6, "2026-05-12 14:00", "Финальный микс"),
        (13, 1, "final_mix", "taiga_mix_v1.wav", 6, "2026-05-14 14:30", "Финальный микс")])

    # Расписание: ближайшие дни относительно текущей даты
    sessions = [
        (1, 1, 5, 3, dt(1, 10), dt(1, 14), "booked", 10000),
        (2, 2, 6, 2, dt(1, 15), dt(1, 19), "booked", 7200),
        (1, 3, 5, 3, dt(2, 12), dt(2, 15), "booked", 3600),
        (5, 1, 6, 4, dt(3, 11), dt(3, 16), "booked", 13500),
        (2, 2, 6, 4, dt(4, 14), dt(4, 18), "booked", 7200),
        (1, 1, 5, 2, dt(5, 10), dt(5, 13), "booked", 7500),
        (1, 1, 5, 3, dt(-7, 10), dt(-7, 14), "done", 10000),
        (2, 2, 6, 4, dt(-3, 15), dt(-3, 18), "done", 5400)]
    many("""INSERT INTO sessions (album_id, room_id, engineer_id, created_by, starts_at, ends_at, status, total_cost)
            VALUES (?,?,?,?,?,?,?,?)""", [(a, r, e, c, s, en, st, t) for a, r, e, c, s, en, st, t in sessions])
    many("INSERT INTO session_services (session_id, service_id, quantity) VALUES (?,?,?)",
         [(1, 1, 1), (4, 3, 1), (4, 2, 1), (6, 1, 1)])

    many("INSERT INTO outlets (id, name, contact_email, address, rep_user_id) VALUES (?,?,?,?,?)", [
        (1, "Музторг «Мелодия»", "melodia@shop.example", "г. Новосибирск, ул. Ленина, 12", 8),
        (2, "Магазин «Виниловый рай»", "vinyl@shop.example", "г. Новосибирск, Красный пр., 45", 9),
        (3, "Сеть «Звук и Ноты»", "zvuk@shop.example", "г. Томск, пр. Ленина, 20", None)])

    # Тираж: альбом 5 переводим в статус «В тираже» после утверждения всех треков
    con.execute("UPDATE albums SET status = 'in_print' WHERE id = 5")
    con.execute("INSERT INTO print_runs (id, album_id, medium, total_copies, status) VALUES (1, 5, 'vinyl', 500, 'printing')")
    many("INSERT INTO print_run_items (print_run_id, outlet_id, copies, delivery_status, act_number) VALUES (?,?,?,?,?)", [
        (1, 1, 200, "sent", "АПП-2026/101"), (1, 2, 150, "pending", "АПП-2026/102"),
        (1, 3, 100, "pending", None)])

    many("INSERT INTO audit_log (user_id, action, entity, entity_id, created_at) VALUES (?,?,?,?,?)", [
        (1, "Договор переведён в статус «Подписан»", "contracts", 5, "2026-04-05 12:00"),
        (5, "Загружена версия трека v3", "track_versions", 3, "2026-09-28 19:02"),
        (6, "Утверждён финальный микс", "tracks", 5, "2026-09-22 20:15"),
        (1, "Альбом отправлен в тираж", "albums", 5, "2026-09-30 10:00")])
    con.commit()
    con.close()
    return db_path


if __name__ == "__main__":
    print("БД создана:", build())
