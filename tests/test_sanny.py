import json
import os
import tempfile
import unittest
from pathlib import Path

import helpers
import sanny_decompile
from _common import DevkitError

ORIGINAL_INI = b"[general]\r\nlang=en\r\n[sa_sbl]\r\nGamePath=C:\\Old\r\nfoo=1\r\n[vc]\r\nGamePath=C:\\VC\r\n"


class SannyWrapper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.game = helpers.make_install(base)
        self.sanny = base / "Sanny"
        self.work = base / "work"
        self.work.mkdir()
        self.scm = self.work / "main.scm"
        self.scm.write_bytes(b"private-copy")
        self.out = self.work / "out" / "main.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, behaviour="ok", ini=ORIGINAL_INI, **kwargs):
        helpers.make_stub_sanny(self.sanny, behaviour)
        if ini is not None:
            (self.sanny / "data").mkdir(exist_ok=True)
            (self.sanny / "data" / "settings.ini").write_bytes(ini)
        return sanny_decompile.decompile(self.sanny, self.game, kwargs.pop("scm", self.scm),
                                         kwargs.pop("output", self.out), launcher=helpers.LAUNCHER, **kwargs)

    def recorded(self):
        return json.loads((self.sanny / "call.json").read_text())

    def test_game_identifier_is_not_the_installation_path(self):
        # Regression: the earlier wrapper overwrote the game identifier with the installation directory.
        self.call()
        argv = self.recorded()["argv"]
        self.assertEqual(argv[argv.index("--game") + 1], "sa")
        self.assertNotIn(str(self.game), argv[argv.index("--game") + 1])

    def test_settings_are_patched_for_the_run_and_restored_exactly(self):
        # Regression: the earlier wrapper left its GamePath edit in the user's settings.ini.
        result = self.call()
        seen = self.recorded()["settings"]
        self.assertIn("[sa_sbl]\r\nGamePath=%s\r\nfoo=1" % self.game, seen)
        self.assertIn("[vc]\r\nGamePath=C:\\VC", seen)
        self.assertEqual((self.sanny / "data" / "settings.ini").read_bytes(), ORIGINAL_INI)
        self.assertTrue(result["settingsRestored"])
        self.assertEqual(result["outputLines"], 2)

    def test_settings_restored_after_failure_and_timeout(self):
        with self.assertRaisesRegex(DevkitError, "exit code 3"):
            self.call("fail")
        self.assertEqual((self.sanny / "data" / "settings.ini").read_bytes(), ORIGINAL_INI)
        with self.assertRaisesRegex(DevkitError, "did not finish"):
            self.call("hang", timeout=0.5)
        self.assertEqual((self.sanny / "data" / "settings.ini").read_bytes(), ORIGINAL_INI)

    def test_settings_created_for_the_run_are_removed(self):
        self.call(ini=None)
        self.assertIn("[sa_sbl]\r\nGamePath=", self.recorded()["settings"])
        self.assertFalse((self.sanny / "data").exists())

    def test_missing_output_is_an_error(self):
        with self.assertRaisesRegex(DevkitError, "no decompiled output"):
            self.call("silent")

    def test_refuses_installation_paths_and_wrong_hash(self):
        with self.assertRaisesRegex(DevkitError, "private copy"):
            self.call(scm=self.game / "data" / "script" / "main.scm")
        with self.assertRaisesRegex(DevkitError, "outside the game installation"):
            self.call(output=self.game / "out.txt")
        with self.assertRaisesRegex(DevkitError, "hash differs"):
            self.call(expected_sha256="0" * 64)
        with self.assertRaisesRegex(DevkitError, "plain identifiers"):
            self.call(game=str(self.game))
        self.assertEqual((self.sanny / "data" / "settings.ini").read_bytes(), ORIGINAL_INI)

    def test_output_that_is_the_input_is_refused_before_anything_is_deleted(self):
        # Regression: the output is deleted before the run, so output == input destroyed the private copy.
        content = self.scm.read_bytes()
        aliases = [self.scm, self.work / "sub" / ".." / "main.scm"]
        link = self.work / "alias.scm"
        try:
            os.link(self.scm, link)
            aliases.append(link)
        except (OSError, NotImplementedError, AttributeError):
            pass
        if os.path.normcase("A") == os.path.normcase("a"):
            aliases.append(self.work / "MAIN.SCM")
        (self.work / "sub").mkdir()
        for alias in aliases:
            with self.assertRaisesRegex(DevkitError, "output path is the input file"):
                self.call(output=alias)
            self.assertEqual(self.scm.read_bytes(), content, alias)
        self.assertFalse((self.sanny / "call.json").exists())

    def test_section_name_is_matched_like_an_ini_file(self):
        patched = sanny_decompile.patched_settings(b"[ SA_SBL ]\r\ngamepath = C:\\Old\r\n", "sa_sbl", "D:\\G").decode()
        self.assertEqual(patched, "[ SA_SBL ]\r\nGamePath=D:\\G\r\n")

    def test_utf16_settings_are_refused_untouched(self):
        content = b"\xff\xfe" + "[sa_sbl]\r\n".encode("utf-16-le")
        with self.assertRaisesRegex(DevkitError, "UTF-16"):
            self.call(ini=content)
        self.assertEqual((self.sanny / "data" / "settings.ini").read_bytes(), content)
        self.assertFalse((self.sanny / "call.json").exists())

    def test_interrupted_run_is_repaired_before_the_next_one(self):
        # A run killed mid-way leaves patched settings plus a backup; the next run must restore the original.
        self.call()
        data = self.sanny / "data"
        (data / "settings.ini.devkit-backup").write_bytes(ORIGINAL_INI)
        (data / "settings.ini").write_bytes(b"[sa_sbl]\r\nGamePath=LEFTOVER\r\n")
        self.call(ini=None)
        self.assertEqual((data / "settings.ini").read_bytes(), ORIGINAL_INI)
        self.assertFalse((data / "settings.ini.devkit-backup").exists())
        self.assertNotIn("LEFTOVER", self.recorded()["settings"])

    def test_section_added_when_missing(self):
        patched = sanny_decompile.patched_settings(b"[general]\r\nlang=en\r\n", "sa_sbl", "D:\\G").decode()
        self.assertEqual(patched, "[general]\r\nlang=en\r\n[sa_sbl]\r\nGamePath=D:\\G\r\n")


if __name__ == "__main__":
    unittest.main()
