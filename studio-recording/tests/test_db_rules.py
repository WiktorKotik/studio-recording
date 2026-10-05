"""Проверка бизнес-правил, реализованных в БД. Запуск: python -m unittest -v"""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import init_db  # noqa: E402


class DbRulesTest(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "test.db")
        init_db.build(self.path)
        self.con = sqlite3.connect(self.path)
        self.con.execute("PRAGMA foreign_keys = ON")

    def tearDown(self):
        self.con.close()

    def add_session(self, album, room, start, end):
        return self.con.execute(
            "INSERT INTO sessions (album_id, room_id, created_by, starts_at, ends_at) VALUES (?,?,?,?,?)",
            (album, room, 1, start, end))

    def test_booking_blocked_without_signed_contract(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, "Договор не подписан"):
            self.add_session(3, 1, "2030-01-10 10:00", "2030-01-10 12:00")

    def test_booking_conflict_in_same_room(self):
        self.add_session(1, 1, "2030-01-10 10:00", "2030-01-10 14:00")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "Слот занят"):
            self.add_session(2, 1, "2030-01-10 13:00", "2030-01-10 16:00")

    def test_booking_in_other_room_allowed(self):
        self.add_session(1, 1, "2030-01-10 10:00", "2030-01-10 14:00")
        self.add_session(2, 2, "2030-01-10 13:00", "2030-01-10 16:00")

    def test_print_requires_all_tracks_approved(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, "Не все треки утверждены"):
            self.con.execute("UPDATE albums SET status = 'in_print' WHERE id = 1")

    def test_print_copies_sum_limit(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, "Сумма копий"):
            self.con.execute(
                "INSERT INTO print_run_items (print_run_id, outlet_id, copies) VALUES (1, 3, 99999)")

    def test_track_version_number_unique(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("""INSERT INTO track_versions (track_id, version_no, kind, file_name, uploaded_by)
                                VALUES (1, 2, 'draft', 'dup.wav', 5)""")

    def test_invalid_status_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("UPDATE tracks SET status = 'unknown' WHERE id = 1")


if __name__ == "__main__":
    unittest.main()
