#!/usr/bin/env bash
# install-hooks.sh — 启用本仓库的 git hooks
#
# 作用：设置 core.hooksPath 指向 .githooks/，让 git 在 commit 前自动跑 pre-commit
#
# 用法：bash scripts/install-hooks.sh
#
# 说明：
#   - 只对当前仓库生效（git config --local），不影响其他仓库
#   - 每个新 clone 出来的副本需要单独跑一次
#   - 钩子只在本地执行，不上传任何内容

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

HOOKS_DIR=".githooks"

if [[ ! -d "$HOOKS_DIR" ]]; then
  echo "✗ 找不到 $HOOKS_DIR 目录" >&2
  exit 1
fi

if [[ ! -x "$HOOKS_DIR/pre-commit" ]]; then
  echo "· $HOOKS_DIR/pre-commit 不可执行，正在 chmod +x"
  chmod +x "$HOOKS_DIR/pre-commit"
fi

git config core.hooksPath "$HOOKS_DIR"

echo "✓ 已启用本仓库的 git hooks"
echo "  core.hooksPath = $HOOKS_DIR"
echo ""
echo "效果：每次 git commit 前自动扫描密钥、隐私信息和危险指令，命中就拦下提交。"
echo ""
echo "验证："
echo "  echo 'xoxb-<在这里粘一个真令牌>' > /tmp/leak.txt"
echo "  git add /tmp/leak.txt && git commit -m test    # 应该被拦截"
echo ""
echo "跳过（不推荐）：git commit --no-verify"
