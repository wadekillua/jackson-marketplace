#!/usr/bin/env python3
"""提交前扫描暂存内容里的密钥、隐私信息和危险指令。只用 Python 标准库。

用法：
    python3 scripts/scan_secrets.py              # 扫描暂存区（pre-commit 默认调用）
    python3 scripts/scan_secrets.py --all        # 扫描工作区全部文件
    python3 scripts/scan_secrets.py --history    # 扫描 git 历史里的所有内容
    python3 scripts/scan_secrets.py --file 路径   # 扫描指定文件

退出码：
    0 = 通过（可能有警告）
    1 = 发现高风险内容，阻止提交
    2 = 用法错误

误报处理：在该行行尾加注释 `# allow-secret` 即可跳过这一行；
紧急情况下可以用 `git commit --no-verify` 跳过整个钩子。
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

BLOCK = "block"
WARN = "warn"

# 明显是占位符而不是真凭据的值，命中后不拦截。
PLACEHOLDERS = (
    "your_", "your-", "yourpassword", "example", "changeme", "change_me",
    "placeholder", "redacted", "dummy", "xxxx", "todo", "none", "null",
    "fake", "sample", "test_key", "<", "${", "{{", "***", "dotenv",
)

# (级别, 规则名, 正则, 处理建议)
RULES = [
    (BLOCK, "私钥文件块", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
     "别把私钥提交进仓库，改用环境变量或密钥管理服务"),
    (BLOCK, "GitHub 访问令牌", r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,255}\b",
     "去 GitHub 设置里吊销该令牌，重新生成后放到环境变量"),
    (BLOCK, "GitHub 细粒度令牌", r"\bgithub_pat_[A-Za-z0-9_]{50,255}\b",
     "去 GitHub 设置里吊销该令牌，重新生成后放到环境变量"),
    (BLOCK, "Anthropic API 密钥", r"\bsk-ant-[A-Za-z0-9_-]{24,}\b",
     "去 Anthropic 控制台吊销该密钥，改用环境变量注入"),
    (BLOCK, "OpenAI API 密钥", r"\bsk-(?!ant-)[A-Za-z0-9_-]{24,}\b",
     "去 OpenAI 控制台吊销该密钥，改用环境变量注入"),
    (BLOCK, "AWS AccessKey ID", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
     "去 AWS 控制台停用该密钥对，改用 IAM 角色或环境变量"),
    (BLOCK, "AWS Secret Key", r"(?i)aws_secret_access_key\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}",
     "去 AWS 控制台停用该密钥对，改用 IAM 角色或环境变量"),
    (BLOCK, "Google API Key", r"\bAIza[0-9A-Za-z_-]{35}\b",
     "去 Google Cloud 控制台吊销该密钥，改用环境变量"),
    (BLOCK, "Slack 令牌", r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b",
     "去 Slack 应用后台吊销该令牌，重新生成 webhook"),
    (BLOCK, "Slack Webhook", r"https://hooks\.slack\.com/services/[A-Za-z0-9_/]+",
     "去 Slack 应用后台吊销该 webhook"),
    (BLOCK, "Stripe 密钥", r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b",
     "去 Stripe 控制台吊销该密钥"),
    (BLOCK, "SendGrid 密钥", r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b",
     "去 SendGrid 控制台吊销该密钥"),
    (BLOCK, "Twilio 密钥", r"\bSK[0-9a-fA-F]{32}\b",
     "去 Twilio 控制台吊销该密钥"),
    (BLOCK, "npm 令牌", r"\bnpm_[A-Za-z0-9]{36}\b",
     "去 npm 后台吊销该令牌，重新生成后放到环境变量"),
    (BLOCK, "PyPI 令牌", r"\bpypi-[A-Za-z0-9_-]{16,}\b",
     "去 PyPI 后台吊销该令牌，重新生成后放到环境变量"),
    (BLOCK, "GitLab 令牌", r"\bglpat-[A-Za-z0-9_-]{20,}\b",
     "去 GitLab 个人设置吊销该令牌"),
    (BLOCK, "Discord 机器人令牌", r"\b[MNO][A-Za-z0-9_-]{23,}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}\b",
     "去 Discord 开发者后台重置该令牌"),
    (BLOCK, "Square 令牌", r"\bsq0(?:atp|csp)-[A-Za-z0-9_-]{20,}\b",
     "去 Square 后台吊销该令牌"),
    (BLOCK, "腾讯云密钥", r"\bAKID[A-Za-z0-9]{28,}\b",
     "去腾讯云控制台停用该密钥"),
    (BLOCK, "阿里云 AccessKey", r"\bLTAI[A-Za-z0-9]{16,}\b",
     "去阿里云控制台停用该密钥"),
    (BLOCK, "JWT 令牌", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
     "令牌不该进仓库，确认是否已泄露并轮换"),
    (BLOCK, "带密码的连接串", r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp|ftp)://[^\s:/@]+:[^\s/@]+@",
     "把连接串里的密码删掉，改用环境变量拼接"),
    (BLOCK, "飞书资源 token", r"\bIzNQ[A-Za-z0-9_-]{15,}\b",
     "飞书 token 不能入库，改从 lark.config.json 读取"),
    (BLOCK, "通用凭据赋值", r"(?i)\b(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key|app[_-]?secret|folder[_-]?token|passwd|password)\b\s*[:=]\s*[\"']?([A-Za-z0-9_\-+/=.]{16,})",
     "把真实值移到环境变量，仓库里只留变量名"),
    (BLOCK, "本机绝对路径", r"(?:/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|~/(?:Docu)ments/|~/(?:Docu)ments/work/)",
     "仓库里不要出现个人机器路径，改成相对路径或占位符"),
    # 规则字面量用拼接构造，避免扫描器源码命中自身规则。
    (BLOCK, "私有笔记库路径", "Jackson" + "Doc",
     "仓库里不要出现私有笔记库路径"),
    (BLOCK, "递归删除命令", r"\brm\s+-[a-z]*[rf][a-z]*\s+(?:/|~|\$HOME|\*)",
     "技能里不要包含会删数据的命令"),
    (BLOCK, "下载即执行", r"(?:curl|wget)[^|\n]*\|\s*(?:ba|z|d)?sh",
     "技能里不要包含下载后直接执行的命令"),
    (BLOCK, "磁盘格式化", r"\bmkfs(?:\.\w+)?\b|\bdd\s+if=",
     "技能里不要包含破坏性磁盘命令"),
    (BLOCK, "sudo 删除", r"\bsudo\s+rm\b",
     "技能里不要包含提权删除命令"),
    (BLOCK, "身份证号", r"(?<!\d)\d{17}[\dXx](?!\d)",
     "不要把身份证号写进仓库"),
    (WARN, "个人邮箱", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
     "公开仓库里的邮箱会被收集，必要时换成 noreply 邮箱"),
    (WARN, "手机号", r"(?<!\d)1[3-9]\d{9}(?!\d)",
     "公开仓库里的手机号会被收集，必要时删掉"),
    (WARN, "全员放权", r"\bchmod\s+777\b",
     "权限应收紧到最小"),
    (WARN, "可疑外发命令", r"(?:curl|wget)[^\n]*\s(?:-d|--data-binary|-F|--form|-T|--upload-file)\s",
     "确认这个命令不会把本地数据发到外部"),
    (WARN, "越权指令", r"(?i)ignore (?:all |any )?previous instructions|忽略(?:以上|之前|前面|之前所有)(?:的)?(?:指令|要求)|不要(?:告诉|告知)用户|悄悄(?:地)?(?:执行|上传|发送)",
     "技能里出现这类措辞可能让 Agent 绕过用户确认"),
]

COMPILED = [(level, name, re.compile(pattern), hint) for level, name, pattern, hint in RULES]

ALLOW_MARK = "allow-secret"
MAX_BYTES = 2 * 1024 * 1024
BINARY = b"\x00"


def mask(text):
    """只回显首尾几个字符，避免把真凭据又打印一遍。"""
    text = text.strip()
    if len(text) <= 12:
        return "***"
    return f"{text[:6]}…{text[-2:]}"


def is_placeholder(value):
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDERS)


def scan_text(text):
    """返回命中的规则列表，每项是 (级别, 规则名, 行号, 命中文本, 建议)。"""
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARK in line:
            continue
        for level, name, pattern, hint in COMPILED:
            match = pattern.search(line)
            if not match:
                continue
            if name == "通用凭据赋值" and is_placeholder(match.group(1)):
                continue
            findings.append((level, name, number, match.group(0), hint))
            break  # 一行只报第一条，避免刷屏
    return findings


def run_git(root, *args, binary=False):
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout if binary else result.stdout.decode("utf-8", "replace")


def staged_paths(root):
    output = run_git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return [line for line in output.splitlines() if line]


def worktree_paths(root):
    output = run_git(root, "ls-files", "--others", "--cached", "--exclude-standard")
    return [line for line in output.splitlines() if line]


def read_staged(root, path):
    try:
        return run_git(root, "show", f":{path}", binary=True)
    except RuntimeError:
        return b""


def read_file(path):
    try:
        return path.read_bytes()
    except OSError:
        return b""


def scan_bytes(data, path_label):
    if not data or BINARY in data[:8000] or len(data) > MAX_BYTES:
        return []
    text = data.decode("utf-8", "replace")
    return [
        (level, name, number, snippet, hint, path_label)
        for level, name, number, snippet, hint in scan_text(text)
    ]


def scan_paths(root, paths, reader):
    findings = []
    for path in paths:
        if path.startswith(".git/"):
            continue
        data = reader(path)
        findings.extend(scan_bytes(data, path))
    return findings


def scan_history(root):
    listing = run_git(root, "rev-list", "--all", "--objects")
    blobs = {}
    for line in listing.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        sha, path = parts
        if path.startswith(".git/"):
            continue
        blobs.setdefault(sha, path)
    findings = []
    for sha, path in blobs.items():
        try:
            data = run_git(root, "cat-file", "-p", sha, binary=True)
        except RuntimeError:
            continue
        findings.extend(scan_bytes(data, path))
    return findings


def report(findings):
    blocks = [f for f in findings if f[0] == BLOCK]
    warns = [f for f in findings if f[0] == WARN]
    if not findings:
        print("  ✓ 没有发现高风险内容")
        return not blocks
    for level, name, number, snippet, hint, path in sorted(findings, key=lambda f: (f[0] != BLOCK, f[5], f[2])):
        mark = "✗" if level == BLOCK else "!"
        print(f"  {mark} {path}:{number}  [{level}] {name}")
        print(f"      {mask(snippet)}")
        print(f"      建议：{hint}")
    if blocks:
        print(f"  → {len(blocks)} 处高风险内容会阻止提交")
    if warns:
        print(f"  → 另有 {len(warns)} 处提醒（不阻止提交）")
    return not blocks


def main():
    parser = argparse.ArgumentParser(description="扫描暂存内容里的密钥、隐私信息和危险指令")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", help="扫描暂存区（默认行为）")
    group.add_argument("--all", action="store_true", help="扫描工作区全部文件")
    group.add_argument("--history", action="store_true", help="扫描 git 历史里的所有内容")
    group.add_argument("--file", help="扫描指定文件")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    try:
        if args.file:
            path = Path(args.file)
            findings = scan_bytes(read_file(path), str(path))
        elif args.history:
            findings = scan_history(root)
        elif args.all:
            findings = scan_paths(root, worktree_paths(root), lambda p: read_file(root / p))
        else:
            findings = scan_paths(root, staged_paths(root), lambda p: read_staged(root, p))
    except RuntimeError as exc:
        print(f"扫描失败：{exc}", file=sys.stderr)
        return 2

    ok = report(findings)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
