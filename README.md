# Jackson Marketplace

我的个人智能技能库，用来保存实际工作中逐步沉淀的产品、前端、设计和写作技能。

参考 [khazix-skills](https://github.com/KKKKhazix/khazix-skills) 的技能合集与插件分发方式搭建。每个技能独立维护，Claude Code 和 Codex 共用同一份内容。

**当前正式技能：3 个。** 模板内嵌在维护脚本中，不会被安装。

## 技能目录

| 技能 | 用途 |
| --- | --- |
| [viral-longform-zh](skills/viral-longform-zh/) | 长图文创作与改稿公式库，涵盖标题、开篇、结构、正文、结尾和配套要素，共 24 个公式。 |
| [bidirectional-steelman](skills/bidirectional-steelman/) | 双向钢人论证：先澄清问题、给出支持与反对的最强理由，只问一个关键问题；回答后再给判断与行动。 |
| [大野心提示词 · big-ambition-prompt](skills/big-ambition-prompt/) | 从高度、深度、广度提升任务，输出简要分析、可直接使用的正式提示词和必要前置条件。 |

使用示例：

> 用 bidirectional-steelman 帮我分析：我想把个人技能库改成私有仓库。先做双向钢人论证，只问一个关键问题，等我回答后再给判断。

> 用“大野心提示词”改写这项任务：为我的个人技能库设计一套持续维护方案。

## 新增技能

需要 Python 3.10+，无需安装第三方依赖。在仓库根目录运行：

```bash
python3 scripts/manage.py new my-skill --description "处理某类具体任务；当用户需要……时使用。"
```

命令会创建 `skills/my-skill/SKILL.md`，并拒绝覆盖已有目录。补全文件中的 TODO，按实际需要添加 `scripts/`、`references/` 或 `assets/`，再运行检查：

```bash
python3 scripts/manage.py check
python3 -m unittest discover -s tests -v
```

也可以对 AI 说：

> 在这个仓库新增一个个人技能，用于【具体工作】。先了解我的输入、输出与完成标准，再创建技能，补全模板并检查。

## 安装

### Claude Code

在 Claude Code 中执行：

```text
/plugin marketplace add wadekillua/jackson-marketplace
/plugin install jackson-skills@jackson-marketplace
```

更新：

```bash
claude plugin update jackson-skills@jackson-marketplace
```

### Codex

支持插件命令的 Codex CLI 中执行：

```bash
codex plugin marketplace add wadekillua/jackson-marketplace
codex plugin add jackson-skills@jackson-marketplace
```

更新市场快照：

```bash
codex plugin marketplace upgrade jackson-marketplace
```

本仓库使用官方支持的插件清单与仓库市场结构，参见 [OpenAI 插件打包文档](https://developers.openai.com/plugins/build/plugins)。不同客户端的插件入口可能不同，以本机版本提供的命令和界面为准。

### 单独安装一个技能

可让 Agent 安装指定目录：

```text
帮我安装这个技能：https://github.com/wadekillua/jackson-marketplace/tree/main/skills/<skill-name>
```

也可把整个 `skills/<skill-name>/` 目录复制到：

| 工具 | 个人目录 | 项目目录 |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex | `~/.agents/skills/` | `.agents/skills/` |

保留完整目录与资源文件。插件安装和单技能安装任选一种，避免重复加载。

## 仓库结构

```text
jackson-marketplace/
├── plugin.json                     # 插件身份、版本和简介的维护入口
├── .agents/plugins/marketplace.json # Codex 市场清单（自动生成）
├── .claude-plugin/                 # Claude Code 兼容清单（自动生成）
├── skills/                         # 正式技能
│   ├── viral-longform-zh/          # 长图文创作公式
│   ├── bidirectional-steelman/     # 双向钢人论证
│   └── big-ambition-prompt/        # 大野心提示词
├── scripts/manage.py               # 新增、同步、校验（内嵌技能模板）
├── tests/                          # 维护脚本的行为测试
└── .github/workflows/validate.yml   # 自动校验
```

## 维护

- 插件名称 `jackson-skills`，市场名称 `jackson-marketplace`。
- 修改插件名称、版本或简介后，运行 `python3 scripts/manage.py sync`；不要手改生成的清单。
- 加入技能无需逐个注册，插件从 `skills/` 读取技能。
- 校验会检查清单一致性、技能名称与必填描述、模板残留和目录中的符号链接；它不能替代真实任务验证，也不是完整的 YAML 语法或安全审计。
- 安装内容有变化时，在 `plugin.json` 更新版本，并记录到 `CHANGELOG.md`。
- 本仓库只存放可复用的技能与资源；个人资料和运行产物保留在各自项目中。

本项目采用 [MIT License](LICENSE)。参考项目仅作为结构参考，未迁入其技能内容。
