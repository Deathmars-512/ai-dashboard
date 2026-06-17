"""每日主 pipeline：collect → fetch → summarize → generate → push"""

import logging
import subprocess
import time
from pathlib import Path
from datetime import datetime

LOG_PATH = Path(__file__).parent / "logs" / "main.log"
LOG_PATH.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def step(name: str, fn, **kwargs):
    log.info(f"{'='*40}")
    log.info(f"開始：{name}")
    t0 = time.time()
    ok = True
    try:
        fn(**kwargs)
    except Exception as e:
        log.error(f"{name} 失敗：{e}", exc_info=True)
        ok = False
    elapsed = time.time() - t0
    status = "完成" if ok else "失敗"
    log.info(f"{status}：{name}（{elapsed:.1f} 秒）")


def push_to_github():
    repo = Path(__file__).parent
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    cmds = [
        ["git", "-C", str(repo), "add", "index.html"],
        ["git", "-C", str(repo), "commit", "-m", f"daily update {today}"],
        ["git", "-C", str(repo), "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        combined = result.stdout + result.stderr
        if result.returncode != 0:
            if "nothing to commit" in combined or "nothing added to commit" in combined:
                log.info("index.html 無變動，略過 push")
                return
            log.warning(f"git 指令失敗：{' '.join(cmd)}\n{combined}")
            return
    log.info("index.html 已推送到 GitHub Pages")


def main():
    log.info(f"{'='*40}")
    log.info(f"每日 pipeline 開始 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    t_start = time.time()

    from collect import run as collect_run
    from fetch import run as fetch_run
    from summarize import run as summarize_run
    from generate import generate
    from discover import run as discover_run

    PRIORITY_CATS = ["大神", "台灣大神", "中文"]

    step("1. 收集 RSS", collect_run)
    # 大神 / 台灣大神 / 中文 優先抓取與摘要，確保早上打開就能看到
    step("2a. 抓取全文（優先）", fetch_run, batch_size=200, priority_categories=PRIORITY_CATS)
    step("2b. 抓取全文（一般）", fetch_run, batch_size=100)
    step("3a. 摘要（優先）", summarize_run, batch_size=60, priority_categories=PRIORITY_CATS)
    step("3b. 摘要（一般）", summarize_run, batch_size=60)
    step("4. 來源發現", discover_run)
    step("5. 產生儀表板", generate)
    step("6. 推送到 GitHub Pages", push_to_github)

    total = time.time() - t_start
    log.info(f"{'='*40}")
    log.info(f"pipeline 全部完成，總耗時 {total/60:.1f} 分鐘")


if __name__ == "__main__":
    main()
