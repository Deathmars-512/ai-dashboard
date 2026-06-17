"""Phase 3：對 fetched 文章做相關性評分，高分者生成繁體中文摘要。"""

import re
import time
import logging
import ollama
from pathlib import Path

from db import get_conn, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "logs" / "summarize.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

MODEL = "qwen3:8b"
BATCH_SIZE = 20
SCORE_THRESHOLD = 7   # 低於此分數直接 skipped

SCORE_PROMPT = """\
請判斷以下文章與「人工智慧（AI）技術、工具、模型、研究或應用」的相關程度。
只回覆一個 0 到 10 的整數，不要附帶任何說明。

評分標準：
- 9～10：核心 AI 主題（LLM、模型訓練、AI 工具評測、AI 應用案例等）
- 6～8：有明確 AI 內容但非主題（科技新聞中順帶提及 AI）
- 3～5：與 AI 間接相關（生物科技、量子運算、一般軟體工程等）
- 0～2：完全無關（財經、政治、娛樂、醫療、體育等）

重要原則：若文章主題是醫療、疫苗、氣候、太空、物理、化學等自然科學，
即使是「研究」或「科技媒體報導」，只要沒有明確 AI 內容，一律給 0～2 分。

標題：{title}
內文（前 500 字）：
{snippet}
"""

SUMMARY_PROMPT = """\
你是一位 AI 領域的中文編輯。請閱讀以下文章，輸出繁體中文的重點摘要。

要求：
- 3～5 段，每段聚焦一個重點。
- 用台灣慣用的繁體中文與術語。
- 只根據文章內容，不要杜撰或補充外部資訊。
- 開頭一句點出這篇在講什麼，後面補關鍵細節與影響。
- 不要加開場白或結語，直接給摘要。

文章標題：{title}
文章內文：
{full_text}
"""

CATEGORY_PROMPT = """\
請根據文章內容，從以下分類中選出最符合的一個，只回覆分類名稱，不要加任何說明：

模型與研究、AI工具與產品、產業動態、資安與風險、政策與法規、硬體與基礎設施、其他

文章標題：{title}
內文摘要：{summary}
"""

CATEGORIES = ("模型與研究", "AI工具與產品", "產業動態", "資安與風險", "政策與法規", "硬體與基礎設施", "其他")


def score_relevance(title: str, full_text: str) -> int:
    snippet = full_text[:500]
    prompt = SCORE_PROMPT.format(title=title, snippet=snippet)
    try:
        resp = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            think=False,
            options={"num_predict": 10},
        )
        raw = resp.message.content.strip()
        match = re.search(r"\d+", raw)
        if match:
            return min(10, max(0, int(match.group())))
    except Exception as e:
        log.warning(f"  評分失敗：{e}")
    return 0


def classify_category(title: str, summary: str) -> str:
    prompt = CATEGORY_PROMPT.format(title=title, summary=summary[:500])
    try:
        resp = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            think=False,
            options={"num_predict": 20},
        )
        raw = resp.message.content.strip()
        for cat in CATEGORIES:
            if cat in raw:
                return cat
    except Exception as e:
        log.warning(f"  分類失敗：{e}")
    return "其他"


def generate_summary(title: str, full_text: str) -> str | None:
    # 全文過長時截斷（約 3000 字，避免超出 context）
    text = full_text[:3000]
    prompt = SUMMARY_PROMPT.format(title=title, full_text=text)
    try:
        resp = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            think=False,
            options={"num_predict": 600},
        )
        return resp.message.content.strip()
    except Exception as e:
        log.warning(f"  摘要失敗：{e}")
    return None


def run(batch_size: int = BATCH_SIZE, priority_categories: list | None = None):
    init_db()
    conn = get_conn()

    if priority_categories:
        placeholders = ",".join("?" * len(priority_categories))
        rows = conn.execute(f"""
            SELECT a.id, a.title, a.full_text FROM articles a
            JOIN feeds f ON a.source = f.name AND f.active = 1
            WHERE a.status = 'fetched' AND f.category IN ({placeholders})
            LIMIT ?
        """, (*priority_categories, batch_size)).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, full_text FROM articles WHERE status = 'fetched' LIMIT ?",
            (batch_size,),
        ).fetchall()

    log.info(f"待處理文章：{len(rows)} 篇")

    summarized, skipped = 0, 0
    for row in rows:
        title = row["title"] or ""
        full_text = row["full_text"] or ""
        log.info(f"評分中：{title[:60]}")

        score = score_relevance(title, full_text)
        log.info(f"  相關性分數：{score}")

        if score < SCORE_THRESHOLD:
            conn.execute(
                "UPDATE articles SET relevance_score=?, status='skipped' WHERE id=?",
                (score, row["id"]),
            )
            skipped += 1
        else:
            log.info("  生成摘要中…")
            summary = generate_summary(title, full_text)
            if summary:
                category = classify_category(title, summary)
                conn.execute(
                    "UPDATE articles SET relevance_score=?, ai_summary=?, content_category=?, status='summarized' WHERE id=?",
                    (score, summary, category, row["id"]),
                )
                log.info(f"  摘要完成（{len(summary)} 字）分類：{category}")
                summarized += 1
            else:
                conn.execute(
                    "UPDATE articles SET relevance_score=?, status='skipped' WHERE id=?",
                    (score, row["id"]),
                )
                skipped += 1

        conn.commit()
        time.sleep(0.2)

    conn.close()
    log.info(f"完成！摘要 {summarized} 篇，跳過 {skipped} 篇")


if __name__ == "__main__":
    run()
