#!/usr/bin/env python3
"""
生成 GitHub Top 3 项目的中文简介和爆火原因分析
使用 DeepSeek API（复用已有的环境变量配置）
输出：intros.json（与 trending.html 同目录）
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import os
import time
import datetime

# ── 配置 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "intros.json")

# DeepSeek API（使用与 claude code 相同的凭据）
API_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL_NAME = "deepseek-chat"

# GitHub 搜索参数
SEARCH_DAYS = 30
TOP_N = 3


def github_top_repos(n=TOP_N):
    """从 GitHub Search API 获取近 N 天的 Top N 热门项目"""
    since = (datetime.date.today() - datetime.timedelta(days=SEARCH_DAYS)).isoformat()
    query = f"created:>{since}"
    url = (f"https://api.github.com/search/repositories?"
           f"q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page={n}")

    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "trending-intro-generator/1.0",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    repos = []
    for r in data.get("items", [])[:n]:
        created = datetime.datetime.strptime(r["created_at"][:10], "%Y-%m-%d").date()
        days_ago = (datetime.date.today() - created).days
        repos.append({
            "full_name": r["full_name"],
            "description": r.get("description") or "暂无简介",
            "language": r.get("language") or "Unknown",
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
            "url": r["html_url"],
            "created_at": r["created_at"][:10],
            "days_ago": days_ago,
        })
    return repos


def call_llm(prompt, max_tokens=400):
    """调用 DeepSeek API（OpenAI 兼容格式）"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",
    }
    body = {
        "model": MODEL_NAME,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}],
    }
    req_url = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req_url, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            choices = result.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            raise RuntimeError(f"API 返回异常: {json.dumps(result, ensure_ascii=False)[:300]}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:300] if e.fp else ""
        raise RuntimeError(f"API 错误 {e.code}: {err_body}")


def generate_intro(repo):
    """为单个仓库生成中文简介和爆火原因"""
    prompt = f"""你是一位资深技术分析师，为 GitHub 热门项目撰写中文洞察报告。

项目信息：
- 名称：{repo['full_name']}
- 语言：{repo['language']}
- 描述：{repo['description']}
- Stars：{repo['stars']:,}（{repo['days_ago']} 天内获得）
- Forks：{repo['forks']:,}

请深入分析并用 JSON 返回（不要额外内容）：
{{
  "intro": "项目功能介绍（100-150字）。写清楚：这个项目是什么、解决什么具体问题、面向什么用户。要具体，不要说空泛的套话。",
  "why_hot": "爆火原因分析（80-100字）。必须结合以下至少两点来分析：1) 当前技术趋势或行业热点 2) 它解决了什么具体痛点 3) 目标用户群体或社区推动。禁止说'获得了极高关注度'之类没有信息量的空话，必须给出具体原因。"
}}"""

    print(f"    生成 {repo['full_name']} 的中文简介...")
    for attempt in range(3):
        try:
            text = call_llm(prompt, max_tokens=600).strip()
            # 提取 JSON
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except (json.JSONDecodeError, RuntimeError) as e:
            if attempt < 2:
                time.sleep(2)
                continue
            print(f"    [警告] 生成失败 ({e})")
            return {"intro": "生成失败，请稍后重试", "why_hot": f"该项目在 {repo['days_ago']} 天内获得了 {repo['stars']:,} 颗 Star，增速惊人"}
    return {"intro": "生成失败", "why_hot": "数据异常"}


def main():
    if not API_TOKEN:
        print("❌ 未检测到 ANTHROPIC_AUTH_TOKEN 环境变量")
        print("   请先设置：export ANTHROPIC_AUTH_TOKEN=<你的 DeepSeek API Key>")
        return 1

    print("=" * 55)
    print("  🤖 GitHub Top 3 中文简介生成器")
    print("=" * 55)

    # 1. 获取热门项目
    print("\n📡 获取 GitHub 热门项目...")
    repos = github_top_repos(TOP_N)
    for i, r in enumerate(repos):
        print(f"  #{i+1} {r['full_name']} ★{r['stars']:,}")

    # 2. 生成中文简介
    print(f"\n🧠 使用 {MODEL_NAME} 生成中文简介...")
    result = {"updated": datetime.datetime.now().isoformat(), "repos": {}}
    for r in repos:
        r["intro_data"] = generate_intro(r)
        result["repos"][r["full_name"]] = r["intro_data"]

    # 3. 输出
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已生成: {OUTPUT_FILE}")

    # 预览
    print("\n📋 预览：")
    for r in repos:
        intro = r["intro_data"]
        print(f"\n  ┌─ #{repos.index(r)+1} {r['full_name']}")
        print(f"  ├─ 简介: {intro['intro']}")
        print(f"  └─ 为何火: {intro['why_hot']}")

    print(f"\n💡 下次想看中文分析时，刷新网页即可（它会加载 intros.json）")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
