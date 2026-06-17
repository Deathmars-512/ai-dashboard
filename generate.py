"""Phase 4：從 SQLite 讀出已摘要文章，產生 index.html 儀表板。"""

import sqlite3
from pathlib import Path
from datetime import datetime

from db import get_conn, init_db

OUT_PATH = Path(__file__).parent / "index.html"

# 分類配色：(accent色, badge背景, badge邊框)
CAT_STYLE = {
    "模型與研究":     ("#00f2ff", "rgba(0,242,255,0.1)",   "rgba(0,242,255,0.3)"),
    "AI工具與產品":   ("#34d399", "rgba(52,211,153,0.1)",  "rgba(52,211,153,0.3)"),
    "產業動態":       ("#fbbf24", "rgba(251,191,36,0.1)",  "rgba(251,191,36,0.3)"),
    "資安與風險":     ("#ffb4ab", "rgba(255,180,171,0.1)", "rgba(255,180,171,0.3)"),
    "政策與法規":     ("#dcb8ff", "rgba(220,184,255,0.1)", "rgba(220,184,255,0.3)"),
    "硬體與基礎設施": ("#38bdf8", "rgba(56,189,248,0.1)",  "rgba(56,189,248,0.3)"),
    "其他":           ("#849495", "rgba(132,148,149,0.1)", "rgba(132,148,149,0.3)"),
}

# HTML 模板（使用 __TOKEN__ 避免與 CSS/JS 的 {} 衝突）
HTML_TEMPLATE = '''<!DOCTYPE html>
<html class="dark" lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 每日摘要</title>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;600;700;800;900&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; }
  body {
    background-color: #051424;
    color: #d4e4fa;
    font-family: 'Inter', sans-serif;
    overflow-x: hidden;
  }
  /* Glass effect */
  .glass-1 {
    background: rgba(255,255,255,0.03);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(116,245,255,0.08);
  }
  /* Scan-line animation (horizontal sweep) */
  .scan-line {
    height: 2px;
    background: linear-gradient(90deg, transparent, #00f2ff, transparent);
    background-size: 200% 100%;
    animation: scan 3s linear infinite;
  }
  @keyframes scan {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
  /* Pulsing indicator pip */
  .pulse-pip {
    animation: pulse-ring 2s cubic-bezier(0.4,0,0.6,1) infinite;
  }
  @keyframes pulse-ring {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%       { opacity: 0.5; transform: scale(1.2); }
  }
  /* Summary expand/collapse */
  .summary { white-space: pre-line; }
  .summary.clamp {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 4;
    overflow: hidden;
    /* 不加 white-space:normal，保留 pre-line 讓展開後段落換行正常 */
  }
  /* Utility */
  .hidden { display: none; }
  /* Sidebar filter buttons */
  .filter-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 7px 12px;
    border-radius: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.07em;
    color: #b9cacb;
    transition: all 0.2s;
    cursor: pointer;
    background: transparent;
    border: 1px solid transparent;
    text-align: left;
  }
  .filter-btn:hover {
    color: #74f5ff;
    background: rgba(116,245,255,0.05);
  }
  .filter-btn.on {
    color: #74f5ff;
    background: rgba(116,245,255,0.08);
    border-color: rgba(116,245,255,0.18);
  }
  .filter-cnt {
    font-size: 10px;
    background: rgba(255,255,255,0.05);
    border-radius: 4px;
    padding: 1px 6px;
    min-width: 24px;
    text-align: center;
    flex-shrink: 0;
  }
  .filter-btn.on .filter-cnt { background: rgba(116,245,255,0.12); }
  /* Expand button */
  .xbtn {
    display: inline-block;
    margin-top: 8px;
    font-size: 11px;
    color: #74f5ff;
    font-family: 'JetBrains Mono', monospace;
    cursor: pointer;
    background: none;
    border: none;
    padding: 0;
    letter-spacing: 0.06em;
  }
  .xbtn:hover { text-decoration: underline; }
  /* Card links */
  a.card-link  { color: #d4e4fa; text-decoration: none; transition: color 0.2s; }
  a.card-link:hover { color: #74f5ff; }
  a.read-link {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.06em;
    color: #74f5ff;
    text-decoration: none;
  }
  a.read-link:hover { text-decoration: underline; }
  /* Custom scrollbar */
  .scr::-webkit-scrollbar { width: 3px; }
  .scr::-webkit-scrollbar-track { background: transparent; }
  .scr::-webkit-scrollbar-thumb { background: rgba(116,245,255,0.15); border-radius: 10px; }
  .scr::-webkit-scrollbar-thumb:hover { background: rgba(116,245,255,0.3); }
</style>
</head>
<body>

<!-- Ambient glow orbs -->
<div style="position:fixed;bottom:0;right:0;width:384px;height:384px;border-radius:50%;background:rgba(0,242,255,0.04);filter:blur(120px);pointer-events:none;z-index:0"></div>
<div style="position:fixed;top:80px;left:300px;width:256px;height:256px;border-radius:50%;background:rgba(139,43,226,0.04);filter:blur(100px);pointer-events:none;z-index:0"></div>

<!-- ── SIDEBAR ── -->
<aside class="scr" style="position:fixed;left:0;top:0;height:100vh;width:256px;display:flex;flex-direction:column;padding:28px 18px;z-index:50;background:rgba(5,20,36,0.7);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);border-right:1px solid rgba(116,245,255,0.08)">

  <!-- Brand -->
  <div style="margin-bottom:18px">
    <h1 style="font-family:'Geist',sans-serif;font-weight:900;font-size:18px;letter-spacing:-0.02em;color:#74f5ff;line-height:1.2">AI 每日摘要</h1>
    <p style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.1em;color:#849495;margin-top:4px">LOCAL AI · DAILY DIGEST</p>
  </div>

  <!-- Stats panel -->
  <div style="border-radius:8px;padding:12px;margin-bottom:18px;background:rgba(116,245,255,0.04);border:1px solid rgba(116,245,255,0.1)">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
      <span style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.08em;color:#849495">ARTICLES</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#74f5ff">__TOTAL__</span>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.08em;color:#849495">UPDATED</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#74f5ff">__UPDATED_AT__</span>
    </div>
  </div>

  <!-- Filter nav -->
  <nav class="scr" style="flex:1;min-height:0;overflow-y:auto;margin:0 -4px;padding:0 4px">
    <div style="display:flex;flex-direction:column;gap:2px">
      <button class="filter-btn on" data-mode="all" onclick="applyFilter(this,'all','')">
        <span>ALL ARTICLES</span>
        <span class="filter-cnt">__TOTAL__</span>
      </button>
      <button class="filter-btn" data-mode="src" data-val="大神" onclick="applyFilter(this,'src','大神')">
        <span>⭐ EXPERT PICKS</span>
        <span class="filter-cnt" data-count-src="大神">—</span>
      </button>
      <div style="border-top:1px solid rgba(116,245,255,0.08);margin:6px 0"></div>
      __FILTER_BUTTONS__
    </div>
  </nav>

  <!-- Disclaimer -->
  <div style="padding-top:12px;border-top:1px solid rgba(116,245,255,0.08);font-size:10px;color:#6b7a8a;line-height:1.65;margin-top:8px">
    本站摘要整理自各公開文章，每篇均標示來源，版權歸原作者所有。摘要由本地 AI 自動生成，僅供個人學習參考、非商業用途，不代表原文立場。
  </div>
</aside>

<!-- ── TOP HEADER ── -->
<header style="position:fixed;top:0;left:256px;right:0;height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 36px;z-index:40;background:rgba(5,20,36,0.88);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid rgba(116,245,255,0.08)">
  <div style="display:flex;align-items:center;gap:10px">
    <span class="pulse-pip" style="width:8px;height:8px;border-radius:50%;background:#74f5ff;box-shadow:0 0 8px #00dbe7;display:inline-block;flex-shrink:0"></span>
    <span style="font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:0.1em;color:#74f5ff">LIVE FEED</span>
  </div>
</header>

<!-- ── MAIN ── -->
<main style="margin-left:256px;padding-top:52px;min-height:100vh">
  <div style="max-width:900px;margin:0 auto;padding:28px 36px 80px">
    __DATE_GROUPS__
    <div id="emptyMsg" class="hidden" style="text-align:center;padding:80px 0">
      <p style="font-size:40px;margin-bottom:14px">🔍</p>
      <p style="color:#849495;font-size:14px;font-family:'JetBrains Mono',monospace;letter-spacing:0.06em">NO ARTICLES IN THIS CATEGORY</p>
    </div>
  </div>
</main>

<script>
// 計算各篩選鈕的文章數
(function() {
  document.querySelectorAll('[data-count-src]').forEach(function(el) {
    el.textContent = document.querySelectorAll('.card[data-src-cat="' + el.dataset.countSrc + '"]').length;
  });
  document.querySelectorAll('[data-count-cat]').forEach(function(el) {
    el.textContent = document.querySelectorAll('.card[data-cat="' + el.dataset.countCat + '"]').length;
  });
})();

// 篩選
function applyFilter(btn, mode, val) {
  document.querySelectorAll('.filter-btn').forEach(function(b) { b.classList.remove('on'); });
  btn.classList.add('on');
  document.querySelectorAll('.card').forEach(function(c) {
    c.style.display = (
      mode === 'all' ||
      (mode === 'src' && c.dataset.srcCat === val) ||
      (mode === 'cat' && c.dataset.cat === val)
    ) ? '' : 'none';
  });
  var any = false;
  document.querySelectorAll('.dg').forEach(function(g) {
    var v = [].slice.call(g.querySelectorAll('.card')).some(function(c) { return c.style.display !== 'none'; });
    g.style.display = v ? '' : 'none';
    if (v) any = true;
  });
  document.getElementById('emptyMsg').classList.toggle('hidden', any);
}

// 摘要展開／收折
function toggleSummary(btn) {
  var s = btn.previousElementSibling;
  var collapsed = s.classList.toggle('clamp');
  btn.textContent = collapsed ? 'EXPAND ↓' : 'COLLAPSE ↑';
}
</script>

</body>
</html>'''


def fmt_date(date_str: str) -> str:
    try:
        d = datetime.fromisoformat(date_str)
        diff = (datetime.now().date() - d.date()).days
        if diff == 0: return "今天"
        if diff == 1: return "昨天"
        return f"{d.year} 年 {d.month} 月 {d.day} 日"
    except Exception:
        return date_str[:10]


def fmt_time(date_str: str) -> str:
    if not date_str: return ""
    try:
        return datetime.fromisoformat(date_str).strftime("%m/%d %H:%M")
    except Exception:
        return date_str[:16]


def build_card(row: sqlite3.Row) -> str:
    cat     = row["content_category"] or "其他"
    src_cat = row["src_category"] or ""
    color, badge_bg, badge_border = CAT_STYLE.get(cat, ("#849495", "rgba(132,148,149,0.1)", "rgba(132,148,149,0.3)"))
    score   = f"· {int(row['relevance_score'])}/10" if row["relevance_score"] else ""
    pub     = fmt_time(row["published_at"])
    url     = (row["url"] or "#").replace('"', "%22")
    title   = (row["title"] or "無標題").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    source  = (row["source"] or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    summary = (row["ai_summary"] or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("{", "&#123;").replace("}", "&#125;")

    expand_btn = ""
    clamp_cls  = ""
    if len(summary) > 300:
        clamp_cls  = " clamp"
        expand_btn = '<button class="xbtn" onclick="toggleSummary(this)">EXPAND ↓</button>'

    # border-top color: 25% alpha = hex 3d, hover 60% alpha = hex 99
    border_dim  = f"{color}3d"
    border_hi   = f"{color}99"

    return f"""\
<article class="card" data-cat="{cat}" data-src-cat="{src_cat}"
  style="position:relative;overflow:hidden;border-radius:12px;background:rgba(255,255,255,0.03);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(116,245,255,0.08);border-top:2px solid {border_dim};margin-bottom:12px;transition:transform 0.25s,box-shadow 0.25s,border-top-color 0.25s"
  onmouseenter="this.style.transform='translateY(-2px)';this.style.boxShadow='0 8px 32px rgba(0,219,231,0.08)';this.style.borderTopColor='{border_hi}'"
  onmouseleave="this.style.transform='';this.style.boxShadow='';this.style.borderTopColor='{border_dim}'">
  <div class="scan-line" style="position:absolute;top:0;left:0;width:100%;z-index:2"></div>
  <div style="padding:18px 20px">
    <div style="display:flex;align-items:center;gap:6px;margin-bottom:10px;flex-wrap:wrap">
      <span style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.06em;padding:2px 7px;border-radius:4px;border:1px solid rgba(132,148,149,0.25);color:#849495">{source}</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:0.06em;padding:2px 7px;border-radius:4px;background:{badge_bg};border:1px solid {badge_border};color:{color}">{cat}</span>
      <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#849495">{score}</span>
      <span style="margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:10px;color:#849495">{pub}</span>
    </div>
    <h3 style="font-family:'Geist',sans-serif;font-size:15px;font-weight:600;line-height:1.45;margin-bottom:10px">
      <a class="card-link" href="{url}" target="_blank" rel="noopener">{title}</a>
    </h3>
    <div class="summary{clamp_cls}" style="font-size:13.5px;color:#b9cacb;line-height:1.75">{summary}</div>
    {expand_btn}
    <div style="margin-top:12px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.05)">
      <a class="read-link" href="{url}" target="_blank" rel="noopener">閱讀原文 →</a>
    </div>
  </div>
</article>"""


def generate():
    init_db()
    conn = get_conn()

    rows = conn.execute("""
        SELECT a.url, a.title, a.published_at, a.ai_summary, a.relevance_score,
               a.source, a.content_category, f.category AS src_category
        FROM articles a
        LEFT JOIN feeds f ON a.source = f.name AND f.active = 1
        WHERE a.status = 'summarized'
          AND COALESCE(a.published_at, a.collected_at) >= date('now', '-60 days')
        ORDER BY COALESCE(a.published_at, a.collected_at) DESC
        LIMIT 300
    """).fetchall()
    conn.close()

    if not rows:
        print("尚無已摘要的文章，請先執行 summarize.py")
        return

    # 日期分組
    groups: dict[str, list] = {}
    for row in rows:
        key = (row["published_at"] or "")[:10]
        groups.setdefault(key, []).append(row)

    # 內容分類篩選按鈕（含計數）
    cat_order = ["模型與研究", "AI工具與產品", "產業動態", "資安與風險", "政策與法規", "硬體與基礎設施", "其他"]
    cat_counts: dict[str, int] = {}
    for row in rows:
        c = row["content_category"] or "其他"
        cat_counts[c] = cat_counts.get(c, 0) + 1

    filter_buttons = "\n".join(
        f'<button class="filter-btn" data-mode="cat" data-val="{c}" onclick="applyFilter(this,\'cat\',\'{c}\')">'
        f'<span>{c}</span>'
        f'<span class="filter-cnt" data-count-cat="{c}">{cat_counts.get(c, 0)}</span></button>'
        for c in cat_order if c in cat_counts
    )

    # 日期區塊 HTML
    date_groups_html = ""
    for key in sorted(groups.keys(), reverse=True):
        label    = fmt_date(key) if key else "日期不明"
        date_str = key or ""
        grp      = groups[key]
        cards    = "\n".join(build_card(r) for r in grp)
        date_groups_html += f"""\
<div class="dg" style="margin-bottom:40px">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
    <span style="font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;letter-spacing:0.1em;color:#849495;white-space:nowrap;text-transform:uppercase">{label}</span>
    <div style="flex:1;height:1px;background:rgba(255,255,255,0.06)"></div>
    <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#849495;white-space:nowrap">{date_str} · {len(grp)} ART.</span>
  </div>
  {cards}
</div>
"""

    html = (HTML_TEMPLATE
            .replace("__TOTAL__", str(len(rows)))
            .replace("__UPDATED_AT__", datetime.now().strftime("%Y/%m/%d %H:%M"))
            .replace("__FILTER_BUTTONS__", filter_buttons)
            .replace("__DATE_GROUPS__", date_groups_html))

    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"儀表板已產生：{OUT_PATH}（{len(rows)} 篇）")


if __name__ == "__main__":
    generate()
