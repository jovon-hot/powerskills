---
name: fost-drift-management
description: Use when 检测/分析/对齐/修复信息漂移（skill副本/cron快照/memory副本/数据口径）。
version: 1.0.0
author: FOST AGENCY
platforms: [macos, linux]
tags: [fost, drift, sync, alignment, governance, 漂移]
---

# FOST 漂移管理（发现→分析→对齐→修复）

## 触发场景

- 定期巡检（周度）信息体系漂移
- 发现 skill 副本不一致 / cron 静默跳过 / memory 有旧认知
- 老板追问"为什么这里和那里不一样"
- 模型切换后 cron 不跑

## 核心认知

**漂移的本质 = 同一信息存在多个物理/逻辑副本，且副本间无自动同步。** 谁改了一处，其他处就旧了。不是偶发 bug，是系统性风险。

**四类漂移**：
| 类型 | 机制 | 防治理 |
|------|------|--------|
| 物理副本 | 实体复制 skill/memory，CEO 改动不同步 | 软链同步（唯一物理位置） |
| 配置快照 | job 创建时 snapshot 模型，全局切换后不匹配 | 切换后全量检查 |
| 语义认知 | 对事实的理解漂移 | 事实进库表 + 唯一入库口 |
| 数据口径 | 多数据源天然口径不同 | 视图固化 + 交叉校验 |

## 工作流（发现→分析→对齐→修复）

### 第 1 步：发现（脚本巡检）

```bash
python3 ~/Desktop/hdlib/30-scripts/fost/drift_check.py
```

输出 JSON：
- `skill_drift`：各 profile skills/fost 软链状态（实体副本 = 风险）+ 实体内容与 CEO 版本差异
- `cron_drift`：job model_snapshot 与全局模型不匹配（drift_skip 风险）
- `memory_copy`：memory 含编码/金额/费率明细（需确认是指向还是副本）

### 第 2 步：分析（判定严重度）

| 发现 | 级别 | 说明 |
|------|------|------|
| 子 agent skill 实体副本 | 🟡 警告 | CEO 改 skill 不同步，内容会旧 |
| 实体副本且内容与 CEO 不一致 | 🔴 危险 | 已在漂移，需对齐 |
| cron model_snapshot ≠ 全局模型 | 🔴 危险 | job 会 drift_skip 静默不跑 |
| memory 含明细副本 | 🟡 警告 | 违反副本禁令，需改指向 |

### 第 3 步：对齐（改软链 / 修 snapshot）

```bash
# ① 子 agent skill 对齐为软链（权威源 = CEO）
bash ~/Desktop/hdlib/30-scripts/fost/fost-sync-skills.sh

# ② cron snapshot 对齐（直接改 jobs.json）
# 把 model_snapshot 改为当前全局模型，然后重启 gateway
# 例：deepseek-v4-pro → deepseek-v4-flash

# ③ memory 副本改指向
# 把"XX 编码是 YY"改为"XX 编码 → 查 field_dictionary 表"
```

### 第 4 步：修复（验证闭环）

- 重跑 drift_check.py 确认所有漂移清零
- 验证受影响功能正常（如 cron 手动触发一次）
- 更新 fost-info-governance 权威源清单（新增事实/逻辑）

## 历史案例（2026-08-26 实战）

- **fost-recon 47 个实体 skill**（17 个漂移，最严重 report-generation 差 111KB）→ 改软链后根治
- **文档监控 cron drift_skip**：model_snapshot=pro 但全局切 flash → job 静默不跑 3 天 → 改 snapshot + 重启 gateway 修复
- **福司特张店 vs 齐商共青团**：误判"新旧名"合并（实际独立账户 8/19 共存）→ 语义认知漂移，靠老板纠正 + 事实落库
- **CFO memory 旧认知**："206源端+93镜像"与新铁律"206不可写"矛盾 → 修正 memory

## 坑

1. **sync 脚本会 rm -rf 目标目录**：跑之前先备份子 agent 独有的 skill（不在 CEO 目录的）
2. **recon 有 2 个独有 skill**（wecom-media-patch / wecom-cron-delivery）：放 `skills/wecom-patches/` 避免被同步脚本清掉
3. **drift_skip 是静默的**：job 不跑但不报错，靠巡检才能发现——模型切换后必须查 snapshot
4. **memory 副本 vs 指向的判定**：出现具体编码/金额/费率 = 副本（违规）；"查 XX 表" = 指向（合规）
5. **漂移巡检要定期跑**：建议并入 token 体检 cron（每周一），或单独 cron

## 支撑文件

- `~/Desktop/hdlib/30-scripts/fost/drift_check.py` — 漂移巡检脚本（skill 软链 + cron snapshot + memory 副本）
- `~/Desktop/hdlib/30-scripts/fost/fost-sync-skills.sh` — skill 软链同步脚本（权威源 = CEO）
- `fost-info-governance` — 信息治理规范（三层载体/单一入库口/副本禁令/206铁律）
