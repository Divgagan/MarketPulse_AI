"""
ml/signal_combiner.py — MarketPulse AI
========================================
Blueprint Part 9: Weighted ensemble of all ML signals into one final score.

Two functions:
  1. combine_signals()          : Merges LightGBM + Chronos + HMM Regime
  2. combine_with_news_signal() : Adds News Agent signal on top of ML signal

WEIGHTING SCHEME (ML-only signals):
  LightGBM : 60%  — core directional predictor, trained on 40+ features
  Chronos   : 30%  — zero-shot temporal forecaster, adds trajectory context
  Regime    : 10%  — macro bias adjustment (bull/bear/sideways from HMM)

WEIGHTING SCHEME (ML + News combined):
  ML signal  : 60%
  News signal: 40%
  (Major news with confidence > 0.8 overrides ML entirely)
"""

import logging

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("signal_combiner")

# Regime bias adjustments — bull adds slight upward nudge, bear adds downward
REGIME_BIAS = {
    "bull":     +0.03,   # +3% boost to probability_up in bull market
    "sideways":  0.00,   # no adjustment
    "bear":     -0.03,   # -3% drag to probability_up in bear market
}


# ── combine_signals: ML-only ensemble ────────────────────────────────────────

def combine_signals(lgbm_pred: dict, chronos_pred: dict, regime: str) -> dict:
    """
    Combine LightGBM + Chronos + HMM Regime into one final ML signal.

    Args:
        lgbm_pred    : Output from StockPredictor.predict() or model_trainer
                       Must have: probability_up, predicted_direction, confidence
        chronos_pred : Output from ChronosForecaster.forecast_direction()
                       Must have: chronos_direction, chronos_confidence
        regime       : One of "bull", "bear", "sideways" (from MarketRegimeDetector)

    Returns:
        dict: {
            ticker               : str,
            final_probability_up : float (0.0–1.0),
            final_direction      : "bullish" / "bearish",
            final_confidence     : float (0.0–1.0),
            signal_sources       : ["lgbm", "chronos", "regime"],
            signals_agree        : bool,
            ml_only_signal       : True,
        }
    """
    ticker   = lgbm_pred.get("ticker", "UNKNOWN")
    lgbm_prob = float(lgbm_pred.get("probability_up", 0.5))
    lgbm_dir  = lgbm_pred.get("predicted_direction", "neutral")

    chronos_dir  = chronos_pred.get("chronos_direction", "neutral")
    chronos_conf = float(chronos_pred.get("chronos_confidence", 0.0))

    # ── Step 1: Base probability from LightGBM (60% weight) ──────────────────
    combined_prob = lgbm_prob * 0.6

    # ── Step 2: Chronos adjustment (30% weight) ───────────────────────────────
    # Chronos gives direction, not probability — convert to probability
    if chronos_dir == "bullish":
        chronos_prob = 0.5 + (chronos_conf * 0.5)   # 0.5 → 1.0 range
    elif chronos_dir == "bearish":
        chronos_prob = 0.5 - (chronos_conf * 0.5)   # 0.5 → 0.0 range
    else:
        chronos_prob = 0.5                           # neutral = 50/50

    combined_prob += chronos_prob * 0.3

    # ── Step 3: Regime bias adjustment (10% weight) ───────────────────────────
    regime_bias     = REGIME_BIAS.get(str(regime).lower(), 0.0)
    regime_prob     = 0.5 + regime_bias              # 0.47 / 0.50 / 0.53
    combined_prob  += regime_prob * 0.1

    # Clip to valid probability range
    combined_prob = float(max(0.01, min(0.99, combined_prob)))

    # ── Step 4: Final direction ───────────────────────────────────────────────
    final_direction = "bullish" if combined_prob > 0.5 else "bearish"

    # ── Step 5: Confidence (how far from 0.5, scaled 0–1) ────────────────────
    final_confidence = round(abs(combined_prob - 0.5) * 2, 4)

    # ── Step 6: signals_agree check ───────────────────────────────────────────
    # True if all three sources agree on direction
    regime_direction = "bullish" if regime == "bull" else ("bearish" if regime == "bear" else "neutral")
    all_directions   = [lgbm_dir, chronos_dir, regime_direction]
    bullish_votes    = sum(1 for d in all_directions if d == "bullish")
    bearish_votes    = sum(1 for d in all_directions if d == "bearish")
    signals_agree    = (bullish_votes == 3) or (bearish_votes == 3)

    result = {
        "ticker":                ticker,
        "final_probability_up":  round(combined_prob, 4),
        "final_direction":       final_direction,
        "final_confidence":      final_confidence,
        "signal_sources":        ["lgbm", "chronos", "regime"],
        "signals_agree":         signals_agree,
        "ml_only_signal":        True,
        # Debug breakdown
        "_lgbm_prob":            round(lgbm_prob, 4),
        "_chronos_prob":         round(chronos_prob, 4),
        "_regime_bias":          regime_bias,
    }

    logger.info(
        f"  {ticker}: ML signal → {final_direction.upper()} "
        f"(prob={combined_prob:.3f}, conf={final_confidence:.3f}, "
        f"agree={signals_agree}, regime={regime})"
    )
    return result


# ── combine_with_news_signal: ML + News Agent ─────────────────────────────────

def combine_with_news_signal(ml_signal: dict, news_signal: dict) -> dict:
    """
    Merge ML combined signal with News Agent impact score into final signal.

    Args:
        ml_signal   : Output from combine_signals() above
                      Must have: ticker, final_probability_up, final_direction,
                                 final_confidence
        news_signal : Output from Agent 4 (ImpactScore aggregated per ticker)
                      Must have: direction, confidence, severity
                      direction = "bullish" / "bearish" / "neutral"
                      severity  = "minor" / "moderate" / "major"
                      confidence = float 0.0–1.0

    Returns:
        Full merged signal dict with reasoning, conflict flags, and override info.
    """
    ticker = ml_signal.get("ticker", "UNKNOWN")

    ml_prob      = float(ml_signal.get("final_probability_up", 0.5))
    ml_dir       = ml_signal.get("final_direction", "bearish")
    ml_conf      = float(ml_signal.get("final_confidence", 0.0))

    news_dir     = news_signal.get("direction", "neutral")
    news_conf    = float(news_signal.get("confidence", 0.0))
    news_sev     = news_signal.get("severity", "minor")
    news_reason  = news_signal.get("reasoning", "")

    # ── Special Case: MAJOR news override ────────────────────────────────────
    # If news is a high-confidence major event, it overrides ML entirely
    # (earnings shock, RBI surprise rate cut, geopolitical crisis etc.)
    if news_sev == "major" and news_conf > 0.8:
        if news_dir == "bullish":
            final_prob = max(ml_prob, 0.80)     # Floor at 80% for major bullish
        elif news_dir == "bearish":
            final_prob = min(ml_prob, 0.20)     # Ceiling at 20% for major bearish
        else:
            final_prob = ml_prob                # Neutral major news → no override

        final_direction  = "bullish" if final_prob > 0.5 else "bearish"
        final_confidence = round(abs(final_prob - 0.5) * 2, 4)
        signals_agree    = (ml_dir == final_direction)
        conflicting      = not signals_agree

        logger.info(
            f"  {ticker}: MAJOR NEWS OVERRIDE — {news_dir.upper()} "
            f"(conf={news_conf:.2f}) overrides ML signal"
        )

        return {
            "ticker":                ticker,
            "final_probability_up":  round(final_prob, 4),
            "final_direction":       final_direction,
            "final_confidence":      final_confidence,
            "signal_sources":        ["lgbm", "chronos", "regime", "news_MAJOR"],
            "signals_agree":         signals_agree,
            "conflicting_signals":   conflicting,
            "news_override":         True,
            "ml_signal":             ml_signal,
            "news_signal":           news_signal,
            "reasoning":             f"Major news override: {news_reason}",
        }

    # ── Normal Case: weighted blend (60% ML, 40% News) ───────────────────────
    # Convert news direction to probability
    if news_dir == "bullish":
        news_prob = 0.5 + (news_conf * 0.5)
    elif news_dir == "bearish":
        news_prob = 0.5 - (news_conf * 0.5)
    else:
        news_prob = 0.5   # neutral news = no adjustment

    # Severity multiplier — major news carries more weight
    severity_weight = {"minor": 0.7, "moderate": 0.85, "major": 1.0}
    news_weight_adj = severity_weight.get(news_sev, 0.7)

    # Weighted blend: 60% ML + 40% News (adjusted for severity)
    final_prob = (ml_prob * 0.60) + (news_prob * 0.40 * news_weight_adj)

    # If severity is minor, remaining weight stays with ML
    if news_sev == "minor":
        remainder = 0.40 * (1.0 - news_weight_adj)
        final_prob += ml_prob * remainder

    final_prob  = float(max(0.01, min(0.99, final_prob)))

    final_direction  = "bullish" if final_prob > 0.5 else "bearish"
    final_confidence = round(abs(final_prob - 0.5) * 2, 4)

    # ── Conflict detection ───────────────────────────────────────────────────
    signals_agree    = (ml_dir == news_dir) or news_dir == "neutral"
    conflicting      = not signals_agree and news_conf > 0.5

    if conflicting:
        # Reduce confidence when ML and News strongly disagree
        final_confidence = round(final_confidence * 0.7, 4)
        logger.warning(
            f"  {ticker}: CONFLICTING SIGNALS — "
            f"ML={ml_dir} vs News={news_dir} "
            f"(confidence reduced to {final_confidence:.3f})"
        )
    else:
        logger.info(
            f"  {ticker}: ML+News → {final_direction.upper()} "
            f"(prob={final_prob:.3f}, conf={final_confidence:.3f}, agree={signals_agree})"
        )

    return {
        "ticker":                ticker,
        "final_probability_up":  round(final_prob, 4),
        "final_direction":       final_direction,
        "final_confidence":      final_confidence,
        "signal_sources":        ["lgbm", "chronos", "regime", "news"],
        "signals_agree":         signals_agree,
        "conflicting_signals":   conflicting,
        "news_override":         False,
        "ml_signal":             ml_signal,
        "news_signal":           news_signal,
        "reasoning":             news_reason,
    }


# ── Main Block ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick unit test
    import logging
    logger.info("Testing signal_combiner...")

    # Simulate inputs
    lgbm = {
        "ticker": "RELIANCE.NS",
        "probability_up": 0.65,
        "predicted_direction": "bullish",
        "confidence": 0.30,
    }
    chronos = {
        "ticker": "RELIANCE.NS",
        "chronos_direction": "bullish",
        "chronos_confidence": 0.72,
    }

    # Test 1: All agree (bull regime)
    result = combine_signals(lgbm, chronos, regime="bull")
    logger.info(f"Test 1 (all agree, bull): {result['final_direction']} prob={result['final_probability_up']}")

    # Test 2: ML bullish, Chronos bearish
    chronos2 = {**chronos, "chronos_direction": "bearish", "chronos_confidence": 0.60}
    result2 = combine_signals(lgbm, chronos2, regime="sideways")
    logger.info(f"Test 2 (conflict): {result2['final_direction']} prob={result2['final_probability_up']} agree={result2['signals_agree']}")

    # Test 3: With news signal
    news = {"direction": "bullish", "confidence": 0.75, "severity": "moderate", "reasoning": "Strong Q4 results beat estimates"}
    result3 = combine_with_news_signal(result, news)
    logger.info(f"Test 3 (ML+News): {result3['final_direction']} prob={result3['final_probability_up']}")

    # Test 4: Major news override
    news_major = {"direction": "bearish", "confidence": 0.90, "severity": "major", "reasoning": "SEBI investigation announced"}
    result4 = combine_with_news_signal(result, news_major)
    logger.info(f"Test 4 (Major override): {result4['final_direction']} override={result4['news_override']}")

    logger.info("signal_combiner module OK.")
