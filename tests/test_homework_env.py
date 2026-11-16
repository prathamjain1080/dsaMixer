import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from homework import homework_env


@unittest.skipUnless(importlib.util.find_spec("dotenv"), "Install homework/requirements.txt to test the notebook loader")
class HomeworkEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.homework = self.root / "homework"
        self.homework.mkdir()
        self.location = patch.object(homework_env, "__file__", str(self.homework / "homework_env.py"))
        self.location.start()

    def tearDown(self):
        self.location.stop()
        self.temp.cleanup()

    def test_homework_values_are_isolated_from_root_and_process(self):
        (self.root / ".env").write_text("DATABASE_URL=app-database\nAPP_ONLY=root-only\n")
        (self.homework / ".env").write_text('DATABASE_URL="practice-database"\nOPTIONAL=\nUNSET\n')
        with patch.dict(os.environ, {"DATABASE_URL": "inherited-database", "APP_ONLY": "process-only"}):
            values = homework_env.load_homework_env()
            self.assertEqual(values, {"DATABASE_URL": "practice-database", "OPTIONAL": ""})
            self.assertEqual(os.environ["DATABASE_URL"], "inherited-database")
            self.assertNotIn("APP_ONLY", values)

    def test_missing_homework_file_never_falls_back_to_root(self):
        (self.root / ".env").write_text("DATABASE_URL=app-database\n")
        with self.assertRaisesRegex(FileNotFoundError, "homework/.env"):
            homework_env.load_homework_env()

    def test_interpolation_cannot_pull_in_inherited_secrets(self):
        (self.homework / ".env").write_text("VALUE=${APP_SECRET}\n")
        with patch.dict(os.environ, {"APP_SECRET": "inherited-secret"}):
            self.assertEqual(homework_env.load_homework_env()["VALUE"], "${APP_SECRET}")

    def test_reload_reads_edited_file(self):
        path = self.homework / ".env"
        path.write_text("DATABASE_URL=first\n")
        self.assertEqual(homework_env.load_homework_env()["DATABASE_URL"], "first")
        path.write_text("DATABASE_URL=second\n")
        self.assertEqual(homework_env.load_homework_env()["DATABASE_URL"], "second")


if __name__ == "__main__":
    unittest.main()
