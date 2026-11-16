import sqlite3
import unittest

from dsamixer.core import config, db
from dsamixer.planning import planner


class ContestCarryOverTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        db.init(self.conn)
        config.save(self.conn, {"start_date": "2026-11-02"})

    def tearDown(self):
        self.conn.close()

    def card(self, kind="contest", title="Virtual contest", day="2026-11-08", status="todo", note=None):
        tid = planner._add(self.conn, day, 1, kind, title, 90)
        self.conn.execute("UPDATE tickets SET status=?,note=? WHERE id=?", (status, note, tid))
        return tid

    def test_all_missed_contests_stay_on_their_date_and_are_skipped(self):
        for destination in ("2026-11-09", "2026-11-14"):
            for title in ("Weekly — LIVE", "Virtual contest", "Custom practice contest"):
                for status in ("todo", "doing"):
                    with self.subTest(destination=destination, title=title, status=status):
                        tid = self.card(title=title, status=status, note="Keep my note")
                        planner._carry_over(self.conn, destination, 2)
                        card = dict(self.conn.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone())
                        self.assertEqual(card["date"], "2026-11-08")
                        self.assertEqual(card["sprint_id"], 1)
                        self.assertEqual(card["carried"], 0)
                        self.assertEqual(card["status"], "skipped")
                        self.assertEqual(card["note"], "Keep my note")

    def test_finished_current_and_future_contests_are_untouched(self):
        ids = [self.card(status="done"), self.card(status="skipped"),
               self.card(day="2026-11-09"), self.card(day="2026-11-15")]
        before = [dict(self.conn.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()) for tid in ids]
        planner._carry_over(self.conn, "2026-11-09", 2)
        after = [dict(self.conn.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()) for tid in ids]
        self.assertEqual(before, after)

    def test_other_work_still_carries_and_missed_contest_gets_note(self):
        contest = self.card()
        work = [self.card(kind=k) for k in ("ai", "upsolve", "dsa")]
        planner._carry_over(self.conn, "2026-11-09", 2)
        self.assertEqual(self.conn.execute("SELECT note FROM tickets WHERE id=?", (contest,)).fetchone()[0], "missed")
        for tid in work:
            card = self.conn.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()
            self.assertEqual(card["date"], "2026-11-09")
            self.assertEqual(card["carried"], 1)


if __name__ == "__main__":
    unittest.main()
