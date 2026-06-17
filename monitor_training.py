"""
monitor_training.py — MarketPulse AI
=======================================
Live training progress monitor.
Run this in a separate terminal while setup.py is running.

Usage:
    conda activate agentic_env
    python monitor_training.py

Shows:
  - Real-time data download progress (stocks fetched)
  - Feature engineering progress
  - Model training progress per stock
  - Countdown timer and ETA
  - Color-coded status bars
"""

import os
import sys
import time
import glob
from pathlib import Path
from datetime import datetime, timedelta

# ── ANSI colors ───────────────────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    CYAN    = "\033[96m"
    RED     = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE    = "\033[94m"
    DIM     = "\033[2m"
    WHITE   = "\033[97m"

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT   = Path(__file__).parent
PROCESSED_DIR  = PROJECT_ROOT / "data" / "processed"
MODELS_DIR     = PROJECT_ROOT / "data" / "models"
CHROMA_DIR     = PROJECT_ROOT / "data" / "chroma_db"

TOTAL_STOCKS   = 50

# ── Progress bar builder ──────────────────────────────────────────────────────
def progress_bar(current, total, width=30, color=C.GREEN):
    filled = int(width * current / max(total, 1))
    bar    = "█" * filled + "░" * (width - filled)
    pct    = current / max(total, 1) * 100
    return f"{color}{bar}{C.RESET} {pct:5.1f}% ({current}/{total})"


def file_count(directory, pattern="*"):
    try:
        return len([f for f in Path(directory).glob(pattern)
                    if f.name != ".gitkeep"])
    except Exception:
        return 0


def format_size(path):
    try:
        total = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())
        if total > 1024 * 1024:
            return f"{total / 1024 / 1024:.1f} MB"
        return f"{total / 1024:.0f} KB"
    except Exception:
        return "—"


def clear():
    os.system("cls" if os.name == "nt" else "clear")


# ── Check if setup is running ─────────────────────────────────────────────────
def is_setup_running():
    """Check for any python process running setup.py"""
    try:
        import subprocess
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
            capture_output=True, text=True, timeout=3
        )
        return "python.exe" in result.stdout
    except Exception:
        return True  # Assume running if we can't check


# ── Main monitor loop ─────────────────────────────────────────────────────────
def monitor():
    start_time = datetime.now()

    print(f"\n{C.CYAN}{C.BOLD}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║        MarketPulse AI — Training Monitor                ║")
    print("║     Auto-refreshes every 5 seconds · Ctrl+C to quit    ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(C.RESET)
    time.sleep(2)

    phase_estimates = {
        "Waiting to start":    0,
        "Checking API keys":   2,
        "Downloading data":    600,   # 10 min
        "Feature engineering": 180,   # 3 min
        "Regime detector":     60,    # 1 min
        "Training models":     900,   # 15 min
        "Backtesting":         120,   # 2 min
        "Complete":            0,
    }

    while True:
        try:
            elapsed      = datetime.now() - start_time
            elapsed_str  = str(elapsed).split(".")[0]

            # ── Count files ───────────────────────────────────────────────────
            csv_files      = file_count(PROCESSED_DIR, "*.csv")
            parquet_files  = file_count(PROCESSED_DIR, "*.parquet")
            model_files    = file_count(MODELS_DIR, "*.pkl")
            model_cbm      = file_count(MODELS_DIR, "*.cbm")
            total_models   = model_files + model_cbm

            # Determine current phase
            if total_models >= TOTAL_STOCKS:
                phase = "Complete"
            elif total_models > 0:
                phase = "Training models"
            elif parquet_files > 0 or (csv_files > TOTAL_STOCKS):
                phase = "Feature engineering"
            elif csv_files > 0:
                phase = "Downloading data"
            else:
                phase = "Waiting to start / Checking API keys"

            clear()

            # ── Header ────────────────────────────────────────────────────────
            print(f"\n{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════════════════╗")
            print(f"║        📈 MarketPulse AI — Training Progress Monitor    ║")
            print(f"╚══════════════════════════════════════════════════════════╝{C.RESET}")
            print(f"  {C.DIM}Started: {start_time.strftime('%H:%M:%S')}  |  "
                  f"Elapsed: {elapsed_str}  |  "
                  f"Now: {datetime.now().strftime('%H:%M:%S IST')}{C.RESET}")
            print()

            # ── Current phase ─────────────────────────────────────────────────
            phase_icon = {
                "Waiting to start / Checking API keys": "⏳",
                "Downloading data":    "📥",
                "Feature engineering": "⚙️ ",
                "Training models":     "🤖",
                "Complete":            "✅",
            }.get(phase, "🔄")

            phase_color = C.GREEN if phase == "Complete" else C.YELLOW
            print(f"  {C.BOLD}Current Phase:{C.RESET} {phase_color}{phase_icon} {phase}{C.RESET}")
            print()

            # ── Step 5: Data Download ─────────────────────────────────────────
            print(f"  {C.BOLD}Step 5 — Data Download (2015→2025){C.RESET}")
            print(f"  {progress_bar(csv_files, TOTAL_STOCKS, color=C.BLUE)}")

            data_size = format_size(PROCESSED_DIR)
            print(f"  {C.DIM}CSV files: {csv_files}/{TOTAL_STOCKS}  |  "
                  f"Dir size: {data_size}{C.RESET}")
            print()

            # ── Step 6: Feature Engineering ───────────────────────────────────
            effective_parquet = min(parquet_files, TOTAL_STOCKS)
            print(f"  {C.BOLD}Step 6 — Feature Engineering (50+ indicators){C.RESET}")
            print(f"  {progress_bar(effective_parquet, TOTAL_STOCKS, color=C.CYAN)}")
            print(f"  {C.DIM}Parquet files: {parquet_files}/{TOTAL_STOCKS}{C.RESET}")
            print()

            # ── Step 7: Regime Detector ───────────────────────────────────────
            regime_done = (MODELS_DIR / "regime_model.pkl").exists()
            regime_icon = f"{C.GREEN}✅ Done{C.RESET}" if regime_done else f"{C.YELLOW}⏳ Pending{C.RESET}"
            print(f"  {C.BOLD}Step 7 — Regime Detector (HMM){C.RESET}  {regime_icon}")
            print()

            # ── Step 8: Model Training ────────────────────────────────────────
            print(f"  {C.BOLD}Step 8 — Model Training (LightGBM + CatBoost){C.RESET}")
            print(f"  {progress_bar(total_models, TOTAL_STOCKS, color=C.MAGENTA)}")

            model_size = format_size(MODELS_DIR)
            print(f"  {C.DIM}.pkl models: {model_files}  |  "
                  f".cbm models: {model_cbm}  |  "
                  f"Dir size: {model_size}{C.RESET}")

            # List recently trained models
            try:
                recent_models = sorted(
                    MODELS_DIR.glob("*.pkl"),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True
                )[:5]
                if recent_models:
                    print(f"\n  {C.DIM}Recently trained:{C.RESET}")
                    for m in recent_models:
                        mtime = datetime.fromtimestamp(m.stat().st_mtime).strftime("%H:%M:%S")
                        print(f"  {C.GREEN}  ✓{C.RESET} {m.stem:<30} {C.DIM}{mtime}{C.RESET}")
            except Exception:
                pass
            print()

            # ── Step 9: Backtesting ───────────────────────────────────────────
            backtest_done = (MODELS_DIR / "backtest_results.json").exists()
            bt_icon = f"{C.GREEN}✅ Done{C.RESET}" if backtest_done else f"{C.YELLOW}⏳ Pending{C.RESET}"
            print(f"  {C.BOLD}Step 9 — Backtesting{C.RESET}  {bt_icon}")
            print()

            # ── Overall progress ──────────────────────────────────────────────
            steps_done = sum([
                csv_files >= TOTAL_STOCKS,
                parquet_files >= TOTAL_STOCKS,
                regime_done,
                total_models >= TOTAL_STOCKS,
                backtest_done,
            ])
            print(f"  {C.BOLD}Overall Progress:{C.RESET}")
            print(f"  {progress_bar(steps_done, 5, color=C.GREEN)}")
            print()

            # ── ETA estimate ──────────────────────────────────────────────────
            if phase == "Complete":
                print(f"  {C.GREEN}{C.BOLD}🎉 SETUP COMPLETE! All models trained.{C.RESET}")
                print(f"\n  Next steps:")
                print(f"  {C.CYAN}  python test_pipeline.py{C.RESET}  — Run integration test")
                print(f"  {C.CYAN}  streamlit run dashboard/app.py{C.RESET}  — Launch dashboard")
                print()
                break
            else:
                # Rough ETA based on phase
                eta_mins = {
                    "Waiting to start / Checking API keys": 25,
                    "Downloading data":    int(15 - elapsed.seconds/60) if elapsed.seconds < 900 else 5,
                    "Feature engineering": int(20 - elapsed.seconds/60) if elapsed.seconds < 1200 else 3,
                    "Training models":     int(25 - elapsed.seconds/60) if elapsed.seconds < 1500 else 5,
                }.get(phase, 5)

                eta_time = (datetime.now() + timedelta(minutes=max(1, eta_mins))).strftime("%H:%M:%S")
                print(f"  {C.DIM}⏱  Estimated completion: ~{max(1, eta_mins)} min (around {eta_time} IST){C.RESET}")

            print(f"\n  {C.DIM}[Auto-refreshes every 5s · Ctrl+C to exit monitor]{C.RESET}\n")
            time.sleep(5)

        except KeyboardInterrupt:
            print(f"\n{C.YELLOW}Monitor stopped. setup.py continues running in background.{C.RESET}\n")
            sys.exit(0)
        except Exception as e:
            print(f"\n{C.RED}Monitor error: {e}{C.RESET}")
            time.sleep(5)


if __name__ == "__main__":
    monitor()
