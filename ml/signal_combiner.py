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

import math
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


# ── combine_with_news_signal: ML + News Agent (Bayesian Dynamic Updating) ────

def combine_with_news_signal(ml_signal: dict, news_signal: dict) -> dict:
    """
    Merge ML combined signal with News Agent impact score using Bayesian Dynamic Updating.

    Bayesian Principles Applied:
      1. Prior Odds: Calculated from Calibrated ML Probability (p_ml).
      2. News Likelihood Ratio (LR_news): Log-odds shift derived from News Direction,
         LLM Confidence, and Severity Weight.
      3. Posterior Odds: Odds_posterior = Odds_ML * LR_news.
      4. Self-Correction: When ML prior and News Likelihood conflict, Bayes' Rule
         mathematically pulls posterior probability towards 0.50 (neutrality),
         which naturally shrinks confidence without hardcoded hacks.
    """
    ticker = ml_signal.get("ticker", "UNKNOWN")

    ml_prob      = float(ml_signal.get("final_probability_up", 0.5))
    ml_dir       = ml_signal.get("final_direction", "bearish")

    news_dir     = news_signal.get("direction", "neutral")
    news_conf    = float(news_signal.get("confidence", 0.0))
    news_sev     = news_signal.get("severity", "minor")
    news_reason  = news_signal.get("reasoning", "")

    # Bound ML prior probability to prevent division by zero in odds
    p_ml = max(0.01, min(0.99, ml_prob))
    odds_ml = p_ml / (1.0 - p_ml)

    # Severity scale factor for News Likelihood Ratio
    severity_scale = {"minor": 0.6, "moderate": 1.0, "major": 1.8}
    eff_severity = severity_scale.get(news_sev, 0.6)

    # Direction multiplier: +1.5 for bullish, -1.5 for bearish, 0 for neutral
    dir_mult = 1.5 if news_dir == "bullish" else (-1.5 if news_dir == "bearish" else 0.0)

    # Log-Likelihood Ratio shift
    delta_log_odds = eff_severity * news_conf * dir_mult
    lr_news = math.exp(delta_log_odds)

    # Compute Bayesian Posterior Odds & Probability
    odds_posterior = odds_ml * lr_news
    final_prob = odds_posterior / (1.0 + odds_posterior)
    final_prob = float(max(0.01, min(0.99, final_prob)))

    final_direction  = "bullish" if final_prob > 0.5 else "bearish"
    final_confidence = round(abs(final_prob - 0.5) * 2, 4)

    # Signals agreement & conflict check
    signals_agree = (ml_dir == news_dir) or news_dir == "neutral"
    conflicting   = not signals_agree and news_conf > 0.4
    news_override = (news_sev == "major" and news_conf > 0.8 and conflicting)

    if news_override:
        logger.info(
            f"  {ticker}: BAYESIAN MAJOR NEWS SHIFT — {news_dir.upper()} "
            f"(conf={news_conf:.2f}, LR={lr_news:.2f}) updated ML prior ({ml_prob:.3f} → {final_prob:.3f})"
        )
    elif conflicting:
        logger.warning(
            f"  {ticker}: BAYESIAN CONFLICT DAMPENING — ML={ml_dir} ({ml_prob:.3f}) vs News={news_dir} "
            f"(Posterior={final_prob:.3f}, Confidence={final_confidence:.3f})"
        )
    else:
        logger.info(
            f"  {ticker}: BAYESIAN FUSION — ML+News → {final_direction.upper()} "
            f"(prob={final_prob:.3f}, conf={final_confidence:.3f})"
        )

    return {
        "ticker":                ticker,
        "final_probability_up":  round(final_prob, 4),
        "final_direction":       final_direction,
        "final_confidence":      final_confidence,
        "signal_sources":        ["lgbm", "chronos", "regime", "news_bayesian"],
        "signals_agree":         signals_agree,
        "conflicting_signals":   conflicting,
        "news_override":         news_override,
        "bayes_lr_news":         round(lr_news, 4),
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
