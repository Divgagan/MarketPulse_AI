"""
pipeline/scheduler.py — MarketPulse AI
========================================
Blueprint Part 17 File 2: Scheduler (development mode).

Runs MarketPulse AI on a schedule during development (on your laptop).
For production, GitHub Actions replaces this scheduler.

Schedule:
  - ML Pipeline (EOD): Daily at 6:30 AM IST (pre-market, before market opens at 9:15 AM)
  - News pipeline:     Every 30 minutes, 6:30 AM – 6:00 PM IST (full trading day coverage)
  - Monthly retrain:   1st of every month at 8 PM IST

Design Decision:
  The ML pipeline runs at 6:30 AM so predictions are ready BEFORE the market opens at 9:15 AM.
  News agents run every 30 min from 6:30 AM onwards to catch pre-market news,
  intraday developments, and post-market announcements.

Usage:
  python -m pipeline.scheduler         ← runs indefinitely until Ctrl+C
  python -m pipeline.scheduler --once  ← runs news_cycle once then exits
"""

import logging
import sys
import time
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from agents.graph import run_pipeline
from pipeline.eod_pipeline import run_eod_pipeline, run_monthly_retrain

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")

IST = pytz.timezone("Asia/Kolkata")


# ── Job Wrappers ──────────────────────────────────────────────────────────────

def _run_news_cycle():
    """Wrapper: run news_cycle pipeline with error isolation."""
    try:
        now = datetime.now(IST).strftime("%H:%M:%S IST")
        logger.info(f"[{now}] Running news_cycle pipeline...")
        result = run_pipeline("news_cycle")
        n = len(result.get("final_signals", []))
        logger.info(f"[{now}] news_cycle complete: {n} signals")
    except Exception as e:
        logger.error(f"news_cycle failed: {e}")


def _run_eod():
    """Wrapper: run EOD pipeline with error isolation."""
    try:
        now = datetime.now(IST).strftime("%H:%M:%S IST")
        logger.info(f"[{now}] Running EOD pipeline...")
        run_eod_pipeline()
    except Exception as e:
        logger.error(f"EOD pipeline failed: {e}")


def _run_monthly():
    """Wrapper: run monthly retraining with error isolation."""
    try:
        now = datetime.now(IST).strftime("%H:%M:%S IST")
        logger.info(f"[{now}] Running monthly retraining...")
        run_monthly_retrain()
    except Exception as e:
        logger.error(f"Monthly retrain failed: {e}")


# ── Scheduler Factory ─────────────────────────────────────────────────────────

def start_scheduler() -> BackgroundScheduler:
    """
    Initialize and start the APScheduler with all 3 jobs.

    Returns:
        Running BackgroundScheduler instance.
    """
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    # ── Job 1: News pipeline every 30 min, 6:30 AM – 6:00 PM IST ──────────────
    # Starts at 6:30 AM to catch pre-market news before 9:15 AM market open.
    # Runs every 30 min continuously through market hours and post-market.
    scheduler.add_job(
        func    = _run_news_cycle,
        trigger = "cron",
        hour    = "6-18",
        minute  = "*/30",
        id      = "news_pipeline",
        name    = "News Cycle Pipeline",
        misfire_grace_time = 300,  # 5 min grace if job was missed
    )

    # ── Job 2: ML Pipeline at 6:30 AM IST daily (pre-market) ────────────────
    # Runs BEFORE market opens (9:15 AM) so predictions are ready for traders.
    # Collects latest data, runs HMM + LightGBM + Chronos, generates signals.
    scheduler.add_job(
        func    = _run_eod,
        trigger = "cron",
        hour    = 6,
        minute  = 30,
        id      = "eod_pipeline",
        name    = "ML Pipeline (Pre-Market)",
        misfire_grace_time = 600,  # 10 min grace
    )

    # ── Job 3: Monthly retraining on 1st at 8 PM IST ─────────────────────────
    scheduler.add_job(
        func    = _run_monthly,
        trigger = "cron",
        day     = 1,
        hour    = 20,
        minute  = 0,
        id      = "monthly_retrain",
        name    = "Monthly Model Retraining",
        misfire_grace_time = 3600,  # 1 hr grace
    )

    scheduler.start()

    logger.info("=" * 60)
    logger.info("MarketPulse AI Scheduler Started (Asia/Kolkata / IST)")
    logger.info("=" * 60)
    logger.info("  Job 1 — News pipeline  : Every 30 min, 6:30 AM – 6:00 PM IST")
    logger.info("  Job 2 — ML Pipeline    : Daily at 6:30 AM IST (pre-market)")
    logger.info("  Job 3 — Monthly retrain: 1st of month, 8:00 PM IST")
    logger.info("Press Ctrl+C to stop.")
    logger.info("=" * 60)

    return scheduler


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m pipeline.scheduler
    # Run: python -m pipeline.scheduler --once  (single news_cycle then exit)

    if "--once" in sys.argv:
        logger.info("--once flag: running single news_cycle pipeline now...")
        _run_news_cycle()
        logger.info("Single run complete.")
        sys.exit(0)

    scheduler = start_scheduler()

    try:
        while True:
            time.sleep(60)
            now_ist = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
            jobs    = scheduler.get_jobs()
            logger.debug(f"[{now_ist}] Scheduler alive. {len(jobs)} jobs scheduled.")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — shutting down scheduler...")
        scheduler.shutdown()
        logger.info("Scheduler stopped.")
