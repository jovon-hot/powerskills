#!/usr/bin/env python3
"""
Token 消耗体检 · 零配置自动探测版
输出 JSON 到 stdout（供 agent 按阈值判定）。

收集：input/output/total token、成本、重放倍数、最肥会话、最肥工具、大知识文件、会话轮换配置。

用法：
  python3 token_health_check.py            # 默认近 7 天
  python3 token_health_check.py --days 30  # 近 30 天

零配置：自动探测 agent 平台的数据目录（环境变量、~/.hermes、~/.config 等常见布局），
无需用户提供任何路径或配置。只读：所有数据库查询均以只读模式打开。
"""
import glob
import json
import os
import re
import sqlite3
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
DEFAULT_DAYS = 7
BIG_FILE_KB = 20  # 超过此阈值的知识文件判定为"过大"，建议拆分


def detect_home():
    """自动探测 agent 数据目录（支持多种平台布局）"""
    candidates = [
        os.environ.get("AGENT_HOME"),
        os.environ.get("HERMES_HOME"),
        os.path.join(HOME, ".hermes"),
        os.path.join(HOME, ".config", "hermes"),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return None


def find_state_db(home):
    """自动找会话状态库（profile 布局或单库布局）"""
    if not home:
        return []
    prof = os.path.join(home, "profiles")
    if os.path.isdir(prof):
        dbs = glob.glob(os.path.join(prof, "**", "state.db"), recursive=True)
        if dbs:
            return dbs  # 返回所有（多 profile 都查）
    single = os.path.join(home, "state.db")
    if os.path.exists(single):
        return [single]
    return []


def run_insights(days):
    """跑平台 insights 命令拿权威数字（若存在）"""
    for cmd in (["hermes", "insights"], ["agent", "insights"]):
        try:
            r = subprocess.run(cmd + ["--days", str(days)],
                               capture_output=True, text=True, timeout=180)
            if r.returncode == 0 and r.stdout:
                return r.stdout
        except Exception:
            continue
    return None


def parse_insights(text):
    """从 insights 文本提取关键数字"""
    result = {}
    if not text:
        return result
    m = re.search(r"Input tokens:\s+([\d,]+)", text)
    if m:
        result["input_tokens"] = int(m.group(1).replace(",", ""))
    m = re.search(r"Output tokens:\s+([\d,]+)", text)
    if m:
        result["output_tokens"] = int(m.group(1).replace(",", ""))
    m = re.search(r"Total tokens:\s+([\d,]+)", text)
    if m:
        result["total_tokens"] = int(m.group(1).replace(",", ""))
    m = re.search(r"Estimated:\s*~\$([\d.]+)", text)
    if m:
        result["cost_est"] = float(m.group(1))
    if result.get("input_tokens") and result.get("total_tokens"):
        result["replay_multiplier"] = round(result["total_tokens"] / result["input_tokens"], 1)
    return result


def session_attribution(dbs, cutoff_epoch):
    """会话级归因：近 N 天内按会话汇总字符量"""
    result = []
    for db in dbs or []:
        try:
            conn = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT session_id,
                       MIN(timestamp) start_ts, MAX(timestamp) end_ts,
                       SUM(LENGTH(content)) total_chars, COUNT(*) n_msgs,
                       SUM(CASE WHEN role='tool' THEN LENGTH(content) ELSE 0 END) tool_chars
                FROM messages
                WHERE timestamp >= ?
                GROUP BY session_id
                ORDER BY total_chars DESC LIMIT 10
                """,
                (cutoff_epoch,),
            )
            for row in cur.fetchall():
                result.append({
                    "session_id": row[0], "start": row[1], "end": row[2],
                    "total_chars": row[3], "n_msgs": row[4], "tool_chars": row[5],
                    "db": os.path.basename(os.path.dirname(db)),
                })
            conn.close()
        except Exception:
            continue
    return result


def tool_attribution(dbs, cutoff_epoch):
    """工具级归因：定位最肥工具"""
    result = []
    for db in dbs or []:
        try:
            conn = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT tool_name, COUNT(*), SUM(LENGTH(content)), MAX(LENGTH(content))
                FROM messages
                WHERE role='tool' AND tool_name IS NOT NULL AND timestamp >= ?
                GROUP BY tool_name ORDER BY SUM(LENGTH(content)) DESC LIMIT 10
                """,
                (cutoff_epoch,),
            )
            for row in cur.fetchall():
                result.append({
                    "tool": row[0], "calls": row[1],
                    "total_chars": row[2], "max_chars": row[3],
                    "db": os.path.basename(os.path.dirname(db)),
                })
            conn.close()
        except Exception:
            continue
    return result


def find_skill_roots(home):
    """定位知识文件根：标准布局优先，找不到才退回 home 全扫"""
    roots = []
    for p in (os.path.join(home, "skills"), os.path.join(home, "profiles")):
        if os.path.isdir(p):
            roots.append(p)
    if not roots and os.path.isdir(home):
        roots.append(home)
    return roots


def big_skills(home):
    """找 >20KB 的知识文件（按 SKILL.md/README.md 判定）"""
    seen = {}
    if not home:
        return []
    for root in find_skill_roots(home):
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f in ("SKILL.md", "README.md"):
                    p = os.path.join(dirpath, f)
                    try:
                        size = os.path.getsize(p)
                    except Exception:
                        continue
                    if size > BIG_FILE_KB * 1024:
                        seen[p] = {
                            "skill": os.path.basename(dirpath),
                            "size_kb": round(size / 1024),
                        }
    return sorted(seen.values(), key=lambda x: -x["size_kb"])[:15]


def check_session_reset(home):
    """检查会话轮换配置是否已设置（只读，限深 4 层）"""
    found = []
    patterns = ["session_reset", "idle_minutes", "at_hour", "auto_reset"]
    if not home:
        return None
    for dirpath, dirs, files in os.walk(home):
        depth = dirpath[len(home):].count(os.sep)
        if depth > 4:
            dirs[:] = []
            continue
        for f in files:
            if not re.match(r"config.*\.(ya?ml|json)$", f):
                continue
            p = os.path.join(dirpath, f)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            except Exception:
                continue
            hits = [k for k in patterns if k in text.lower()]
            if hits:
                found.append({"file": os.path.relpath(p, home), "keys": hits})
    return found or None


def main():
    days = DEFAULT_DAYS
    argv = sys.argv[1:]
    while argv:
        a = argv.pop(0)
        if a == "--days" and argv:
            try:
                days = int(argv.pop(0))
            except ValueError:
                pass
    cutoff_epoch = time.time() - days * 86400
    home = detect_home()
    dbs = find_state_db(home)
    insights_text = run_insights(days)
    result = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "days": days,
        "home_detected": home,
        "state_dbs": len(dbs),
        "insights": parse_insights(insights_text),
        "top_sessions": session_attribution(dbs, cutoff_epoch),
        "top_tools": tool_attribution(dbs, cutoff_epoch),
        "big_skills": big_skills(home),
        "session_reset": check_session_reset(home),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
