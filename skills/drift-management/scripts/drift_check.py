#!/usr/bin/env python3
"""
漂移巡检脚本（自动探测版）— 检测信息漂移，无需任何配置。

自动做三件事：
1. 扫描默认 profiles 目录下所有节点，输出候选权威源（实体文件最多的 top5）
2. 对比各节点的共享文件目录：实体副本 vs 软链，找内容漂移
3. 检查定时任务配置快照与全局配置是否匹配

用法：python3 drift_check.py   （零参数，全自动）
输出：JSON 到 stdout，供分级报告。
"""
import os, json, re, glob
from datetime import datetime

HOME = os.path.expanduser("~")
# 默认节点目录（可改成你的：agent 平台、角色目录、配置中心根路径）
PROFILES_ROOT = os.path.join(HOME, ".hermes", "profiles")

# 约定：共享 skill 目录名（各 profile 下的分类目录）
SHARED_CATEGORIES = ["fost", "shared", "skills"]  # 常见命名

def find_profiles():
    """自动发现所有 profile"""
    if not os.path.isdir(PROFILES_ROOT):
        return []
    return [d for d in os.listdir(PROFILES_ROOT)
            if os.path.isdir(os.path.join(PROFILES_ROOT, d))]

def find_authority(profiles):
    """
    自动发现"候选权威源"（不做最终决定，判断归 agent）：
    - 返回实体共享 skill 目录最多的 3 个 profile + 名字含 ceo/main 的
    - agent 根据上下文决定哪个是权威（如 FOST 体系选 fost-ceo）
    """
    candidates = []
    for p in profiles:
        cnt = count_real_shared(p)
        if cnt > 0:
            candidates.append({"profile": p, "real_skills": cnt})
    candidates.sort(key=lambda x: x["real_skills"], reverse=True)
    # 名字优先的也加入
    for p in profiles:
        if any(prio in p for prio in ["ceo", "main", "master"]):
            if not any(c["profile"] == p for c in candidates):
                candidates.append({"profile": p, "real_skills": count_real_shared(p)})
    return candidates[:5]  # top5 候选

def profile_shared_dirs(p):
    """一个 profile 下的所有共享 skill 分类目录"""
    base = os.path.join(PROFILES_ROOT, p, "skills")
    if not os.path.isdir(base):
        return []
    return [d for d in os.listdir(base)
            if os.path.isdir(os.path.join(base, d)) and not d.startswith(".")]

def count_real_shared(p):
    """统计该 profile 共享目录里的实体（非软链）skill 数"""
    total = 0
    for cat in profile_shared_dirs(p):
        cat_dir = os.path.join(PROFILES_ROOT, p, "skills", cat)
        for item in os.listdir(cat_dir):
            full = os.path.join(cat_dir, item)
            if os.path.isdir(full) and not os.path.islink(full):
                total += 1
    return total

def check_drift(profiles, authority):
    """对比各 profile 与权威源的软链/实体状态"""
    result = []
    auth_cats = profile_shared_dirs(authority)
    for p in profiles:
        if p == authority:
            continue
        entry = {"profile": p, "shared_categories": [], "real_files": [], "drifted": []}
        for cat in profile_shared_dirs(p):
            cat_dir = os.path.join(PROFILES_ROOT, p, "skills", cat)
            real_items = [i for i in os.listdir(cat_dir)
                          if os.path.isdir(os.path.join(cat_dir, i)) and not os.path.islink(os.path.join(cat_dir, i))]
            if real_items:
                entry["shared_categories"].append(cat)
                entry["real_files"].extend(real_items)
                # 内容对比：找权威源同名的 SKILL.md
                for sk in real_items:
                    local_skill = os.path.join(cat_dir, sk, "SKILL.md")
                    # 权威源里同名 skill（任一分类）
                    auth_match = None
                    for acat in auth_cats:
                        cand = os.path.join(PROFILES_ROOT, authority, "skills", acat, sk, "SKILL.md")
                        if os.path.exists(cand):
                            auth_match = cand
                            break
                    if auth_match and os.path.exists(local_skill):
                        lsz = os.path.getsize(local_skill)
                        asz = os.path.getsize(auth_match)
                        if lsz != asz:
                            entry["drifted"].append({"skill": sk, "local_size": lsz, "authority_size": asz})
                    elif auth_match is None:
                        entry["drifted"].append({"skill": sk, "note": "权威源无同名(该节点独有)"})
        result.append(entry)
    return result

def check_cron_snapshot(profiles):
    """检查 cron 任务快照 vs 全局模型（自动探测）"""
    result = []
    allowed_models = None  # 自动探测
    for p in profiles:
        jp = os.path.join(PROFILES_ROOT, p, "cron", "jobs.json")
        if not os.path.exists(jp):
            continue
        with open(jp, encoding='utf-8') as f:
            d = json.load(f)
        jobs = d if isinstance(d, list) else d.get('jobs', [])
        for j in jobs:
            if j.get('enabled'):
                snap = j.get('model_snapshot')
                if snap:  # 有快照 = 需要与全局比对，这里只标记待检查
                    result.append({"profile": p, "job": j.get('name'), "snapshot": snap})
    return result

def check_memory_copy(profiles):
    """检查记忆里是否有事实副本（编码/金额/费率明细 = 副本风险）"""
    result = []
    copy_patterns = [
        (r'\b[a-z_]+\s*=\s*[A-Z0-9]{2,}', "编码副本"),
        (r'¥[\d,]+', "金额明细"),
        (r'0\.\d{2}%', "费率明细"),
    ]
    for p in profiles:
        mem = os.path.join(PROFILES_ROOT, p, "memories", "MEMORY.md")
        if not os.path.exists(mem):
            continue
        with open(mem, encoding='utf-8') as f:
            content = f.read()
        for pat, label in copy_patterns:
            if re.search(pat, content):
                result.append({"profile": p, "type": label})
                break
    return result

def main():
    profiles = find_profiles()
    candidates = find_authority(profiles) if profiles else []
    # 探测归脚本、判断归 agent：候选权威源列表交给调用方
    result = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "profiles_found": len(profiles),
        "authority_candidates": candidates,
        "file_drift": check_drift(profiles, candidates[0]["profile"]) if candidates else [],
        "cron_snapshot": check_cron_snapshot(profiles),
        "memory_copy": check_memory_copy(profiles),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
