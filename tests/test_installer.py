"""bin/install.js end to end, into a scratch HOME."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _loader import REPO_ROOT

SKILLS = ["ideation", "podcast", "research-suite", "review-scout", "signal-outreach", "signal-report"]


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Installer(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def install(self):
        env = {**os.environ, "HOME": str(self.home), "USERPROFILE": str(self.home)}
        result = subprocess.run(["node", str(REPO_ROOT / "bin" / "install.js")], capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_fresh_machine_gets_all_six_skills_under_claude_only(self):
        self.install()
        installed = self.home / ".claude" / "skills"
        self.assertEqual(sorted(p.name for p in installed.iterdir()), SKILLS)
        for name in SKILLS:
            self.assertTrue((installed / name / "SKILL.md").is_file(), name)
            self.assertFalse((installed / name / ".claude-plugin").exists(), name)
        self.assertTrue((installed / "signal-outreach" / "scripts" / "generate_outreach.py").is_file())
        self.assertFalse((self.home / ".agents").exists())
        self.assertFalse((self.home / ".codex").exists())

    def test_codex_skills_go_to_the_agents_folder(self):
        (self.home / ".codex").mkdir()
        self.install()
        self.assertEqual(sorted(p.name for p in (self.home / ".agents" / "skills").iterdir()), SKILLS)
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.home / ".codex" / "skills").exists())

    def test_reinstall_keeps_the_users_sources_and_config_but_updates_scripts(self):
        self.install()
        podcast = self.home / ".claude" / "skills" / "podcast"
        (podcast / "sources.md").write_text("my shows")
        (podcast / "config.json").write_text('{"transcription_method": "local"}')
        (podcast / "ledger.py").write_text("stale")
        self.install()
        self.assertEqual((podcast / "sources.md").read_text(), "my shows")
        self.assertEqual((podcast / "config.json").read_text(), '{"transcription_method": "local"}')
        self.assertEqual((podcast / "ledger.py").read_text(), (REPO_ROOT / "plugins" / "podcast" / "ledger.py").read_text())


if __name__ == "__main__":
    unittest.main()
