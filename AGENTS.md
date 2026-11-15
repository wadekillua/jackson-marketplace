# Jackson Marketplace

Jackson 的个人技能库；中文交流，面向 Claude Code 和 Codex。

## 维护约定

- 正式技能只放 `skills/<skill-name>/`，每个目录包含 `SKILL.md`。新技能模板内嵌在 `scripts/manage.py`，不单独存放，也不会被当作技能加载。
- 未经用户要求，不迁入其他仓库或本机已安装的技能。
- `plugin.json` 是插件名称、版本、简介的维护入口。修改后运行 `python3 scripts/manage.py sync` 生成兼容清单。
- 保持技能自包含，资源通过相对路径引用；不要写入个人绝对路径、凭据或私有工作资料。
- 名称用小写英文和连字符。description 写能力和触发场景，正文保留必要决策与约束。
- 新技能先补全模板再提交。用真实任务验证技能行为；配套脚本应实际运行检查。
- 修改安装内容时更新插件版本与 `CHANGELOG.md`；只改说明不必升级版本。
- 提交前运行 `python3 scripts/manage.py check` 和 `python3 -m unittest discover -s tests -v`。
- 提交前必须过 pre-commit 钩子（`.githooks/pre-commit`），新克隆的副本先运行 `bash scripts/install-hooks.sh` 启用。误报在该行行尾加 `# allow-secret`，紧急情况用 `git commit --no-verify`。
- 不擅自安装插件或修改用户的 Claude Code、Codex 配置。
