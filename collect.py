"""Phase 1：從 feeds 表讀取 RSS，把新文章存進 articles（url 去重）。"""

import feedparser
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from pathlib import Path

from db import get_conn, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "logs" / "collect.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.removeprefix("www.")
    except Exception:
        return ""


TZ_LOCAL = timezone(timedelta(hours=8))   # Asia/Taipei (UTC+8)

def parse_published(entry) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                # feedparser struct_time 是 UTC，轉成本機時間後存 naive ISO 字串
                dt_utc = datetime(*t[:6], tzinfo=timezone.utc)
                return dt_utc.astimezone(TZ_LOCAL).replace(tzinfo=None).isoformat()
            except Exception:
                pass
    return ""


def collect_feed(conn: sqlite3.Connection, feed_id: int, name: str, feed_url: str) -> int:
    log.info(f"讀取 [{name}] {feed_url}")
    try:
        parsed = feedparser.parse(feed_url, request_headers={"User-Agent": "Mozilla/5.0"})
    except Exception as e:
        log.warning(f"  讀取失敗：{e}")
        return 0

    if parsed.bozo and not parsed.entries:
        log.warning(f"  RSS 解析異常：{parsed.bozo_exception}")
        return 0

    new_count = 0
    c = conn.cursor()
    for entry in parsed.entries:
        url = getattr(entry, "link", "").strip()
        if not url:
            continue

        title = getattr(entry, "title", "").strip()
        published_at = parse_published(entry)
        domain = get_domain(url)

        try:
            c.execute(
                """INSERT OR IGNORE INTO articles
                   (url, source, domain, title, published_at, status)
                   VALUES (?, ?, ?, ?, ?, 'new')""",
                (url, name, domain, title, published_at),
            )
            if c.rowcount:
                new_count += 1
        except Exception as e:
            log.warning(f"  寫入失敗 {url}：{e}")

    conn.commit()
    log.info(f"  新增 {new_count} 篇（共 {len(parsed.entries)} 篇）")
    return new_count


def run():
    init_db()
    conn = get_conn()

    feeds = conn.execute("SELECT id, name, feed_url FROM feeds WHERE active = 1").fetchall()
    log.info(f"開始收集，共 {len(feeds)} 個來源")

    total_new = 0
    for row in feeds:
        total_new += collect_feed(conn, row["id"], row["name"], row["feed_url"])

    conn.close()
    log.info(f"完成！本次共新增 {total_new} 篇文章")


if __name__ == "__main__":
    run()
