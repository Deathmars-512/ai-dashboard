"""Phase 2：對 status='new' 的文章抓取全文，寫回 full_text。"""

import time
import logging
import trafilatura
from pathlib import Path

from db import get_conn, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "logs" / "fetch.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

BATCH_SIZE = 50   # 每次最多處理幾篇（避免單次跑太久）
DELAY = 0.5       # 每篇之間等待秒數（避免對來源造成壓力）


def fetch_full_text(url: str) -> str | None:
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        return text
    except Exception as e:
        log.warning(f"  抓取失敗 {url}：{e}")
        return None


def run(batch_size: int = BATCH_SIZE, priority_categories: list | None = None):
    init_db()
    conn = get_conn()

    if priority_categories:
        placeholders = ",".join("?" * len(priority_categories))
        rows = conn.execute(f"""
            SELECT a.id, a.url, a.title, a.source FROM articles a
            JOIN feeds f ON a.source = f.name AND f.active = 1
            WHERE a.status = 'new' AND f.category IN ({placeholders})
            LIMIT ?
        """, (*priority_categories, batch_size)).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, url, title, source FROM articles WHERE status = 'new' LIMIT ?",
            (batch_size,),
        ).fetchall()

    log.info(f"待抓取文章：{len(rows)} 篇")

    success, skipped = 0, 0
    for row in rows:
        log.info(f"[{row['source']}] {row['title'][:60]}")
        text = fetch_full_text(row["url"])

        if text and len(text) > 100:
            conn.execute(
                "UPDATE articles SET full_text = ?, status = 'fetched' WHERE id = ?",
                (text, row["id"]),
            )
            log.info(f"  OK，{len(text)} 字")
            success += 1
        else:
            conn.execute(
                "UPDATE articles SET status = 'fetch_failed' WHERE id = ?",
                (row["id"],),
            )
            log.info("  跳過（無法取得有效內文）")
            skipped += 1

        conn.commit()
        time.sleep(DELAY)

    conn.close()
    log.info(f"完成！成功 {success} 篇，跳過 {skipped} 篇")


if __name__ == "__main__":
    run()
