"""Every script subcommand a skill's docs tell the agent to run must exist.

SKILL.md is the spec the agent executes. A subcommand that is documented
but missing fails at run time, and where the docs add `2>/dev/null` it
fails without a trace (this happened: ideation called podcast's
`ledger.py known-issues`, which never existed, and so read no podcast
findings at all).
"""
import re
import subprocess
import sys
import unittest

from _loader import REPO_ROOT

PLUGINS = REPO_ROOT / "plugins"
# podcast/resolve.py takes a URL, not a subcommand.
SCRIPTS_WITH_SUBCOMMANDS = {
    ("podcast", "ledger"), ("review-scout", "ledger"), ("ideation", "ledger"), ("review-scout", "resolve"),
}
# `SKILL_DIR/ledger.py sub`, `SKILL_DIR/../podcast/ledger.py sub`, or a backticked `ledger.py sub`.
INVOCATION = re.compile(r"(?:SKILL_DIR/(?:\.\./([\w-]+)/)?|`)(ledger|resolve)\.py[ \t]+([a-z][a-z-]+)")


def documented_invocations():
    found = set()
    for doc in sorted(PLUGINS.glob("*/*.md")):
        own_plugin = doc.parent.name
        for sibling, script, sub in INVOCATION.findall(doc.read_text()):
            plugin = sibling or own_plugin
            if (plugin, script) in SCRIPTS_WITH_SUBCOMMANDS:
                found.add((doc.relative_to(REPO_ROOT).as_posix(), plugin, script, sub))
    return sorted(found)


class DocumentedCommandsExist(unittest.TestCase):
    def test_docs_reference_some_commands(self):
        self.assertGreater(len(documented_invocations()), 20)

    def test_every_documented_subcommand_is_accepted(self):
        missing = []
        for doc, plugin, script, sub in documented_invocations():
            result = subprocess.run(
                [sys.executable, str(PLUGINS / plugin / f"{script}.py"), sub, "--help"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                missing.append(f"{doc}: {plugin}/{script}.py {sub}")
        self.assertEqual(missing, [], "documented subcommands the script rejects")


if __name__ == "__main__":
    unittest.main()
