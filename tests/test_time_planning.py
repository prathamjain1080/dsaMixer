import sqlite3
import unittest

from dsamixer.core import config, db
from dsamixer.planning import planner


class TimePlanningTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        db.init(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_existing_config_defaults_off_and_preserves_saved_values(self):
        config.save(self.conn, {"dsa_minutes": {"mon": 180}, "est_minutes": {"Hard": 75}})
        loaded = config.load(self.conn)
        self.assertFalse(loaded["time_planning_enabled"])
        for enabled in (True, False, True):
            config.save(self.conn, {**loaded, "time_planning_enabled": enabled})
            saved = config.load(self.conn)
            self.assertIs(saved["time_planning_enabled"], enabled)
            self.assertEqual(saved["dsa_minutes"]["mon"], 180)
            self.assertEqual(saved["est_minutes"]["Hard"], 75)

    def test_requires_boolean(self):
        for valid in (True, False):
            self.assertEqual(config.validate({"time_planning_enabled": valid}), [])
        for invalid in (1, "false", None):
            self.assertTrue(config.validate({"time_planning_enabled": invalid}))

    def test_display_toggle_does_not_change_week_plan(self):
        plans = []
        for enabled in (False, True):
            with sqlite3.connect(":memory:") as conn:
                conn.row_factory = sqlite3.Row
                db.init(conn)
                config.save(conn, {"start_date": "2026-11-16", "time_planning_enabled": enabled})
                planner.plan_day(conn, "2026-11-16")
                plans.append([tuple(r) for r in conn.execute(
                    "SELECT date,kind,title,est_minutes FROM tickets ORDER BY id"
                )])
        self.assertTrue(plans[0])
        self.assertEqual(plans[0], plans[1])


if __name__ == "__main__":
    unittest.main()
