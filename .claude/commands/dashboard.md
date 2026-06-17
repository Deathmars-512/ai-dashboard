# AI 每日摘要儀表板 — 專案技能

你正在協助維護「AI 每日摘要儀表板」專案。以下是完整的專案背景，請在整個對話中保持這些知識。

## 專案概述

個人用的每日 AI 文章摘要儀表板，在 Windows 本機執行，用本地 Ollama + Qwen3:8b 做繁體中文摘要，完全免費離線。  
對外部署在 GitHub Pages：`https://Deathmars-512.github.io/ai-dashboard`

**核心原則：** 開發用 Claude Code；摘要引擎固定為 Ollama + Qwen3:8b（localhost:11434），不改用雲端 API。

## 使用者環境

- CPU: i7-14700 / RAM: 16GB DDR4 / GPU: RTX 5060 (8GB VRAM)
- OS: Windows 11 Pro / 工具: VSCode + Claude Code
- 專案路徑: `C:\Users\justin\Desktop\AI查詢系統\`
- GitHub 帳號: Deathmars-512
- venv: `venv\Scripts\python.exe`

## 整體架構（每日 pipeline）

```
RSS (feedparser) → 去重 (SQLite) → 抓全文 (trafilatura)
→ 相關性評分 (Qwen3) → 繁中摘要 (Qwen3) → 分類 (Qwen3)
→ 存 SQLite → 產生 index.html → 自動 push GitHub Pages
```

每日排程：Windows 工作排程器 09:00 執行 `venv\Scripts\python.exe main.py`

## 專案檔案

| 檔案 | 功能 |
|------|------|
| `db.py` | Schema、STARTER_FEEDS、init_db()、舊 URL 停用 migration |
| `collect.py` | Phase 1：feedparser 讀 RSS，INSERT OR IGNORE 去重 |
| `fetch.py` | Phase 2：trafilatura 抓全文 |
| `summarize.py` | Phase 3：Qwen3 評分(0-10) + 繁中摘要 + 7類分類 |
| `generate.py` | Phase 4：產生 index.html（WebGL shader + Glassmorphism UI） |
| `discover.py` | Phase 6：高頻高分 domain 自動探索 RSS |
| `main.py` | 每日 pipeline 主程式 + push_to_github() |
| `run_daily.bat` | Windows Task Scheduler 啟動器 |
| `_audit.py` | 診斷腳本 |

## 關鍵技術細節

### Qwen3 think 參數（必記）
```python
# 正確：think=False 必須是頂層參數
ollama.chat(model=MODEL, messages=[...], think=False, options={"num_predict": 10})
# 錯誤：放 options 裡會讓 content 為空
ollama.chat(model=MODEL, messages=[...], options={"think": False})
```

### 同名 Feed 重複 JOIN（必記）
所有 `JOIN feeds f ON a.source = f.name` 都必須加 `AND f.active = 1`，否則停用的舊 feed 造成重複處理。

### generate.py 模板設計
- `HTML_TEMPLATE = '''...'''`（非 f-string，非 .format()）
- 動態值用 `__TOKEN__` 佔位符，鏈式 `.replace()` 替換
- **WebGL JS 陷阱**：模板內 JS 字串分隔符必須寫 `'\\n'`，不能寫 `'\n'`（Python 會把 `\n` 轉成真實換行，導致 JS SyntaxError）

### 日期處理（Windows 限定）
- `f"{d.year} 年 {d.month} 月 {d.day} 日"` — 不能用 `%-m`、`%-d`（Linux only）
- feedparser struct_time 是 UTC，需轉 UTC+8 再存：`datetime(*t[:6], tzinfo=timezone.utc).astimezone(TZ_LOCAL).replace(tzinfo=None).isoformat()`

## 儀表板 UI（Stitch Glassmorphism 版）

- **背景**：WebGL FBM Shader，canvas `position:fixed; z-index:0`，main `position:relative; z-index:1`
- **側邊欄**：`width:256px; background:rgba(5,20,36,0.18); backdrop-filter:blur(6px)`
- **Header**：`height:52px; background:rgba(5,20,36,0.2); backdrop-filter:blur(6px)`
- **卡片**：毛玻璃 `rgba(255,255,255,0.03)` + 彩色頂邊 + scan-line + hover 浮起

### 7 個分類配色（CAT_STYLE）
| 分類 | accent | badge bg | badge border |
|------|--------|----------|--------------|
| 模型與研究 | #00f2ff | rgba(0,242,255,0.1) | rgba(0,242,255,0.3) |
| AI工具與產品 | #34d399 | rgba(52,211,153,0.1) | rgba(52,211,153,0.3) |
| 產業動態 | #fbbf24 | rgba(251,191,36,0.1) | rgba(251,191,36,0.3) |
| 資安與風險 | #ffb4ab | rgba(255,180,171,0.1) | rgba(255,180,171,0.3) |
| 政策與法規 | #dcb8ff | rgba(220,184,255,0.1) | rgba(220,184,255,0.3) |
| 硬體與基礎設施 | #38bdf8 | rgba(56,189,248,0.1) | rgba(56,189,248,0.3) |
| 其他 | #849495 | rgba(132,148,149,0.1) | rgba(132,148,149,0.3) |

## 常用操作指令

```powershell
# 重新產生儀表板
venv\Scripts\python.exe generate.py

# 手動跑一次完整 pipeline
venv\Scripts\python.exe main.py

# 推上 GitHub Pages
git add index.html; git commit -m "daily update"; git push origin main

# 診斷 feed 狀態
venv\Scripts\python.exe _audit.py
```

## .gitignore 規則
排除：`venv/`、`data/`（SQLite DB）、`logs/`、`__pycache__/`、`*.pptx`

## 已知重要 Bug 模式（避免重蹈）

1. `JOIN feeds` 忘記加 `AND f.active=1` → 重複卡片/抓取/摘要
2. `lstrip("www.")` 是字元集合操作，應改用 `removeprefix("www.")`
3. HTML_TEMPLATE 中 JS `join('\n')` 的 `\n` → 改 `'\\n'`
4. `.summary.clamp` 不能加 `white-space:normal`（會破壞展開後的段落換行）
5. WebGL canvas `z-index:-1` 會被 html 背景蓋住（CSS spec），應用 `z-index:0`
