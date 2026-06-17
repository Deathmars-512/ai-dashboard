import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "ai_dashboard.db"

STARTER_FEEDS = [
    # 國際科技媒體
    ("TechCrunch AI",       "https://techcrunch.com/category/artificial-intelligence/feed/", "https://techcrunch.com",          "新聞"),
    ("The Verge",           "https://www.theverge.com/rss/index.xml",                        "https://www.theverge.com",        "新聞"),
    ("VentureBeat AI",      "https://feeds.feedburner.com/venturebeat/SZYF",                "https://venturebeat.com",         "新聞"),
    ("Ars Technica",        "https://feeds.arstechnica.com/arstechnica/technology-lab",     "https://arstechnica.com",         "新聞"),
    ("MIT Tech Review",     "https://www.technologyreview.com/feed/",                        "https://www.technologyreview.com","新聞"),
    ("The Decoder",         "https://the-decoder.com/feed/",                                 "https://the-decoder.com",         "新聞"),
    # 研究 / 官方部落格
    ("Hugging Face Blog",   "https://huggingface.co/blog/feed.xml",                         "https://huggingface.co/blog",     "研究"),
    ("Google DeepMind",     "https://deepmind.google/blog/rss.xml",                          "https://deepmind.google",         "研究"),
    # 發現引擎
    ("Hacker News",         "https://news.ycombinator.com/rss",                              "https://news.ycombinator.com",    "社群"),
    # 中文媒體
    ("iThome",              "https://www.ithome.com.tw/rss",                                 "https://www.ithome.com.tw",       "中文"),
    ("AI郵報",              "https://www.aiposthub.com/rss/",                                "https://www.aiposthub.com",       "中文"),
    ("TechNews 科技新報",   "https://technews.tw/tn-rss/",                                   "https://technews.tw",             "中文"),
    # AI 大神部落格 / Newsletter
    ("Simon Willison",      "https://simonwillison.net/atom/everything/",                    "https://simonwillison.net",       "大神"),
    ("Andrej Karpathy",     "https://karpathy.substack.com/feed",                            "https://karpathy.substack.com",   "大神"),
    ("One Useful Thing",    "https://www.oneusefulthing.org/feed",                           "https://www.oneusefulthing.org",  "大神"),
    ("Sebastian Raschka",   "https://magazine.sebastianraschka.com/feed",                   "https://magazine.sebastianraschka.com", "大神"),
    ("Chip Huyen",          "https://huyenchip.com/feed.xml",                               "https://huyenchip.com",           "大神"),
    ("Interconnects",       "https://www.interconnects.ai/feed",                            "https://www.interconnects.ai",    "大神"),
    ("Import AI",           "https://jack-clark.net/feed/",                                  "https://jack-clark.net",          "大神"),
    ("Eugene Yan",          "https://eugeneyan.com/rss.xml",                                "https://eugeneyan.com",           "大神"),
    # 台灣 AI 大神
    ("AppWorks Blog",       "https://medium.com/feed/appworks-school",                      "https://blog.appworks.tw",        "台灣大神"),
    ("資訊人權貴",          "https://blog.gslin.org/feed/",                                  "https://blog.gslin.org",          "台灣大神"),
    ("電腦玩物",            "https://www.playpcesor.com/feeds/posts/default",               "https://www.playpcesor.com",      "台灣大神"),
    ("Star Rocket Blog",    "https://blog.starrocket.io/feed/",                             "https://blog.starrocket.io",      "台灣大神"),
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS feeds (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            feed_url    TEXT NOT NULL UNIQUE,
            site_url    TEXT,
            category    TEXT,
            active      INTEGER DEFAULT 1,
            avg_score   REAL DEFAULT 0,
            promoted    INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS articles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            url             TEXT NOT NULL UNIQUE,
            source          TEXT,
            domain          TEXT,
            title           TEXT,
            published_at    TEXT,
            full_text       TEXT,
            relevance_score REAL,
            ai_summary      TEXT,
            content_category TEXT,
            collected_at    TEXT DEFAULT (datetime('now', 'localtime')),
            status          TEXT DEFAULT 'new'
        );
    """)

    # 舊資料庫補欄位（不影響新裝）
    try:
        c.execute("ALTER TABLE articles ADD COLUMN content_category TEXT")
        conn.commit()
    except Exception:
        pass

    # 停用已被新 URL 取代的舊版重複 feeds
    c.execute("""
        UPDATE feeds SET active=0
        WHERE feed_url IN (
            'https://feeds.arstechnica.com/arstechnica/index',
            'https://venturebeat.com/category/ai/feed/',
            'https://blog.appworks.tw/feed/'
        )
    """)
    conn.commit()

    # 寫入起手來源（已存在的跳過）
    c.executemany(
        "INSERT OR IGNORE INTO feeds (name, feed_url, site_url, category) VALUES (?, ?, ?, ?)",
        STARTER_FEEDS,
    )

    conn.commit()
    conn.close()
    print(f"資料庫就緒：{DB_PATH}")


if __name__ == "__main__":
    init_db()
