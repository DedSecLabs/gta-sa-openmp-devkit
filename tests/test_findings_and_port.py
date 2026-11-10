import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

import helpers
import capabilities
import check_native
import validate_findings
from _common import DevkitError, sha256_bytes

EXE = "a" * 64
GOOD = {
    "id": "door-interior", "claim": "The record has interior 3.", "layer": "data",
    "evidenceClass": "original-observed", "build": {"label": "Fixture", "confidence": "corroborated", "exeSha256": EXE},
    "sources": [{"type": "file", "path": "data/maps/area/a.ipl", "sha256": "b" * 64, "line": 5}],
}


class Findings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_on(self, *findings, root=None):
        path = self.base / "findings.json"
        path.write_text(json.dumps({"schemaVersion": 1, "findings": list(findings)}))
        return validate_findings.validate([path], root)

    def errors_for(self, **changes):
        finding = copy.deepcopy(GOOD)
        finding.update(changes)
        return " | ".join(self.run_on(finding)["errors"])

    def test_valid_finding_and_shipped_example(self):
        self.assertTrue(self.run_on(GOOD)["ok"])
        example = validate_findings.validate([helpers.SKILL / "assets" / "findings.example.json"])
        self.assertEqual(example["errors"], [])
        self.assertEqual(example["findings"], 3)

    def test_each_evidence_class_needs_a_source_that_can_carry_it(self):
        self.assertIn("needs a source of type file or probe", self.errors_for(sources=[]))
        self.assertIn("needs a source of type executable", self.errors_for(evidenceClass="exe-byte"))
        self.assertIn("needs a source of type repository", self.errors_for(evidenceClass="source-derived"))
        self.assertIn("needs a source of type documentation", self.errors_for(evidenceClass="documented"))
        self.assertIn("must say what was not examined", self.errors_for(evidenceClass="inferred", sources=[]))

    def test_executable_claims_are_tied_to_one_build_and_one_address_kind(self):
        source = {"type": "executable", "sha256": EXE, "addressKind": "va", "address": "0x401000"}
        self.assertEqual(self.errors_for(evidenceClass="exe-byte", layer="engine", sources=[source]), "")
        self.assertIn("needs build.exeSha256", self.errors_for(
            evidenceClass="exe-byte", sources=[source], build={"label": "x", "confidence": "documented-only"}))
        self.assertIn("never leave the kind implicit", self.errors_for(
            evidenceClass="exe-byte", sources=[dict(source, addressKind="address")]))
        self.assertIn("differs from build.exeSha256", self.errors_for(
            evidenceClass="exe-byte", sources=[dict(source, sha256="c" * 64)]))
        self.assertIn("0x prefix", self.errors_for(evidenceClass="exe-byte", sources=[dict(source, address="401000")]))

    def test_unpinned_or_unverified_work_is_rejected(self):
        repo = {"type": "repository", "url": "https://example.invalid/r", "commit": "master", "path": "a.cpp"}
        self.assertIn("pinned commit hash", self.errors_for(evidenceClass="source-derived", sources=[repo]))
        self.assertIn("cannot be marked implemented", self.errors_for(
            evidenceClass="inferred", sources=[], notExamined="nothing read", implementation={"status": "implemented"}))
        self.assertIn("confidence", self.errors_for(build={"label": "x", "confidence": "sure"}))
        self.assertIn("layer must be", self.errors_for(layer="vibes"))

    def test_duplicates_and_unknown_conflicts(self):
        result = self.run_on(GOOD, dict(GOOD, conflictsWith=["missing-id"]))
        joined = " | ".join(result["errors"])
        self.assertIn("duplicate id", joined)
        self.assertIn("unknown id 'missing-id'", joined)

    def test_changed_source_files_make_a_finding_stale(self):
        game = helpers.make_install(self.base)
        path = helpers.write_ipl(game, "a.ipl", "enex\nend\n")
        finding = copy.deepcopy(GOOD)
        finding["sources"][0]["sha256"] = sha256_bytes(path.read_bytes())
        fresh = self.run_on(finding, root=game)
        self.assertTrue(fresh["ok"])
        self.assertEqual((fresh["verification"]["verified"], fresh["verification"]["complete"]), (1, True))
        path.write_bytes(b"modded")
        result = self.run_on(finding, root=game)
        self.assertFalse(result["ok"])
        self.assertTrue(result["structureValid"])
        self.assertIn("no longer matches", result["verification"]["stale"][0])

    def test_missing_source_files_are_not_a_pass(self):
        # Regression: a requested verification that could not find its files used to report success.
        game = helpers.make_install(self.base)
        result = self.run_on(GOOD, root=game)
        self.assertTrue(result["structureValid"])
        self.assertFalse(result["verification"]["complete"])
        self.assertFalse(result["ok"])
        self.assertIn("not present", result["verification"]["missing"][0])
        unrequested = self.run_on(GOOD)
        self.assertEqual((unrequested["ok"], unrequested["verification"]["requested"],
                          unrequested["verification"]["complete"]), (True, False, False))
        with self.assertRaisesRegex(DevkitError, "not a folder"):
            self.run_on(GOOD, root=self.base / "nowhere")

    def test_wrong_types_are_reported_never_crash(self):
        # Regression: {"implementation": "planned"} on an inferred finding raised AttributeError.
        inferred = dict(GOOD, evidenceClass="inferred", sources=[], notExamined="nothing", implementation="planned")
        self.assertIn("implementation must be an object", " | ".join(self.run_on(inferred)["errors"]))
        junk = [None, "text", 7, 1.5, True, [], ["x"], {}, {"status": 3}, [{"type": 5}], [None], {"type": "file"}]
        for field in list(GOOD) + ["implementation", "conflictsWith", "notExamined", "multiplayerNotes"]:
            for value in junk:
                for evidence in ("original-observed", "exe-byte", "inferred"):
                    finding = dict(copy.deepcopy(GOOD), evidenceClass=evidence)
                    finding[field] = value
                    result = self.run_on(finding, root=self.base)
                    self.assertIsInstance(result["errors"], list)
        for document in (None, [], "x", {"findings": "x"}, {"schemaVersion": 1, "findings": [None, 3, "x", []]}):
            path = self.base / "odd.json"
            path.write_text(json.dumps(document))
            self.assertFalse(validate_findings.validate([path])["ok"])

    def test_file_sources_cannot_point_outside_the_installation(self):
        game = helpers.make_install(self.base)
        (self.base / "secret.txt").write_bytes(b"outside")
        for escape in ("../secret.txt", str(self.base / "secret.txt"), "data/../../secret.txt"):
            finding = copy.deepcopy(GOOD)
            finding["sources"][0].update(path=escape, sha256=sha256_bytes(b"outside"))
            result = self.run_on(finding, root=game)
            self.assertIn("installation-relative", " | ".join(result["errors"]), escape)
            self.assertFalse(result["ok"])

    def test_schema_version_is_checked(self):
        path = self.base / "old.json"
        path.write_text(json.dumps({"schemaVersion": 2, "findings": [GOOD]}))
        self.assertIn("schemaVersion must be 1", validate_findings.validate([path])["errors"][0])


class PawnDeclarations(unittest.TestCase):
    def test_declared_and_missing_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            include = Path(tmp) / "include"
            include.mkdir()
            (include / "a_players.inc").write_text(
                "native SetPlayerInterior(playerid, interiorid);\n"
                "native bool:IsPlayerNear(playerid);\n"
                "forward OnPlayerEnterCheckpoint(playerid);\n"
                "#define MAX_THINGS (50)\n"
                "// SetPlayerGravityLocal(playerid) was never a native\n"
                "const Float:DEFAULT = WeatherSpeed + 1.0;\n"
                "native Other(WeatherSpeed);\n"
                "/* native InBlockComment(playerid);\n"
                "native AlsoInBlockComment(playerid); */ native AfterComment(playerid);\n"
                "native HasString(const s[] = \"/* not a comment\"); // native InLineComment();\n"
                "#if 0\n"
                "native Disabled(playerid);\n"
                "#else\n"
                "native InElseOfZero(playerid);\n"
                "#endif\n"
                "#if defined SOME_FLAG\n"
                "native Conditional(playerid);\n"
                "  #if 0\n"
                "native NestedDisabled(playerid);\n"
                "  #endif\n"
                "#endif\n"
                "#if defined _guard_included\n"
                "  #endinput\n"
                "#endif\n"
                "#define _guard_included\n"
                "native AfterGuard(playerid);\n"
                "#endinput\n"
                "native AfterEndInput(playerid);\n"
                "native SetPlayerInteriorEx(playerid);\n")
            report = check_native.find_declarations(
                ["SetPlayerInterior", "IsPlayerNear", "OnPlayerEnterCheckpoint", "MAX_THINGS", "SetPlayerGravityLocal",
                 "WeatherSpeed", "InBlockComment", "AlsoInBlockComment", "AfterComment", "HasString",
                 "InLineComment", "Disabled", "InElseOfZero", "Conditional", "NestedDisabled", "AfterGuard",
                 "AfterEndInput"],
                [include])
            status = {item["name"]: item["status"] for item in report["names"]}
            self.assertEqual(status, {
                "SetPlayerInterior": "declared", "IsPlayerNear": "declared", "OnPlayerEnterCheckpoint": "declared",
                "MAX_THINGS": "declared", "SetPlayerGravityLocal": "not-found", "WeatherSpeed": "not-found",
                # Regression: comments and '#if 0' used to count as declarations.
                "InBlockComment": "not-found", "AlsoInBlockComment": "not-found", "InLineComment": "not-found",
                "AfterComment": "declared", "HasString": "declared",
                "Disabled": "disabled", "InElseOfZero": "declared", "NestedDisabled": "disabled",
                "Conditional": "conditional", "AfterGuard": "conditional", "AfterEndInput": "disabled"})
            by_name = {item["name"]: item for item in report["names"]}
            self.assertEqual([i["name"] for i in report["names"] if i["declared"]],
                             [n for n, s in status.items() if s == "declared"])
            self.assertEqual(by_name["Conditional"]["declarations"][0]["conditions"], ["defined SOME_FLAG"])
            self.assertEqual((by_name["Disabled"]["textualMatches"], by_name["Disabled"]["declared"]), (1, False))
            first = report["names"][0]["declarations"]
            self.assertEqual((len(first), first[0]["line"]), (1, 1))
            with self.assertRaisesRegex(DevkitError, "not found"):
                check_native.find_declarations(["X"], [Path(tmp) / "nope"])


class PawnUncertainty(unittest.TestCase):
    """Regressions: uncertainty must survive branch chains and a conditional #endinput."""

    def status(self, source, *names):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "x.inc").write_text(source)
            report = check_native.find_declarations(list(names), [tmp])
            return {i["name"]: i["status"] for i in report["names"]}, report

    def test_branch_after_an_unknown_branch_stays_conditional(self):
        status, report = self.status(
            "#if defined FEATURE\n#elseif 1\nnative MaybeAvailable();\n#endif\n"
            "#if defined A\n#elseif defined B\n#else\nnative InElse();\n#endif\n"
            "#if 0\n#elseif 1\nnative Certain();\n#else\nnative Never();\n#endif\n"
            "#if 0\n#elseif defined C\nnative MaybeC();\n#else\nnative ElseOfC();\n#endif\n"
            "#if 1\n#elseif defined D\nnative AfterTaken();\n#endif\n"
            "#if defined E\n#elseif 0\nnative ZeroBranch();\n#else\nnative ElseOfE();\n#endif\n",
            "MaybeAvailable", "InElse", "Certain", "Never", "MaybeC", "ElseOfC", "AfterTaken", "ZeroBranch", "ElseOfE")
        self.assertEqual(status, {"MaybeAvailable": "conditional", "InElse": "conditional", "Certain": "declared",
                                  "Never": "disabled", "MaybeC": "conditional", "ElseOfC": "conditional",
                                  "AfterTaken": "disabled", "ZeroBranch": "disabled", "ElseOfE": "conditional"})
        maybe = next(i for i in report["names"] if i["name"] == "MaybeAvailable")
        self.assertIn("defined FEATURE", maybe["declarations"][0]["conditions"][0])

    def test_conditional_endinput_leaves_the_rest_conditional(self):
        status, report = self.status(
            "native Before();\n#if defined STOP_HERE\n#endinput\n#endif\nnative AfterMaybeEnd();\n"
            "#define STOP_HERE_TOO\nnative StillMaybe();\n",
            "Before", "AfterMaybeEnd", "StillMaybe")
        self.assertEqual(status, {"Before": "declared", "AfterMaybeEnd": "conditional", "StillMaybe": "conditional"})
        after = next(i for i in report["names"] if i["name"] == "AfterMaybeEnd")
        self.assertIn("defined STOP_HERE", after["declarations"][0]["conditions"][0])
        status, _ = self.status("#if defined STOP_HERE\n#endinput\n#endif\nnative Maybe();\n#endinput\nnative Gone();\n",
                                "Maybe", "Gone")
        self.assertEqual(status, {"Maybe": "conditional", "Gone": "disabled"})

    def test_include_guards_do_not_erase_conditional_endinput(self):
        guard = "#if defined _INC_x\n\t#endinput\n#endif\n#define _INC_x\nnative Guarded();\n"
        status, report = self.status(guard, "Guarded")
        self.assertEqual(status["Guarded"], "conditional")
        for variant in (
                "#if defined _INC_x\n#endinput\n#endif\n#define _INC_other\nnative Guarded();\n",   # other symbol
                "#if !defined _INC_x\n#endinput\n#endif\n#define _INC_x\nnative Guarded();\n",      # negated
                "#if defined A\n#if defined _INC_x\n#endinput\n#endif\n#endif\n#define _INC_x\nnative Guarded();\n",
                "#if defined _INC_x && defined B\n#endinput\n#endif\n#define _INC_x\nnative Guarded();\n",
                "#if defined _INC_x\n#endinput\n#endif\n#if defined B\n#define _INC_x\n#endif\nnative Guarded();\n"):
            status, report = self.status(variant, "Guarded")
            self.assertEqual(status["Guarded"], "conditional", variant)
        status, _ = self.status("#if defined _INC_x\n#endinput\n#endif\n#define _INC_x\n#endinput\nnative Late();\n", "Late")
        self.assertEqual(status["Late"], "disabled")

    def test_late_define_cannot_reopen_a_possibly_ended_file(self):
        status, _ = self.status(
            "#if defined STOP\n#endinput\n#endif\nnative BeforeDefine();\n"
            "#if defined OTHER\n#endinput\n#endif\n#define STOP\nnative AfterDefine();\n",
            "BeforeDefine", "AfterDefine")
        self.assertEqual(status, {"BeforeDefine": "conditional", "AfterDefine": "conditional"})

    def test_true_fallback_exhausts_an_unknown_branch_chain(self):
        status, _ = self.status(
            "#if defined FEATURE\nnative First();\n#elseif 1\nnative Fallback();\n"
            "#else\nnative Impossible();\n#endif\nnative Outside();\n",
            "First", "Fallback", "Impossible", "Outside")
        self.assertEqual(status, {"First": "conditional", "Fallback": "conditional",
                                  "Impossible": "disabled", "Outside": "declared"})


class PythonVersion(unittest.TestCase):
    def test_versions_below_the_minimum_are_refused_with_one_line(self):
        import contextlib
        import io
        from unittest import mock
        import _common
        self.assertTrue(_common.python_supported((3, 12, 0)))
        self.assertTrue(_common.python_supported((4, 0)))
        self.assertFalse(_common.python_supported((3, 11, 9)))
        self.assertTrue(capabilities.report()["pythonSupported"])
        stderr = io.StringIO()
        with mock.patch.object(_common, "python_supported", return_value=False), \
                contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as stopped:
            _common.run(lambda: self.fail("the tool must not start on an unsupported Python"))
        self.assertEqual(stopped.exception.code, 2)
        self.assertRegex(stderr.getvalue(), r"^error: these tools need Python 3\.12 or newer")


class Capabilities(unittest.TestCase):
    def test_missing_profile_and_configured_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            empty = capabilities.report(base)
            self.assertIsNone(empty["profile"])
            self.assertEqual(empty["policies"]["cachedEvidence"], "forbidden")
            self.assertTrue(all(not w["available"] and w["fallback"] for w in empty["workflows"]))
            game = helpers.make_install(base)
            (base / "inc").mkdir()
            (base / "gta-sa-openmp-devkit.json").write_text(json.dumps({
                "game": {"installDir": str(game)}, "target": {"includeDirs": ["inc"]},
                "policies": {"cachedEvidence": "allowed-with-provenance"}}))
            flows = {w["workflow"]: w["available"] for w in capabilities.report(base / "inc")["workflows"]}
            self.assertTrue(flows["identify-build"] and flows["pawn-declaration-check"])
            self.assertFalse(flows["scm-decompile"])


class Package(unittest.TestCase):
    def test_version_labels_agree(self):
        import re
        from _common import TOOL_VERSION
        front = (helpers.SKILL / "SKILL.md").read_text().split("---", 2)[1]
        version = re.search(r'^  version: "([0-9]+\.[0-9]+\.[0-9]+)"$', front, re.M)
        self.assertIsNotNone(version)
        self.assertEqual(version.group(1), TOOL_VERSION)
        changelog = (helpers.ROOT / "CHANGELOG.md").read_text()
        self.assertEqual(re.search(r"^## ([0-9]+\.[0-9]+\.[0-9]+)$", changelog, re.M).group(1), TOOL_VERSION)
        tag_ref = os.environ.get("GITHUB_REF", "")
        if tag_ref.startswith("refs/tags/"):
            self.assertEqual(tag_ref, "refs/tags/v" + TOOL_VERSION)

    def test_skill_is_lean_portable_and_self_consistent(self):
        import re
        skill = (helpers.SKILL / "SKILL.md").read_text(encoding="utf-8")
        front = skill.split("---")[1]
        self.assertIn("name: gta-sa-openmp-devkit", front)
        description = re.search(r"^description: (.*)$", front, re.M).group(1)
        self.assertLessEqual(len(description), 1024)
        self.assertLessEqual(len(skill.splitlines()), 120)
        documents = [helpers.SKILL / "SKILL.md", *sorted((helpers.SKILL / "references").glob("*.md"))]
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\]\((?!https?:)([^)#]+)", text):
                self.assertTrue((document.parent / target).exists(), "%s links to missing %s" % (document.name, target))
            for script in re.findall(r"scripts/([a-z_]+\.py)", text):
                self.assertTrue((helpers.SCRIPTS / script).is_file(), "%s names missing %s" % (document.name, script))
        listed = set(re.findall(r"^\| `([a-z_]+\.py)`", skill, re.M))
        shipped = {p.name for p in helpers.SCRIPTS.glob("*.py") if not p.name.startswith("_")}
        self.assertEqual(listed, shipped)
        private = re.compile(r"/home/|/Users/|[A-Z]:\\\\(?!Old|VC|G\b)")
        for path in helpers.SKILL.rglob("*"):
            if path.is_file() and path.suffix in (".md", ".py", ".json", ".yaml", ".sh"):
                self.assertIsNone(private.search(path.read_text(encoding="utf-8")), "project-specific text in %s" % path)


if __name__ == "__main__":
    unittest.main()
