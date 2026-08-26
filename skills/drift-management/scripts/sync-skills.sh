#!/bin/bash
# 软链同步脚本（通用模板）— 把权威源文件同步为各节点的符号链接
# 核心原则：同一信息只有一个物理位置，其他全部是链接。
#
# ⚠️ 用法：改下方【配置区】适配你的环境，再运行。
# ⚠️ 注意：本脚本会清空各节点的共享目录（rm -rf），跑之前先备份节点独有文件。

set -u

# ═══════════════ 配置区（按你的环境修改）═══════════════
# 权威源目录（唯一物理位置）
AUTHORITY_DIR="${HOME}/.hermes/profiles/main/skills/shared"
# 共享文件清单（权威源里的子目录名）
SHARED="common-skill-a common-skill-b common-skill-c"
# 各节点：节点名 + 该节点要链接的共享文件（空格分隔）
# 例：link_node <profile名> <该节点专属的共享文件...>
# ════════════════════════════════════════════════════

link_node() {
  local node="$1"; shift
  local dst_dir="${HOME}/.hermes/profiles/${node}/skills/shared"
  local ok=0 fail=0

  # 清空旧目录（旧快照 + 之前的错误链接），重建
  rm -rf "$dst_dir"
  mkdir -p "$dst_dir"

  for sk in $SHARED "$@"; do
    local src="$AUTHORITY_DIR/$sk"
    local dst="$dst_dir/$sk"
    if [ -d "$src" ]; then
      ln -s "$src" "$dst" && { echo "  ✓ $sk"; ok=$((ok+1)); } || { echo "  ✗ $sk (链接失败)"; fail=$((fail+1)); }
    else
      echo "  ✗ $sk (权威源不存在)"; fail=$((fail+1))
    fi
  done
  echo "  → $node: $ok 成功, $fail 失败"
}

echo "══════════════════════════════════════════"
echo "软链同步 (权威源: $AUTHORITY_DIR)"
echo "══════════════════════════════════════════"

# 在这里列出你的节点（按需增删）
# link_node node1 common-skill-a common-skill-b
# link_node node2 common-skill-b
# link_node node3 common-skill-a common-skill-c

echo ""
echo "══════════════════════════════════════════"
echo "同步完成。验证: 检查各节点 skills 是否为符号链接"
echo "══════════════════════════════════════════"
