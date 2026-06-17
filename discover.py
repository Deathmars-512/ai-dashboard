"""Phase 6：來源發現機制。
1. 統計高分文章的 domain 頻率。
2. 對頻率超過門檻的新網域，自動探索 RSS 並加入 feeds（標記 promoted=1）。
"""

import logging
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from db import get_conn, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "logs" / "discover.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

SCORE_MIN = 6       # 相關性分數門檻（這個 domain 的文章才算數）
FREQ_MIN = 3        # domain 出現幾次才考慮升級
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AI-Dashboard/1.0)"}
TIMEOUT = 10

# 常見 RSS 路徑（當 head 裡沒有宣告時的備用嘗試）
COMMON_RSS_PATHS = [
    "/feed", "/feed.xml", "/rss", "/rss.xml",
    "/atom.xml", "/feed/atom", "/blog/feed",
    "/news/feed", "/feeds/posts/default",
]


def find_rss_from_html(url: str) -> str | None:
    """從網站 HTML head 找出 RSS/Atom 連結。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        soup = BeautifulSoup(resp.text, "html.parser")
        for link in soup.find_all("link", rel="alternate"):
            t = link.get("type", "")
            if "rss" in t or "atom" in t:
                href = link.get("href", "")
                if href:
                    return urljoin(url, href)
    except Exception as e:
        log.debug(f"  HTML 解析失敗 {url}：{e}")
    return None


def probe_common_paths(base_url: str) -> str | None:
    """嘗試常見 RSS 路徑，能取到 XML 就回傳。"""
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in COMMON_RSS_PATHS:
        candidate = base + path
        try:
            resp = requests.get(candidate, headers=HEADERS, timeout=TIMEOUT)
            ct = resp.headers.get("Content-Type", "")
            if resp.status_code == 200 and ("xml" in ct or "rss" in ct or "atom" in ct):
                return candidate
        except Exception:
            continue
    return None


def discover_feed(domain: str) -> str | None:
    """給 domain，回傳找到的 feed URL（找不到就 None）。"""
    homepage = f"https://{domain}"
    log.info(f"  探索 {domain} …")

    feed_url = find_rss_from_html(homepage)
    if feed_url:
        log.info(f"    從 HTML head 找到：{feed_url}")
        return feed_url

    feed_url = probe_common_paths(homepage)
    if feed_url:
        log.info(f"    從常見路徑找到：{feed_url}")
        return feed_url

    log.info(f"    找不到 RSS")
    return None


def run(score_min: int = SCORE_MIN, freq_min: int = FREQ_MIN):
    init_db()
    conn = get_conn()

    # 已追蹤的網域（從 site_url 擷取 netloc，去掉 www. 前綴）
    existing_domains = {
        urlparse(row[0]).netloc.removeprefix("www.")
        for row in conn.execute("SELECT site_url FROM feeds WHERE site_url IS NOT NULL").fetchall()
    }
    existing_feed_urls = {
        row[0]
        for row in conn.execute("SELECT feed_url FROM feeds").fetchall()
    }

    # 統計高分文章的 domain 頻率
    rows = conn.execute("""
        SELECT domain, COUNT(*) as cnt
        FROM articles
        WHERE relevance_score >= ? AND domain != ''
        GROUP BY domain
        HAVING cnt >= ?
        ORDER BY cnt DESC
    """, (score_min, freq_min)).fetchall()

    log.info(f"高頻網域（分數>={score_min}，出現>={freq_min}次）：{len(rows)} 個")

    promoted = 0
    for row in rows:
        domain = row["domain"]
        cnt = row["cnt"]

        # 已在追蹤清單裡就跳過（精確比對 domain）
        already = domain in existing_domains
        if already:
            log.info(f"  [{cnt}次] {domain} — 已在追蹤清單")
            continue

        log.info(f"  [{cnt}次] {domain} — 新網域，嘗試找 RSS")
        feed_url = discover_feed(domain)

        if feed_url and feed_url not in existing_feed_urls:
            conn.execute("""
                INSERT OR IGNORE INTO feeds (name, feed_url, site_url, category, promoted)
                VALUES (?, ?, ?, '發現', 1)
            """, (domain, feed_url, f"https://{domain}"))
            conn.commit()
            existing_feed_urls.add(feed_url)
            log.info(f"    >>> 已加入 feeds：{feed_url}")
            promoted += 1

    conn.close()
    log.info(f"完成！本次新增 {promoted} 個自動發現來源")


if __name__ == "__main__":
    run()
