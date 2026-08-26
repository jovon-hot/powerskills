#!/usr/bin/env python3
"""
漂移巡检脚本（通用版）— 检测三类漂移：
1. 文件软链漂移：各节点是否用实体副本（应软链/引用指向权威源）
2. 文件内容漂移：实体副本与权威版本不一致
3. 任务快照漂移：job 配置快照与全局配置不匹配（静默跳过风险）
4. 记忆副本漂移：记忆里是否有"事实副本"（应指向数据源）

⚠️ 用法：先改下方【配置区】适配你的环境，再运行。
输出 JSON 到 stdout（供分级报告）。
"""
import os, json, re, sys
from datetime import datetime

# ═══════════════ 配置区（按你的环境修改）═══════════════
# 你的所有节点/角色目录名（主控节点也列出，脚本会跳过它）
PROFILES = ["main", "node1", "node2", "node3"]   # ← 改成你的节点列表
# 权威源目录（唯一物理位置，其他节点全部软链指向这里）
AUTHORITY = os.path.join(os.path.expanduser("~"), ".hermes", "profiles", "main", "skills", "shared")
# 各节点共享文件所在子目录（相对 profile 目录）
SHARED_SUBDIR = ["skills", "shared"]
# 检查任务快照的节点（通常主控 + 跑任务的节点）
JOB_PROFILES = ["main"]
# 全局配置允许的模型集合（改成你的）
ALLOWED_MODELS = [None, "flash", "pro"]
# 记忆文件位置（相对 profile 目录）
MEMORY_REL = ["memories", "MEMORY.md"]
# ════════════════════════════════════════════════════

HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, ".hermes", "profiles")

def node_shared_dir(p):
    return os.path.join(BASE, p, *SHARED_SUBDIR)

def check_file_drift():
    """检查各节点共享文件的软链状态 + 实体漂移"""
    result = []
    for p in PROFILES:
        shared = node_shared_dir(p)
        if not os.path.isdir(shared):
            continue
        items = [i for i in os.listdir(shared) if not i.startswith('.')]
        real_items = [i for i in items if os.path.isdir(os.path.join(shared, i)) and not os.path.islink(os.path.join(shared, i))]
        if p == os.path.basename(AUTHORITY).replace("profiles", "").strip("/") and p == PROFILES[0]:
            continue  # 权威源本身是实体，跳过
        entry = {"profile": p, "total": len(items), "real": len(real_items),
                 "link": len(items) - len(real_items), "drifted": []}
        for i in sorted(real_items):
            local = os.path.join(shared, i, "SKILL.md")
            auth = os.path.join(AUTHORITY, i, "SKILL.md")
            if os.path.exists(local) and os.path.exists(auth):
                if os.path.getsize(local) != os.path.getsize(auth):
                    entry["drifted"].append({"file": i, "local_size": os.path.getsize(local), "authority_size": os.path.getsize(auth)})
            elif os.path.exists(local) and not os.path.exists(auth):
                entry["drifted"].append({"file": i, "note": "权威目录无此文件(节点独有)"})
        result.append(entry)
    return result

def check_job_snapshot():
    """检查任务配置快照 vs 全局模型"""
    result = []
    for p in JOB_PROFILES:
        jp = os.path.join(BASE, p, "cron", "jobs.json")
        if not os.path.exists(jp):
            continue
        with open(jp, encoding='utf-8') as f:
            d = json.load(f)
        jobs = d if isinstance(d, list) else d.get('jobs', [])
        for j in jobs:
            if j.get('enabled'):
                snap = j.get('model_snapshot')
                if snap and snap not in ALLOWED_MODELS:
                    result.append({"job": j.get('name'), "snapshot": snap, "note": "未知/不匹配配置，需检查"})
    return result

def check_memory_copy():
    """检查记忆里是否有事实副本（含具体编码/金额/费率明细）"""
    result = []
    copy_patterns = [
        (r'\b[a-z_]+\s*=\s*[A-Z0-9]{2,}', "编码副本"),
        (r'¥[\d,]+', "金额明细"),
        (r'0\.\d{2}%', "费率明细"),
    ]
    for p in PROFILES:
        mem = os.path.join(BASE, p, *MEMORY_REL)
        if not os.path.exists(mem):
            continue
        with open(mem, encoding='utf-8') as f:
            content = f.read()
        for pat, label in copy_patterns:
            if re.search(pat, content):
                result.append({"profile": p, "type": label, "note": f"记忆含 {label}，需确认是指向还是副本"})
                break
    return result

def main():
    result = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "file_drift": check_file_drift(),
        "job_drift": check_job_snapshot(),
        "memory_copy": check_memory_copy(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
