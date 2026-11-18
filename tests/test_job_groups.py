"""Section job runs keep their order and report partial failures."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from musicmind_ui import jobs
from musicmind_ui.musicmind_ui import JOB_GROUPS


class JobGroupTests(unittest.TestCase):
    def test_section_buttons_cover_every_listed_job(self):
        for label, _, entries in JOB_GROUPS:
            self.assertEqual(jobs.GROUP_COMMANDS[f"group_{label.lower()}"],
                             tuple(name for name, _, _ in entries))

    def test_group_continues_after_a_failed_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (patch.object(jobs, "JOB_DIR", Path(temp_dir)),
                  patch.object(jobs, "group_tasks", return_value=("gaps", "fingerprint", "copyforward")),
                  patch.object(jobs, "_run_one", side_effect=[0, 1, 0]) as run_one,
                  patch.object(jobs.time, "sleep")):
                self.assertEqual(jobs.run("group_analysis", []), 1)
                self.assertEqual(
                    [call.args[0] for call in run_one.call_args_list],
                    ["gaps", "fingerprint", "copyforward"],
                )
                self.assertEqual(jobs.status("group_analysis")["exit_code"], 1)

    def test_group_rejects_a_running_member(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (patch.object(jobs, "JOB_DIR", Path(temp_dir)),
                  patch.object(jobs, "group_tasks", return_value=("gaps", "fingerprint")),
                  patch.object(jobs, "status", side_effect=lambda name: {"running": name == "gaps"})):
                with self.assertRaisesRegex(ValueError, "gaps is running"):
                    jobs.start("group_analysis")

    def test_member_rejects_a_running_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (patch.object(jobs, "JOB_DIR", Path(temp_dir)),
                  patch.object(jobs, "group_tasks", return_value=("gaps", "fingerprint")),
                  patch.object(jobs, "status", side_effect=lambda name: {"running": name == "group_analysis"})):
                with self.assertRaisesRegex(ValueError, "group_analysis is running"):
                    jobs.start("gaps")


if __name__ == "__main__":
    unittest.main()
