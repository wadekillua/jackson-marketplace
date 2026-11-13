#!/usr/bin/env python3
"""Manage the personal skill library using only Python's standard library."""

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = "jackson-marketplace"
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")

SKILL_TEMPLATE = """---
name: {{NAME}}
description: {{DESCRIPTION}}
---

# {{NAME}}

TODO: 写清这个技能要交付什么，以及判断任务完成的标准。

## 工作方式

TODO: 补充会改变执行决策的步骤、必要输入和约束；删除通用常识。

## 配套资源

TODO: 需要时添加 scripts/、references/ 或 assets/ 并在此引用；不需要则删除本节。
"""


def valid_name(name):
    return len(name) <= 64 and NAME_PATTERN.fullmatch(name) is not None


def read_metadata(root):
    data = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    if not valid_name(data.get("name", "")):
        raise ValueError("plugin.json: 插件名称格式不正确")
    if not re.fullmatch(r"\d+\.\d+\.\d+", data.get("version", "")):
        raise ValueError("plugin.json: 版本使用 x.y.z 格式")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        raise ValueError("plugin.json: 缺少 description")
    return data


def manifests(root):
    data = read_metadata(root)
    plugin = {key: data[key] for key in ("name", "version", "description")}
    plugin.update(author={"name": "Jackson"}, skills="./skills/")
    return {
        ".claude-plugin/plugin.json": plugin,
        ".claude-plugin/marketplace.json": {
            "name": MARKETPLACE,
            "metadata": {"description": data["description"]},
            "owner": {"name": "Jackson"},
            "plugins": [{"name": data["name"], "source": "./"}],
        },
        ".agents/plugins/marketplace.json": {
            "name": MARKETPLACE,
            "interface": {"displayName": "Jackson 个人技能库"},
            "plugins": [{
                "name": data["name"],
                "source": {"source": "local", "path": "./"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Productivity",
            }],
        },
    }


def sync(root):
    for relative, data in manifests(root).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def new_skill(root, name, description):
    if not valid_name(name):
        raise ValueError("技能名称须为不超过 64 字符的小写英文、数字和连字符")
    if not description.strip() or "\n" in description or "\r" in description:
        raise ValueError("description 须为非空的单行文本")
    content = SKILL_TEMPLATE
    # Substitute in one pass: user text may itself contain template markers.
    values = {"NAME": name, "DESCRIPTION": json.dumps(description, ensure_ascii=False)}
    content = re.sub(r"\{\{(NAME|DESCRIPTION)\}\}", lambda match: values[match[1]], content)
    target = root / "skills" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()  # Refuse to overwrite an existing skill.
    (target / "SKILL.md").write_text(content, encoding="utf-8")
    return target


def check_skill(directory):
    errors = []
    entry = directory / "SKILL.md"
    if not valid_name(directory.name):
        errors.append(f"{directory.name}: 技能目录名称格式不正确")
    if not entry.is_file():
        return errors + [f"{directory.name}: 缺少 SKILL.md"]
    content = entry.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", content, re.S)
    fields = {}
    if match:
        for key in ("name", "description"):
            values = re.findall(rf"^{key}:[ \t]*([^\n]*)$", match[1], re.M)
            if len(values) != 1:
                errors.append(f"{directory.name}: {key} 须出现一次")
                continue
            value = values[0].strip()
            if key == "description" and re.fullmatch(r"[|>][-+]?", value):
                block = re.search(
                    r"^description:[ \t]*[|>][-+]?[ \t]*\r?\n((?:(?:[ \t]+[^\n]*|)[\n]|[ \t]+[^\n]*$)*)",
                    match[1], re.M,
                )
                value = "\n".join(line.strip() for line in block[1].splitlines()).strip() if block else ""
            elif value.startswith('"'):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    errors.append(f"{directory.name}: {key} 双引号值须使用 JSON 兼容转义")
                    continue
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1].replace("''", "'")
            if not isinstance(value, str) or not value.strip() or value in ("|", ">", "|-", ">-"):
                errors.append(f"{directory.name}: {key} 须为非空文本（description 支持多行块）")
            else:
                fields[key] = value
        if fields.get("name") != directory.name:
            errors.append(f"{directory.name}: name 与目录名不一致")
        if not content[match.end():].strip():
            errors.append(f"{directory.name}: 缺少技能正文")
    else:
        errors.append(f"{directory.name}: 缺少 YAML frontmatter")
    if re.search(r"\{\{[^{}]+\}\}|\bTODO\b", content):
        errors.append(f"{directory.name}: 尚有模板占位内容")
    for path in directory.rglob("*"):
        if path.is_symlink():
            errors.append(f"{directory.name}: 分发目录不允许符号链接 {path.name}")
    return errors


def check(root):
    errors = []
    for relative, expected in manifests(root).items():
        path = root / relative
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
            if actual != expected:
                errors.append(f"{relative}: 清单不同步，请运行 sync")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{relative}: {exc}")
    skills = root / "skills"
    if not skills.is_dir():
        return errors + ["缺少 skills/ 目录"]
    for path in sorted(skills.iterdir()):
        if path.name.startswith("."):
            continue  # .DS_Store 等系统文件不是技能内容
        if path.is_symlink():
            errors.append(f"{path.name}: 分发目录不允许符号链接")
        elif path.is_dir():
            errors.extend(check_skill(path))
        else:
            errors.append(f"skills/{path.name}: 技能须放在独立目录中")
    return errors


def main():
    parser = argparse.ArgumentParser(description="新增、同步与检查 Jackson 个人技能库")
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new", help="从模板新增技能，拒绝覆盖")
    new.add_argument("name")
    new.add_argument("--description", required=True)
    commands.add_parser("sync", help="从 plugin.json 生成兼容清单")
    commands.add_parser("check", help="检查清单和正式技能")
    args = parser.parse_args()
    try:
        if args.command == "new":
            target = new_skill(ROOT, args.name, args.description)
            print(f"已创建 {target.relative_to(ROOT)}/SKILL.md；请补全 TODO 后运行 check。")
        elif args.command == "sync":
            sync(ROOT)
            print("分发清单已同步。")
        else:
            errors = check(ROOT)
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
            count = sum(path.is_dir() for path in (ROOT / "skills").iterdir())
            print(f"PASS：清单一致，正式技能 {count} 个。")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
