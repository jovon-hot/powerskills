#!/usr/bin/env python3
"""
FOST 漂移巡检脚本 — 检测三类漂移：
1. Skill 软链漂移：各子 agent skills/fost 是否实体副本（应软链指向 CEO 权威源）
2. Skill 内容漂移：实体副本与 CEO 版本大小/内容不一致
3. Cron snapshot 漂移：job model_snapshot 与全局模型不匹配（drift_skip 风险）
4. Memory 副本漂移：memory 里是否有"事实副本"（应指向库表）
输出 JSON 到 stdout（供 agent 分级报告）。
"""
import os, json, re, sys, subprocess
from datetime import datetime

HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, ".hermes", "profiles")
PROFILES = ["fost-ceo","fost-cfo","fost-coo","fost-cmo","fost-compliance","fost-data","fost-hr","fost-auditor","fost-legal","fost-recon"]
CEO = os.path.join(BASE, "fost-ceo", "skills", "fost")

def check_skill_drift():
    """检查各 profile skills/fost 的软链状态 + 实体漂移"""
    result = []
    for p in PROFILES:
        fost_dir = os.path.join(BASE, p, "skills", "fost")
        if not os.path.isdir(fost_dir):
            continue
        items = [i for i in os.listdir(fost_dir) if not i.startswith('.')]
        real_items = [i for i in items if os.path.isdir(os.path.join(fost_dir, i)) and not os.path.islink(os.path.join(fost_dir, i))]
        if p == "fost-ceo":
            # CEO 是权威源，本身实体正常
            continue
        entry = {"profile": p, "total": len(items), "real": len(real_items),
                 "link": len(items) - len(real_items), "drifted": []}
        for i in sorted(real_items):
            rp = os.path.join(fost_dir, i, "SKILL.md")
            cp = os.path.join(CEO, i, "SKILL.md")
            if os.path.exists(rp) and os.path.exists(cp):
                if os.path.getsize(rp) != os.path.getsize(cp):
                    entry["drifted"].append({"skill": i, "recon_size": os.path.getsize(rp), "ceo_size": os.path.getsize(cp)})
            elif os.path.exists(rp) and not os.path.exists(cp):
                entry["drifted"].append({"skill": i, "note": "CEO无此skill(recon独有)"})
        result.append(entry)
    return result

def check_cron_snapshot():
    """检查 cron model_snapshot vs 全局模型"""
    result = []
    for p in ["fost-ceo", "fost-recon"]:
        jp = os.path.join(BASE, p, "cron", "jobs.json")
        if not os.path.exists(jp):
            continue
        with open(jp, encoding='utf-8') as f:
            d = json.load(f)
        jobs = d if isinstance(d, list) else d.get('jobs', [])
        for j in jobs:
            if j.get('enabled'):
                snap = j.get('model_snapshot')
                # 全局模型：查 config（简化：允许的集合）
                if snap and snap not in (None, 'deepseek-v4-flash', 'deepseek-v4-pro', 'ark-code-latest'):
                    result.append({"job": j.get('name'), "snapshot": snap, "note": "未知模型，需检查"})
    return result

def check_memory_copy():
    """检查 memory 里是否有事实副本（含具体编码/金额明细）"""
    result = []
    copy_patterns = [
        (r'\b[a-z_]+\s*=\s*[A-Z0-9]{2,}', "编码副本"),
        (r'¥[\d,]+', "金额明细"),
        (r'0\.\d{2}%', "费率明细"),
    ]
    for p in PROFILES:
        mem = os.path.join(BASE, p, "memories", "MEMORY.md")
        if not os.path.exists(mem):
            continue
        with open(mem, encoding='utf-8') as f:
            content = f.read()
        for pat, label in copy_patterns:
            if re.search(pat, content):
                result.append({"profile": p, "type": label, "note": f"memory 含 {label}，需确认是指向还是副本"})
                break
    return result

def main():
    result = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "skill_drift": check_skill_drift(),
        "cron_drift": check_cron_snapshot(),
        "memory_copy": check_memory_copy(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
