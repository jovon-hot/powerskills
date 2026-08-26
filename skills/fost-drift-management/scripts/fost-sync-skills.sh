#!/bin/bash
# FOST 多 Agent skill 同步脚本
# 单一数据源: CEO 目录 ~/.hermes/profiles/fost-ceo/skills/fost/
# 机制: 各子 agent 的 skills/fost/ 用符号链接指向 CEO 权威版，改一处处处生效
# 用法: bash fost-sync-skills.sh
set -u

CEO_DIR="$HOME/.hermes/profiles/fost-ceo/skills/fost"
SHARED="fost-sql-cheatsheet fost-data-cleaning fost-env fost-info-governance"

# 每个 agent 的专属 skill（空格分隔）。bash 3.2 兼容，不用关联数组。
link_agent() {
  local agent="$1"; shift
  local dst_dir="$HOME/.hermes/profiles/$agent/skills/fost"
  local ok=0 fail=0

  # 清空旧目录（旧快照 + 之前的错误链接），重建
  rm -rf "$dst_dir"
  mkdir -p "$dst_dir"

  for sk in $SHARED "$@"; do
    local src="$CEO_DIR/$sk"
    local dst="$dst_dir/$sk"
    if [ -d "$src" ]; then
      ln -s "$src" "$dst" && { echo "  ✓ $sk"; ok=$((ok+1)); } || { echo "  ✗ $sk (链接失败)"; fail=$((fail+1)); }
    else
      echo "  ✗ $sk (源不存在)"; fail=$((fail+1))
    fi
  done
  echo "  → $agent: $ok 成功, $fail 失败"
}

echo "══════════════════════════════════════════"
echo "FOST skill 同步 (权威源: fost-ceo)"
echo "══════════════════════════════════════════"

echo ""
echo "[fost-data] 数据: cheatsheet + 清洗 + data"
link_agent fost-data fost-data

echo ""
echo "[fost-hr] 人事: cheatsheet + 清洗 + hr"
link_agent fost-hr fost-hr

echo ""
echo "[fost-coo] 运营: cheatsheet + 清洗 + coo"
link_agent fost-coo fost-coo

echo ""
echo "[fost-cmo] 市场: cheatsheet + cmo"
link_agent fost-cmo fost-cmo

echo ""
echo "[fost-compliance] 合规: cheatsheet + compliance"
link_agent fost-compliance fost-compliance

echo ""
echo "[fost-cfo] 财务: cheatsheet + 清洗 + cfo + 对账"
link_agent fost-cfo fost-cfo fost-reconciliation fost-payment-reconciliation

echo ""
echo "[fost-auditor] 审计: cheatsheet + 清洗 + data-auditor + audit-pipeline"
link_agent fost-auditor fost-data-auditor fost-audit-pipeline

echo ""
echo "[fost-legal] 法律: cheatsheet + 清洗 + legal"
link_agent fost-legal fost-legal

echo ""
echo "[fost-recon] 对账: cheatsheet + 清洗 + payment-reconciliation + info-governance（独有 wecom 补丁保留实体）"
link_agent fost-recon fost-payment-reconciliation fost-info-governance fost-reconciliation fost-sql-cheatsheet fost-data-cleaning
# recon 独有的 wecom 补丁 skill 保留实体（不软链，CEO 无此 skill）
# wecom-media-patch / wecom-cron-delivery 留在 recon 实体目录
for sk in wecom-media-patch wecom-cron-delivery; do
  if [ -d "$HOME/.hermes/profiles/fost-recon/_disabled_skills_bak_20260825/$sk" ]; then
    mv "$HOME/.hermes/profiles/fost-recon/_disabled_skills_bak_20260825/$sk" "$HOME/.hermes/profiles/fost-recon/skills/fost/$sk"
    echo "  → 恢复 recon 独有: $sk"
  fi
done

echo ""
echo "══════════════════════════════════════════"
echo "同步完成。验证: hermes -p <agent> skills list | grep fost"
echo "══════════════════════════════════════════"
