import json
import os
import struct
import tempfile
import unittest
from pathlib import Path

import helpers
import export_ipl_records
import export_manifest
import identify_build
import scan_scm_opcodes
from _common import DevkitError, find_install_root, sha256_bytes, write_json


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.game = helpers.make_install(self.base)

    def tearDown(self):
        self.tmp.cleanup()


class WriteProtection(Base):
    def test_preexisting_temporary_hardlink_cannot_overwrite_game_files(self):
        victim = self.game / "data" / "handling.cfg"
        before = victim.read_bytes()
        output = self.base / "manifest.json"
        collision = output.with_name(output.name + ".tmp")
        os.link(victim, collision)
        write_json(output, {"safe": True})
        self.assertEqual(victim.read_bytes(), before)
        self.assertEqual(collision.read_bytes(), before)
        self.assertEqual(json.loads(output.read_text()), {"safe": True})

    def test_preexisting_temporary_symlink_cannot_overwrite_game_files(self):
        victim = self.game / "data" / "handling.cfg"
        before = victim.read_bytes()
        output = self.base / "manifest.json"
        collision = output.with_name(output.name + ".tmp")
        try:
            collision.symlink_to(victim)
        except (OSError, NotImplementedError):
            self.skipTest("this account cannot create file links")
        write_json(output, {"safe": True})
        self.assertEqual(victim.read_bytes(), before)
        self.assertTrue(collision.is_symlink())

    def test_failed_json_write_preserves_previous_output_and_cleans_temporary_file(self):
        output = self.base / "manifest.json"
        output.write_text('{"previous": true}\n')
        before = set(self.base.iterdir())
        with self.assertRaises(TypeError):
            write_json(output, {"invalid": object()})
        self.assertEqual(json.loads(output.read_text()), {"previous": True})
        self.assertEqual(set(self.base.iterdir()), before)

    def test_outputs_inside_an_installation_are_refused(self):
        for target in (self.game / "out.json", self.game / "data" / "new" / "out.json"):
            with self.assertRaisesRegex(DevkitError, "outside a game installation"):
                write_json(target, {})
            self.assertFalse(target.exists())
        self.assertEqual(find_install_root(self.game / "data" / "maps"), self.game)

    def test_a_link_into_the_installation_does_not_bypass_the_refusal(self):
        link = self.base / "shortcut"
        try:
            os.symlink(self.game / "data", link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("this account cannot create directory links")
        with self.assertRaisesRegex(DevkitError, "outside a game installation"):
            write_json(link / "out.json", {})
        self.assertFalse((self.game / "data" / "out.json").exists())
        self.assertTrue(write_json(self.base / "out" / "ok.json", {"a": 1}).is_file())


class BuildIdentity(Base):
    def table(self, builds):
        path = self.base / "known.json"
        path.write_text(json.dumps({"schemaVersion": 1, "builds": builds}))
        return path

    def test_pe_facts_and_probe(self):
        exe = self.game / "gta_sa.exe"
        result = identify_build.identify(exe, self.table([]), ["0x401000"], 4, show_bytes=True)
        self.assertEqual(result["pe"]["imageBase"], "0x400000")
        probe = result["probes"][0]
        self.assertEqual((probe["rva"], probe["fileOffset"], probe["bytes"]), ("0x1000", "0x400", "aa bb cc dd"))
        self.assertEqual(probe["sha256"], sha256_bytes(b"\xAA\xBB\xCC\xDD"))
        self.assertEqual(result["identity"]["match"], "none")
        outside = identify_build.identify(exe, self.table([]), ["0x900000"], 4)["probes"][0]
        self.assertEqual(outside["status"], "not-file-backed")

    def test_hash_match_keeps_the_recorded_confidence(self):
        exe = self.game / "gta_sa.exe"
        digest = sha256_bytes(exe.read_bytes())
        table = self.table([{"id": "fixture", "label": "Fixture build", "labelConfidence": "corroborated",
                             "exe": {"sha256": digest}}])
        identity = identify_build.identify(exe, table)["identity"]
        self.assertEqual((identity["match"], identity["labelConfidence"]), ("hash", "corroborated"))

    def test_signature_only_match_is_not_an_identification(self):
        table = self.table([{"id": "fixture", "label": "Fixture build", "exe": {"sha256": "0" * 64},
                             "probes": [{"va": "0x401000", "length": 4, "sha256": sha256_bytes(b"\xAA\xBB\xCC\xDD")}]}])
        identity = identify_build.identify(self.game / "gta_sa.exe", table)["identity"]
        self.assertEqual((identity["match"], identity["labelConfidence"]), ("probes-only", "documented-only"))

    def test_name_proves_nothing(self):
        fake = self.base / "gta_sa_1.0_us_original.exe"
        fake.write_bytes(b"not an executable")
        result = identify_build.identify(fake, self.table([]))
        self.assertFalse(result["pe"]["valid"])
        self.assertEqual(result["identity"]["match"], "none")

    def test_shipped_table_is_well_formed(self):
        table = json.loads(identify_build.DEFAULT_TABLE.read_text())
        for build in table["builds"]:
            self.assertRegex(build["exe"]["sha256"], "^[0-9a-f]{64}$")
            self.assertIn(build["labelConfidence"], ("confirmed", "corroborated", "documented-only"))


class Manifest(Base):
    def test_groups_references_and_determinism(self):
        first = export_manifest.build_manifest(self.game)
        groups = {g["id"]: g for g in first["groups"]}
        self.assertEqual(groups["script"]["count"], 1)
        self.assertIsNone(groups["archives"]["aggregateSha256"])
        self.assertTrue(first["complete"])
        self.assertEqual(first["installation"]["executable"]["pe"]["architecture"], "x86")
        reference = self.base / "ref.json"
        reference.write_text(json.dumps({"sources": [
            {"path": "data/script/main.scm", "sha256": sha256_bytes(b"scm-fixture")},
            {"path": "data/handling.cfg", "sha256": "1" * 64}]}))
        second = export_manifest.build_manifest(self.game, [reference], hash_archives=True)
        groups2 = {g["id"]: g for g in second["groups"]}
        self.assertEqual(groups2["script"]["matchesRecorded"], 1)
        self.assertEqual(groups2["data-cfg"]["differsFromRecorded"], 1)
        self.assertEqual(groups2["script"]["aggregateSha256"], groups["script"]["aggregateSha256"])
        self.assertIsNotNone(groups2["archives"]["aggregateSha256"])

    def test_a_folder_without_an_executable_is_not_a_complete_manifest(self):
        empty = self.base / "NotAGame"
        (empty / "data").mkdir(parents=True)
        manifest = export_manifest.build_manifest(empty)
        self.assertFalse(manifest["complete"])
        self.assertIn("no game executable", manifest["problems"][0]["message"])


class IplRecords(Base):
    def test_fractional_interior_or_flags_are_malformed_not_truncated(self):
        for field, value in ((11, "3.75"), (12, "4.5"), (11, "3.00000000000000000000000000001")):
            with self.subTest(field=field):
                parts = helpers.ENEX_OK.split(",")
                parts[field] = value
                helpers.write_ipl(self.game, "fractional.ipl", "enex\n%s\nend\n" % ",".join(parts))
                result = export_ipl_records.export_records(self.game, "enex")
                self.assertFalse(result["complete"])
                self.assertEqual(result["records"], [])
                self.assertEqual(len(result["problems"]), 1)
                self.assertIn("integer", result["problems"][0]["message"])

    def test_integral_decimal_fields_remain_exact(self):
        parts = helpers.ENEX_OK.split(",")
        parts[11], parts[12] = "3.0", "4e0"
        helpers.write_ipl(self.game, "integral.ipl", "enex\n%s\nend\n" % ",".join(parts))
        result = export_ipl_records.export_records(self.game, "enex")
        self.assertTrue(result["complete"])
        self.assertEqual((result["records"][0]["areaCode"], result["records"][0]["flags"]), (3, 4))

    def test_enex_and_grge_rows_with_provenance(self):
        path = helpers.write_ipl(self.game, "a.ipl", "inst\nend\nenex\n# note\n%s\nend\ngrge\n%s\nend\n"
                                 % (helpers.ENEX_OK, helpers.GRGE_OK))
        enex = export_ipl_records.export_records(self.game, "enex")
        row = enex["records"][0]
        self.assertEqual((row["source"], row["line"], row["name"]), ("data/maps/area/a.ipl", 5, "DOORA"))
        self.assertEqual((row["entry"], row["destination"], row["areaCode"]), ([1.5, 2.5, 3.5], [10, 20, 30], 3))
        self.assertEqual(enex["sources"][0]["sha256"], sha256_bytes(path.read_bytes()))
        self.assertTrue(enex["complete"])
        grge = export_ipl_records.export_records(self.game, "grge")["records"][0]
        self.assertEqual((grge["name"], grge["type"], grge["opposite"]), ("garage_a", 5, [6, 7, 8]))

    def test_malformed_and_binary_input_is_reported_not_hidden(self):
        helpers.write_ipl(self.game, "bad.ipl", "enex\n%s\n1, 2, oops\nnan, 2.5, 3.5, 90, 1, 2, 8, 10, 20, 30, 180, 3, 4, X, 0, 2, 0, 24\n"
                          % helpers.ENEX_OK)
        (self.game / "data" / "maps" / "area" / "stream.ipl").write_bytes(b"bnry" + bytes(32))
        result = export_ipl_records.export_records(self.game, "enex")
        self.assertEqual(len(result["records"]), 1)
        self.assertFalse(result["complete"])
        messages = " ".join(p["message"] for p in result["problems"])
        self.assertIn("expected at least 18 fields", messages)
        self.assertIn("non-finite", messages)
        self.assertIn("no end marker", messages)
        self.assertEqual(result["coverage"]["binaryIplSkipped"], 1)
        self.assertFalse(result["coverage"]["archiveStreamedIplScanned"])


def instruction(opcode, *args, negate=False):
    return struct.pack("<H", opcode | (0x8000 if negate else 0)) + b"".join(args)


def make_img(entries, count=None, sectors_override=None):
    directory, payload, offset = b"", b"", 1
    for name, data in entries:
        sectors = sectors_override or -(-len(data) // 2048)
        directory += struct.pack("<IHH", offset, sectors, 0) + name.encode().ljust(24, b"\0")
        payload += data.ljust(-(-len(data) // 2048) * 2048, b"\0")
        offset += -(-len(data) // 2048)
    head = b"VER2" + struct.pack("<i", len(entries) if count is None else count) + directory
    return head.ljust(2048, b"\0") + payload


class ScmScan(Base):
    def setUp(self):
        super().setUp()
        self.work = self.base / "work"
        self.work.mkdir()
        body = (b"\xFF" * 8 + instruction(0x00A5, b"\x01" + struct.pack("<i", 411), b"\x06" + struct.pack("<f", 2.5))
                + b"\xFF" * 4 + instruction(0x00A5, b"\x09" + b"SHOP\0\0\0\0", negate=True)
                + b"\xFF" * 4 + struct.pack("<H", 0x00A5) + b"\x77\x00")
        self.scm = self.work / "main.scm"
        self.scm.write_bytes(body)

    def test_hits_arguments_and_filters(self):
        facts = scan_scm_opcodes.build_facts(self.scm, ["0x00A5"])
        self.assertEqual([h["offset"] for h in facts["hits"]], ["0x8", "0x18"])
        self.assertEqual(facts["hits"][0]["args"][:2], [{"type": "int32", "value": 411}, {"type": "float", "value": 2.5}])
        self.assertTrue(facts["hits"][1]["notFlag"])
        self.assertEqual(facts["summary"][0]["rejectedByTypeOrFilter"], 1)
        self.assertTrue(facts["complete"])
        self.assertFalse(facts["coverage"]["scriptImg"])
        self.assertIn("NOT scanned", facts["coverage"]["statement"])
        only = scan_scm_opcodes.build_facts(self.scm, ["00A5"], known_strings=["shop"])
        self.assertEqual([h["offset"] for h in only["hits"]], ["0x18"])

    def test_truncation_makes_the_result_incomplete(self):
        facts = scan_scm_opcodes.build_facts(self.scm, ["00A5"], max_hits=1)
        self.assertEqual(len(facts["hits"]), 1)
        self.assertTrue(facts["summary"][0]["truncated"])
        self.assertFalse(facts["complete"])

    def test_archive_entries_and_damage(self):
        img = self.work / "script.img"
        img.write_bytes(make_img([("shop.scm", instruction(0x00A5, b"\x04\x05"))]))
        facts = scan_scm_opcodes.build_facts(self.scm, ["00A5"], img)
        self.assertIn("script.img:shop.scm", [h["source"] for h in facts["hits"]])
        self.assertEqual(facts["imgEntries"], 1)
        self.assertTrue(facts["coverage"]["scriptImg"])
        img.write_bytes(make_img([("shop.scm", instruction(0x00A5, b"\x04\x05"))], sectors_override=9))
        damaged = scan_scm_opcodes.build_facts(self.scm, ["00A5"], img)
        self.assertFalse(damaged["complete"])
        self.assertIn("cut short", damaged["problems"][0]["message"])
        img.write_bytes(make_img([("a", b"x")], count=5000))
        with self.assertRaisesRegex(DevkitError, "malformed"):
            scan_scm_opcodes.build_facts(self.scm, ["00A5"], img)
        img.write_bytes(b"NOPE" + bytes(64))
        with self.assertRaisesRegex(DevkitError, "not a VER2"):
            scan_scm_opcodes.build_facts(self.scm, ["00A5"], img)

    def test_refuses_installation_copies_and_bad_opcodes(self):
        with self.assertRaisesRegex(DevkitError, "private copy"):
            scan_scm_opcodes.build_facts(self.game / "data" / "script" / "main.scm", ["00A5"])
        with self.assertRaisesRegex(DevkitError, "hexadecimal"):
            scan_scm_opcodes.build_facts(self.scm, ["zz"])


if __name__ == "__main__":
    unittest.main()
