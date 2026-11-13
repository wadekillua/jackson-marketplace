import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("manage", ROOT / "scripts/manage.py")
manage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manage)


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copy(ROOT / "plugin.json", self.root)
        shutil.copytree(ROOT / "templates", self.root / "templates")
        (self.root / "skills").mkdir()
        manage.sync(self.root)

    def test_empty_library_is_valid(self):
        self.assertEqual(manage.check(self.root), [])

    def test_new_skill_preserves_description_and_blocks_overwrite(self):
        description = '描述中的 "引号"、冒号: 和中文'
        target = manage.new_skill(self.root, "sample", description)
        original = (target / "SKILL.md").read_text()
        line = original.splitlines()[2].removeprefix("description: ")
        self.assertEqual(json.loads(line), description)
        with self.assertRaises(FileExistsError):
            manage.new_skill(self.root, "sample", "另一个描述")
        self.assertEqual((target / "SKILL.md").read_text(), original)
        self.assertTrue(any("模板" in error for error in manage.check(self.root)))

    def test_new_skill_rejects_paths_and_bad_metadata(self):
        for name in ("../escape", "/tmp/escape", "UpperCase", "", "a" * 65):
            with self.subTest(name=name), self.assertRaises(ValueError):
                manage.new_skill(self.root, name, "描述")
        for description in ("", "  ", "a\nb", "a\rb"):
            with self.subTest(description=description), self.assertRaises(ValueError):
                manage.new_skill(self.root, "sample", description)

    def test_completed_skill_is_discovered_without_registration(self):
        target = manage.new_skill(self.root, "sample", "用于处理示例任务。")
        (target / "SKILL.md").write_text(
            '---\nname: sample\ndescription: "用于处理示例任务。"\n---\n\n交付用户要求的结果。\n',
            encoding="utf-8",
        )
        self.assertEqual(manage.check(self.root), [])

    def test_missing_entry_and_name_mismatch_fail(self):
        target = self.root / "skills/sample"
        target.mkdir()
        self.assertTrue(manage.check(self.root))
        (target / "SKILL.md").write_text('---\nname: other\ndescription: "说明"\n---\n正文\n')
        self.assertTrue(any("不一致" in error for error in manage.check(self.root)))

    def test_stale_manifest_fails_and_sync_repairs_it(self):
        path = self.root / "plugin.json"
        metadata = json.loads(path.read_text())
        metadata["version"] = "0.2.0"
        path.write_text(json.dumps(metadata))
        self.assertTrue(any("不同步" in error for error in manage.check(self.root)))
        manage.sync(self.root)
        self.assertEqual(manage.check(self.root), [])

    def test_symlink_to_external_skill_is_rejected(self):
        target = self.root / "skills/external"
        target.symlink_to(self.root / "templates/skill", target_is_directory=True)
        self.assertTrue(any("符号链接" in error for error in manage.check(self.root)))


if __name__ == "__main__":
    unittest.main()
