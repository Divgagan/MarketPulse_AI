"""
agents/graph.py — MarketPulse AI
==================================
Blueprint Part 16: LangGraph Full Graph Orchestration.

Wires all 7 agents into a compiled LangGraph StateGraph.

Pipeline flow:
  news_harvester
      ↓
  relevance_filter
      ↓ (conditional: skip entity_mapper if no articles)
  entity_mapper ──────────────────┐
      ↓                           │ (no articles path)
  impact_scorer                   │
      ↓                           │
  market_monitor ← ───────────────┘
      ↓
  signal_aggregator
      ↓
  alert_generator
      ↓
    END

LangSmith tracing is enabled automatically if LANGCHAIN_API_KEY
is set in .env (LANGCHAIN_TRACING_V2=true, PROJECT=marketpulse-ai).

Run types:
  "news_cycle" — every 30 min during market hours (news only)
  "eod_full"   — daily at 3:45 PM (full ML + news pipeline)
"""

import logging
import os
from datetime import datetime, timezone

# ── LangSmith tracing setup (Blueprint requirement) ───────────────────────────
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"]    = "marketpulse-ai"

from langgraph.graph import END, StateGraph

from agents.alert_generator import alert_generator_node
from agents.entity_mapper import entity_mapper_node
from agents.impact_scorer import impact_scorer_node
from agents.market_monitor import market_monitor_node
from agents.news_harvester import news_harvester_node
from agents.relevance_filter import relevance_filter_node
from agents.signal_aggregator import signal_aggregator_node
from agents.state import MarketPulseState, create_initial_state

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("graph")


# ── Conditional Edge: Check if articles passed relevance filter ────────────────

def check_has_articles(state: MarketPulseState) -> str:
    """
    After relevance_filter: if no relevant articles were found,
    skip entity_mapper and impact_scorer — go directly to market_monitor.
    The ML pipeline still runs; we just have no news signal.

    Returns:
        "continue_to_mapper"  — articles found, run full pipeline
        "skip_to_monitor"     — no articles, skip to market_monitor
    """
    count = len(state.get("filtered_articles", []))
    if count == 0:
        logger.info(
            "Relevance filter: 0 articles passed — skipping to market_monitor"
        )
        return "skip_to_monitor"

    logger.info(
        f"Relevance filter: {count} articles passed — continuing to entity_mapper"
    )
    return "continue_to_mapper"


# ── Graph Factory ─────────────────────────────────────────────────────────────

def create_marketpulse_graph():
    """
    Build and compile the full MarketPulse AI LangGraph.

    Returns:
        Compiled LangGraph graph (callable with .invoke())
    """
    graph = StateGraph(MarketPulseState)

    # ── Add all 7 nodes ───────────────────────────────────────────────────────
    graph.add_node("news_harvester",    news_harvester_node)
    graph.add_node("relevance_filter",  relevance_filter_node)
    graph.add_node("entity_mapper",     entity_mapper_node)
    graph.add_node("impact_scorer",     impact_scorer_node)
    graph.add_node("market_monitor",    market_monitor_node)
    graph.add_node("signal_aggregator", signal_aggregator_node)
    graph.add_node("alert_generator",   alert_generator_node)

    # ── Define the flow ───────────────────────────────────────────────────────
    graph.set_entry_point("news_harvester")

    # Linear chain: harvester → filter
    graph.add_edge("news_harvester", "relevance_filter")

    # Conditional edge after relevance filter
    graph.add_conditional_edges(
        "relevance_filter",
        check_has_articles,
        {
            "continue_to_mapper": "entity_mapper",
            "skip_to_monitor":    "market_monitor",
        },
    )

    # Linear chain: mapper → scorer → monitor → aggregator → alerts → END
    graph.add_edge("entity_mapper",     "impact_scorer")
    graph.add_edge("impact_scorer",     "market_monitor")
    graph.add_edge("market_monitor",    "signal_aggregator")
    graph.add_edge("signal_aggregator", "alert_generator")
    graph.add_edge("alert_generator",   END)

    return graph.compile()


# ── Singleton compiled graph ──────────────────────────────────────────────────
marketpulse_graph = create_marketpulse_graph()
logger.info("MarketPulse AI graph compiled: 7 nodes, 1 conditional edge.")


# ── Runner Function ───────────────────────────────────────────────────────────

def run_pipeline(
    run_type: str = "news_cycle",
    ml_predictions: list = None,
) -> dict:
    """
    Run the full MarketPulse AI LangGraph pipeline.

    Args:
        run_type:       "news_cycle" (every 30 min) or "eod_full" (3:45 PM daily)
        ml_predictions: Pre-computed MLPrediction list (for eod_full runs).
                        Pass None for news_cycle (ML runs separately).

    Returns:
        Final MarketPulseState dict with all populated fields.
    """
    logger.info(f"{'=' * 60}")
    logger.info(f"MarketPulse AI Pipeline — run_type={run_type}")
    logger.info(f"{'=' * 60}")

    initial_state = create_initial_state(
        run_type        = run_type,
        ml_predictions  = ml_predictions or [],
    )

    result = marketpulse_graph.invoke(initial_state)

    # Summary log
    n_signals  = len(result.get("final_signals", []))
    n_alerts   = len(result.get("alerts", []))
    n_errors   = len(result.get("errors", []))
    n_warnings = len(result.get("warnings", []))

    logger.info(
        f"Pipeline complete: {n_signals} signals | {n_alerts} alerts | "
        f"{n_errors} errors | {n_warnings} warnings"
    )

    return result


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python -m agents.graph
    logger.info("MarketPulse AI -- Graph Orchestration Module")
    logger.info("Verifying graph structure...")

    # Print graph node list
    try:
        nodes = list(marketpulse_graph.nodes.keys()) if hasattr(marketpulse_graph, 'nodes') else ["(compiled)"]
        logger.info(f"  Graph nodes: {nodes}")
    except Exception:
        logger.info("  Graph compiled successfully (node list not available on compiled graph)")

    logger.info("  Entry point : news_harvester")
    logger.info("  Exit point  : alert_generator → END")
    logger.info("  Conditional : relevance_filter → entity_mapper OR market_monitor")
    logger.info("")
    logger.info("To run the full pipeline:")
    logger.info("  from agents.graph import run_pipeline")
    logger.info("  result = run_pipeline('news_cycle')")
    logger.info("")
    logger.info("Graph module OK — run 'python -m pipeline.eod_pipeline' for full EOD run.")
