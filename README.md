# powerskills

实战沉淀的可复用 skills 包 —— 多角色信息体系运维经验。

## 目录

| Skill | 用途 | 状态 |
|-------|------|------|
| drift-management | 信息漂移检测/分析/对齐/修复（零配置自动探测，适配任意节点体系） | ✅ v2.0 2026-08 |
| token-reduction | token 消耗诊断/归因/按ROI优化/验证（零配置体检脚本，先量化再动手） | ✅ v1.0 2026-08 |

## 使用

每个 skill 目录包含 `SKILL.md`（方法论）+ `scripts/`（自动脚本）。
**零配置**：脚本自动探测你的环境，无需手动适配。复制到你的 skills 目录即可用。

```bash
git clone https://github.com/jovon-hot/powerskills.git
# 把需要的 skill 目录复制到你的 agent skills 目录
cp -r powerskills/drift-management ~/.your-agent/skills/
```

## 设计原则

- 不绑定具体平台/角色数量/目录结构
- 脚本自动探测（发现节点 → 候选权威源 → 对比漂移），判断归 agent
- 通用原则：事实进数据源 / 逻辑进视图 / 流程进文件 / 记忆只留指向
