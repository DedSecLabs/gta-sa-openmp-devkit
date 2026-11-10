"""Installs the skill into an empty project the way a user would (a plain copy) and drives it from there.

Nothing from this repository except the skill folder is available to the installed copy.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers


class CleanProjectInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.project = base / "my-gamemode"
        self.skill = self.project / ".agents" / "skills" / "gta-sa-openmp-devkit"
        shutil.copytree(helpers.SKILL, self.skill, ignore=shutil.ignore_patterns("__pycache__"))
        self.game = helpers.make_install(base / "elsewhere")
        helpers.write_ipl(self.game, "a.ipl", "enex\n%s\nend\n" % helpers.ENEX_OK)
        self.before = self.snapshot()

    def tearDown(self):
        self.tmp.cleanup()

    def snapshot(self):
        return sorted(str(p.relative_to(self.skill)) for p in self.skill.rglob("*"))

    def tool(self, name, *args, expect=0):
        environment = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        done = subprocess.run([sys.executable, str(self.skill / "scripts" / name), *map(str, args)],
                              cwd=self.project, env=environment, capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, expect, "%s: %s%s" % (name, done.stdout, done.stderr))
        return done

    def test_documented_first_run(self):
        # 1. No profile yet: the skill still answers and says so.
        first = json.loads(self.tool("capabilities.py").stdout)
        self.assertIsNone(first["profile"])
        self.assertIn("project-profile.template.json", first["profileHint"])

        # 2. The template becomes the project's profile.
        profile = json.loads((self.skill / "assets" / "project-profile.template.json").read_text(encoding="utf-8"))
        profile["game"]["installDir"] = str(self.game)
        profile["target"]["includeDirs"] = ["include"]
        (self.project / "include").mkdir()
        (self.project / "include" / "a.inc").write_text("native SetPlayerInterior(playerid, interiorid);\n")
        (self.project / "gta-sa-openmp-devkit.json").write_text(json.dumps(profile), encoding="utf-8")
        flows = {w["workflow"]: w["available"] for w in json.loads(self.tool("capabilities.py").stdout)["workflows"]}
        self.assertTrue(flows["identify-build"] and flows["data-layer-export"] and flows["pawn-declaration-check"])

        # 3. Each documented workflow runs from the project folder.
        identity = json.loads(self.tool("identify_build.py", self.game / "gta_sa.exe").stdout)
        self.assertEqual(identity["identity"]["match"], "none")
        self.tool("export_manifest.py", "--game-dir", self.game, "--output", "research/manifest.json")
        self.tool("export_ipl_records.py", "--game-dir", self.game, "--section", "enex", "--output", "research/enex.json")
        records = json.loads((self.project / "research" / "enex.json").read_text(encoding="utf-8"))
        self.assertEqual(records["records"][0]["name"], "DOORA")
        declared = json.loads(self.tool("check_native.py", "SetPlayerInterior").stdout)
        self.assertTrue(declared["names"][0]["declared"])
        self.tool("check_native.py", "MadeUpNative", expect=1)
        self.tool("validate_findings.py", self.skill / "assets" / "findings.example.json")
        self.tool("validate_findings.py", self.skill / "assets" / "findings.example.json",
                  "--verify-files", self.game, expect=3)

        # 4. Refusals are one-line errors, not tracebacks, and nothing lands in the installation.
        refused = self.tool("export_manifest.py", "--game-dir", self.game, "--output", self.game / "m.json", expect=2)
        self.assertTrue(refused.stderr.startswith("error: "))
        self.assertNotIn("Traceback", refused.stderr)
        self.assertFalse((self.game / "m.json").exists())
        missing = self.tool("identify_build.py", self.project / "nope.exe", expect=2)
        self.assertNotIn("Traceback", missing.stderr)
        blocked = self.tool("export_manifest.py", "--game-dir", self.game, "--output", "include/a.inc/m.json", expect=2)
        self.assertTrue(blocked.stderr.startswith("error: "), blocked.stderr)

        # 5. Using the skill leaves the installed copy exactly as installed.
        self.assertEqual(self.snapshot(), self.before)

    def test_documented_commands_resolve_from_the_consuming_project(self):
        # Regression: SKILL.md told users to run 'python scripts/...' from their project, where it does not exist.
        import re
        documents = [self.skill / "SKILL.md", *sorted((self.skill / "references").glob("*.md")),
                     helpers.ROOT / "README.md"]
        installed = self.skill.relative_to(self.project).as_posix()
        commands = []
        for document in documents:
            for match in re.finditer(r"python (\S*scripts/[a-z_]+\.py)([^\n`]*)", document.read_text(encoding="utf-8")):
                commands.append((document.name, match.group(1), match.group(2)))
        self.assertGreaterEqual(len(commands), 12)
        for document, script, arguments in commands:
            self.assertTrue(script.startswith("<skill>/scripts/"), "%s: %s is not addressed through <skill>" % (document, script))
            relative = script.replace("<skill>", installed)
            self.assertTrue((self.project / relative).is_file(), "%s: %s does not exist in a project" % (document, relative))
            environment = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
            usage = subprocess.run([sys.executable, relative, "--help"], cwd=self.project, env=environment,
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(usage.returncode, 0, relative)
            for option in re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]+)", arguments):
                self.assertIn(option, usage.stdout, "%s: %s has no option %s" % (document, script, option))
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("replace `<skill>` with", skill_text)

    def test_every_tool_explains_itself(self):
        for script in sorted(p.name for p in (self.skill / "scripts").glob("*.py") if not p.name.startswith("_")):
            self.assertIn("usage:", self.tool(script, "--help").stdout)
        self.assertEqual(self.snapshot(), self.before)


if __name__ == "__main__":
    unittest.main()
