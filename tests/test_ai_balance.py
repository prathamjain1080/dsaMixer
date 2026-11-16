import sqlite3
import unittest
from unittest.mock import patch

from dsamixer.core import config, db
from dsamixer.planning import ai_balance, planner


class BalanceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        db.init(self.conn)
        config.save(self.conn, {"start_date": "2026-11-02", "ai_template": {wd: [] for wd in config.WEEKDAYS}})
        self.clock = patch.object(planner, "today", return_value="2026-11-11")
        self.clock.start()
        self.caps = {f"2026-11-{n:02}": 120 for n in range(9, 16)}

    def tearDown(self):
        self.clock.stop()
        self.conn.close()

    def card(self, day=11, minutes=60, **fields):
        tid = planner._add(self.conn, f"2026-11-{day:02}", 2, "ai", fields.pop("title", "Homework"), minutes)
        for key, value in fields.items():
            self.conn.execute(f"UPDATE tickets SET {key}=? WHERE id=?", (value, tid))
        self.conn.commit()
        return tid

    def preview(self):
        return ai_balance.preview(self.conn, "2026-11-11", self.caps)

    def test_even_spread_includes_weekends_and_preview_is_read_only(self):
        for i in range(10):
            self.card(title=f"Step {i}", carried=i % 2, source="homework")
        before = list(self.conn.iterdump())
        result = self.preview()
        self.assertEqual(before, list(self.conn.iterdump()))
        self.assertEqual([d["after"] for d in result["days"][2:]], [120] * 5)
        self.assertTrue({"2026-11-14", "2026-11-15"} <= {m["to"] for m in result["moves"]})
        ai_balance.apply(self.conn, "2026-11-11", self.caps, result["token"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0], 10)
        self.assertEqual(self.conn.execute("SELECT SUM(carried) FROM tickets").fetchone()[0], 5)
        self.assertEqual(self.preview()["moves"], [])

    def test_fixed_work_and_under_quota_days_are_untouched(self):
        fixed = [self.card(status="doing"), self.card(status="done"), self.card(title="AI live class"),
                 self.card(minutes_spent=10), self.card(day=10), self.card(day=12, minutes=30),
                 self.card(kind="dsa"), self.card(status="skipped")]
        for i in range(6):
            self.card(title=f"Overflow {i}")
        result = self.preview()
        self.assertFalse(set(fixed) & {m["id"] for m in result["moves"]})
        self.assertTrue(all(m["to"] >= "2026-11-11" for m in result["moves"]))

    def test_closed_days_and_zero_quotas_are_not_destinations(self):
        self.conn.execute("INSERT INTO days(date,closed_at) VALUES('2026-11-12','closed')")
        self.conn.commit()
        self.caps["2026-11-14"] = 0
        for i in range(5):
            self.card(title=str(i))
        result = self.preview()
        self.assertFalse({"2026-11-12", "2026-11-14"} & {m["to"] for m in result["moves"]})

    def test_insufficient_capacity_is_reported_without_losing_cards(self):
        self.card(minutes=900)
        result = self.preview()
        self.assertTrue(any(d["over"] for d in result["days"] if d["eligible"]))
        self.assertEqual(sum(d["after"] for d in result["days"]), 900)

    def test_stale_preview_rejected_without_partial_moves(self):
        for i in range(5):
            self.card(title=str(i))
        result = self.preview()
        self.card(day=12, title="New work")
        before = list(self.conn.iterdump())
        with self.assertRaisesRegex(ValueError, "board changed"):
            ai_balance.apply(self.conn, "2026-11-11", self.caps, result["token"])
        self.assertEqual(before, list(self.conn.iterdump()))

    def test_reserves_future_classes_and_suppresses_moved_template(self):
        config.save(self.conn, {"start_date": "2026-11-02", "ai_template": {
            "wed": [{"title": "Study", "minutes": 180}],
            "sat": [{"title": "AI live class", "minutes": 120}]}})
        tid = self.card(title="Study", minutes=180)
        self.card(minutes=120, status="doing")
        self.caps["2026-11-12"] = 300
        result = self.preview()
        self.assertEqual(result["days"][5]["reserved"], 120)
        self.assertIn(tid, {m["id"] for m in result["moves"]})
        ai_balance.apply(self.conn, "2026-11-11", self.caps, result["token"])
        planner.plan_day(self.conn, "2026-11-11")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM tickets WHERE title='Study'").fetchone()[0], 1)

    def test_invalid_quota_rejected(self):
        for overrides in ({"2026-11-11": -1}, {"2026-11-11": 1441}, {"2026-11-16": 60}):
            with self.assertRaises(ValueError):
                ai_balance.preview(self.conn, "2026-11-11", overrides)

    def test_failure_rolls_back_all_moves(self):
        for i in range(5):
            self.card(title=str(i))
        result = self.preview()
        before = list(self.conn.iterdump())
        with patch.object(db, "set_setting", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                ai_balance.apply(self.conn, "2026-11-11", self.caps, result["token"])
        self.assertEqual(before, list(self.conn.iterdump()))


if __name__ == "__main__":
    unittest.main()
