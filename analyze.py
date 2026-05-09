#!/usr/bin/env python3
"""
GitHub 仓库 Star 趋势分析工具
只用 Python 内置库，无需额外安装依赖
"""

import urllib.request
import urllib.error
import json
import os
import time
import datetime
import webbrowser

# ── 配置：你想分析哪些仓库 ──
REPOS = [
    "facebook/react",
    "vuejs/vue",
    "torvalds/linux",
    "microsoft/vscode",
    "rust-lang/rust",
]

OUTPUT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.html")


def api_get(path, retries=3):
    """调用 GitHub REST API，返回解析后的 JSON"""
    url = f"https://api.github.com/{path}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "github-stats-analyzer/1.0",
                "Accept": "application/vnd.github.v3+json",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 403 and attempt < retries - 1:
                time.sleep(2)
                continue
            print(f"  [错误] HTTP {e.code} → {url}")
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            print(f"  [错误] 网络问题 → {url}: {e}")
            return None
    return None


def fetch_repo_stats(full_name):
    """获取单个仓库的基础信息"""
    print(f"  获取 {full_name} …", end=" ", flush=True)
    data = api_get(f"repos/{full_name}")
    if data is None:
        print("失败")
        return None
    stars = data.get("stargazers_count", 0)
    forks = data.get("forks_count", 0)
    issues = data.get("open_issues_count", 0)
    lang = data.get("language", "N/A")
    desc = (data.get("description") or "（无描述）")[:80]
    created = data.get("created_at", "")[:10]
    pushed = data.get("pushed_at", "")[:10]
    print(f"★ {stars}")
    return {
        "name": full_name.split("/")[-1],
        "full_name": full_name,
        "stars": stars,
        "forks": forks,
        "issues": issues,
        "language": lang,
        "description": desc,
        "created": created,
        "pushed": pushed,
    }


def fetch_star_history(full_name):
    """
    获取近 30 天的 star 增长记录
    使用 gh-trending 的 star-history API（无认证）
    """
    url = f"https://star-history.imbee.im/api/stats?owner={full_name.split('/')[0]}&name={full_name.split('/')[1]}"
    req = urllib.request.Request(url, headers={"User-Agent": "github-stats-analyzer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            # 数据格式：[{date, starNum}, ...]
            return [(d["date"], d["starNum"]) for d in data]
    except Exception:
        return None


# ── 终端显示 ──

def print_header(title):
    print(f"\n{'═' * 55}")
    print(f"  {title}")
    print(f"{'═' * 55}")


def print_bar(label, value, max_value, width=35):
    """打印终端横向柱状图"""
    bar_len = int(value / max_value * width) if max_value else 0
    bar = "█" * bar_len + "░" * (width - bar_len)
    print(f"  {label:<12} │{bar}│ {value:>8,}")


def terminal_report(stats_list):
    """在终端输出分析报告"""
    if not stats_list:
        print("没有数据可显示")
        return

    # 按 star 数从高到低排序
    stats_list = sorted(stats_list, key=lambda s: s["stars"], reverse=True)
    max_star = stats_list[0]["stars"]

    print_header("📊 GitHub Star 排行榜")
    for s in stats_list:
        print_bar(s["name"], s["stars"], max_star)

    print(f"\n{'─' * 55}")
    print(f"{'仓库':<15} {'语言':<10} {'Stars':>8} {'Forks':>8} {'Issues':>8} {'创建':>12}")
    print(f"{'─' * 55}")
    for s in stats_list:
        print(f"{s['name']:<15} {s['language'] or 'N/A':<10} {s['stars']:>8,} {s['forks']:>8,} {s['issues']:>8,} {s['created']:>12}")

    # 汇总
    total_stars = sum(s["stars"] for s in stats_list)
    total_forks = sum(s["forks"] for s in stats_list)
    print(f"{'─' * 55}")
    print(f"{'合计':<15} {'':10} {total_stars:>8,} {total_forks:>8,}")
    print(f"\n  语言分布：")
    langs = {}
    for s in stats_list:
        lang = s["language"] or "Unknown"
        langs[lang] = langs.get(lang, 0) + s["stars"]
    for lang, stars in sorted(langs.items(), key=lambda x: x[1], reverse=True):
        print(f"    {lang:<15} {stars:>8,} ★")

    return stats_list


# ── HTML 报告 ──

def generate_html(stats_list):
    """生成带饼图、柱状图的 HTML 可视化报告"""
    names = [s["name"] for s in stats_list]
    stars = [s["stars"] for s in stats_list]

    # 预计算语言分布
    lang_star_map = {}
    for s in stats_list:
        lang = s["language"] or "Unknown"
        lang_star_map[lang] = lang_star_map.get(lang, 0) + s["stars"]
    lang_labels = list(lang_star_map.keys())
    lang_data = [lang_star_map[l] for l in lang_labels]

    html = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>GitHub Star 分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 900px; margin: 0 auto; padding: 30px; background: #0d1117; color: #c9d1d9; }
  h1 { text-align: center; color: #58a6ff; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin: 30px 0; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }
  .card h3 { margin-top: 0; color: #58a6ff; }
  table { width: 100%; border-collapse: collapse; margin-top: 15px; }
  th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #30363d; }
  th { color: #8b949e; font-weight: 600; }
  tr:hover { background: #1c2129; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  footer { text-align: center; color: #484f58; margin-top: 40px; font-size: 13px; }
</style>
</head>
<body>
<h1>&#x1f4ca; GitHub 仓库 Star 分析</h1>
<p style="text-align:center;color:#8b949e;">数据获取时间：""" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + """</p>

<div class="grid">
  <div class="card">
    <h3>&#x2b50; Star 数量对比</h3>
    <canvas id="starChart"></canvas>
  </div>
  <div class="card">
    <h3>&#x1f524; 语言 Star 分布</h3>
    <canvas id="langChart"></canvas>
  </div>
</div>

<div class="card">
  <h3>&#x1f4cb; 详细数据</h3>
  <table>
    <thead><tr><th>仓库</th><th>语言</th><th class="num">&#x2b50; Stars</th><th class="num">&#x1f374; Forks</th><th class="num">&#x1f41b; Issues</th><th>最后推送</th></tr></thead>
    <tbody>
"""
    for s in stats_list:
        full = s['full_name']
        html += f'<tr><td><a href="https://github.com/{full}" target="_blank" style="color:#58a6ff">{full}</a></td>'
        html += f"<td>{s['language'] or 'N/A'}</td>"
        html += f"<td class=\"num\">{s['stars']:,}</td>"
        html += f"<td class=\"num\">{s['forks']:,}</td>"
        html += f"<td class=\"num\">{s['issues']:,}</td>"
        html += f"<td>{s['pushed']}</td></tr>\n"

    html += f"""</tbody>
  </table>
</div>

<script>
const colors = ['#58a6ff','#3fb950','#d29922','#f78166','#a371f7','#8b949e','#79c0ff',
                '#56d364','#e3b341','#f0883e','#bc8cff'];

new Chart(document.getElementById('starChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(names)},
    datasets: [{{
      label: 'Stars',
      data: {json.dumps(stars)},
      backgroundColor: colors.slice(0, {len(names)}),
      borderColor: colors.slice(0, {len(names)}),
      borderWidth: 1,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ beginAtZero: true, ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }},
      x: {{ ticks: {{ color: '#8b949e' }}, grid: {{ display: false }} }}
    }}
  }}
}});

new Chart(document.getElementById('langChart'), {{
  type: 'doughnut',
  data: {{
    labels: {json.dumps(lang_labels)},
    datasets: [{{
      data: {json.dumps(lang_data)},
      backgroundColor: colors.slice(0, {len(lang_labels)}),
      borderWidth: 0,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ position: 'bottom', labels: {{ color: '#8b949e' }} }}
    }}
  }}
}});
</script>

<footer>&#x7531; GitHub Stats Analyzer &#x751f;&#x6210; &middot; &#x6570;&#x636e;&#x6e90;&#xff1a;GitHub REST API</footer>
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    return OUTPUT_HTML


# ── 主流程 ──

def main():
    print("\n" + "=" * 55)
    print("  🚀 GitHub 仓库 Star 趋势分析")
    print("=" * 55)
    print(f"  待分析仓库：{len(REPOS)} 个")

    stats_list = []
    for repo in REPOS:
        stats = fetch_repo_stats(repo)
        if stats:
            stats_list.append(stats)
        time.sleep(0.3)  # 避免触发 API 限流

    if not stats_list:
        print("\n❌ 所有仓库获取失败，请检查网络连接")
        return

    # 终端报告
    terminal_report(stats_list)

    # 生成 HTML
    print(f"\n📄 生成可视化报告 …", end=" ", flush=True)
    html_path = generate_html(stats_list)
    print("完成")
    print(f"   文件路径：{html_path}")
    print(f"   在浏览器中打开 …")
    webbrowser.open(f"file://{html_path}")

    print(f"\n✅ 分析完成！")
    print(f"   提示：你可以在脚本顶部的 REPOS 列表里修改要分析的仓库\n")


if __name__ == "__main__":
    main()
