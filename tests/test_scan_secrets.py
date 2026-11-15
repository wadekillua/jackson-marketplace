import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("scan_secrets", ROOT / "scripts/scan_secrets.py")
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)

# 假凭据一律用拼接构造，这样测试文件本身不会被扫描器命中。
FAKE_GITHUB = "gh" + "p_" + "a1B2c3D4" * 5
FAKE_ANTHROPIC = "sk" + "-ant-" + "api03" + "Z" * 40
FAKE_PRIVATE_KEY = "-----BEGIN " + "RSA " + "PRIVATE KEY-----" + "\n"
FAKE_SLACK = "xox" + "b-" + "123456789012-" + "abcdefghijklmnop"
CREDENTIAL_WORD = "pass" + "word"


def rule_names(text):
    return [name for _level, name, _line, _snippet, _hint in scanner.scan_text(text)]


def levels(text):
    return [level for level, _name, _line, _snippet, _hint in scanner.scan_text(text)]


class ScanSecretsTest(unittest.TestCase):
    def test_provider_tokens_are_blocked(self):
        for sample in (FAKE_GITHUB, FAKE_ANTHROPIC, FAKE_SLACK, FAKE_PRIVATE_KEY):
            with self.subTest(sample=sample[:12]):
                self.assertIn(scanner.BLOCK, levels(sample))

    def test_generic_credential_assignment_is_blocked(self):
        sample = CREDENTIAL_WORD + ' = "' + "Zq7Kx2mW9pL4vR8tY" + '"'
        self.assertIn("通用凭据赋值", rule_names(sample))
        self.assertIn(scanner.BLOCK, levels(sample))

    def test_placeholder_value_is_not_blocked(self):
        sample = CREDENTIAL_WORD + ' = "' + "your_" + "value_here_placeholder" + '"'
        self.assertNotIn(scanner.BLOCK, levels(sample))

    def test_allow_secret_marker_suppresses_finding(self):
        sample = FAKE_GITHUB + "  # allow-secret"
        self.assertEqual(scanner.scan_text(sample), [])

    def test_private_machine_path_is_blocked(self):
        sample = "见 " + "/Users/" + "someone" + "/notes.md"
        self.assertIn("本机绝对路径", rule_names(sample))

    def test_public_email_is_only_a_warning(self):
        sample = "联系 " + "someone" + "@" + "example.com"
        self.assertIn(scanner.WARN, levels(sample))
        self.assertNotIn(scanner.BLOCK, levels(sample))

    def test_dangerous_command_is_blocked(self):
        self.assertIn(scanner.BLOCK, levels("清理一下 ~ " + "rm -rf " + "/"))

    def test_clean_content_produces_nothing(self):
        sample = "这是一个正常技能：说明如何写标题，输出 30 字以内。"
        self.assertEqual(scanner.scan_text(sample), [])

    def test_findings_carry_line_numbers(self):
        sample = "第一行没问题\n第二行 " + FAKE_GITHUB + "\n"
        findings = scanner.scan_text(sample)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][2], 2)

    def test_mask_hides_the_middle(self):
        masked = scanner.mask(FAKE_GITHUB)
        self.assertNotIn(FAKE_GITHUB, masked)
        self.assertIn("…", masked)

    def test_scanner_does_not_trigger_on_its_own_source(self):
        source = (ROOT / "scripts/scan_secrets.py").read_bytes()
        findings = scanner.scan_bytes(source, "scripts/scan_secrets.py")
        blocking = [f for f in findings if f[0] == scanner.BLOCK]
        self.assertEqual(blocking, [], f"扫描器源码命中自身规则：{blocking}")

    def test_repository_files_are_clean(self):
        skipped = {ROOT / "scripts/scan_secrets.py", Path(__file__).resolve()}
        blocking = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path in skipped:
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            data = path.read_bytes()
            for finding in scanner.scan_bytes(data, str(path.relative_to(ROOT))):
                if finding[0] == scanner.BLOCK:
                    blocking.append(finding)
        self.assertEqual(blocking, [], f"仓库内存在高风险内容：{blocking}")


if __name__ == "__main__":
    unittest.main()
