"""Cross-sectional backtester.

Look-ahead prevention is structural, not a setting: the panel is built from
envelope rows, and at each rebalance date the engine can only see rows whose
`known_at` is strictly before that date. There is no flag to turn it off.

Costs are always on. There is no zero-cost mode, because a zero-cost backtest
is not a backtest.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from . import honesty

TRADING_DAYS = 252

SIGNALS = {
    "momentum_12_1": "12-month return skipping the most recent month (Jegadeesh-Titman)",
    "momentum_6_1": "6-month return skipping the most recent month",
    "reversal_1m": "negative of last month's return (short-term reversal)",
    "low_volatility": "negative of trailing 12-month volatility",
    "trend_200d": "price relative to its 200-day moving average",
}


def panel(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Envelope rows -> a dates x entities frame, keyed on `known_at`.

    Indexing on `known_at` rather than `observed_at` is the whole trick: a
    value enters the panel on the day it became knowable, so any slice of the
    index is automatically a point-in-time view.
    """
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame = frame.dropna(subset=["known_at", "value"])
    frame["known_at"] = pd.to_datetime(frame["known_at"])
    # Last value wins if a period was restated before the same known_at.
    wide = frame.pivot_table(
        index="known_at", columns="entity", values="value", aggfunc="last"
    )
    return wide.sort_index()


def _signal(prices: pd.DataFrame, name: str) -> pd.DataFrame:
    if name == "momentum_12_1":
        return prices.shift(21) / prices.shift(252) - 1.0
    if name == "momentum_6_1":
        return prices.shift(21) / prices.shift(126) - 1.0
    if name == "reversal_1m":
        return -(prices / prices.shift(21) - 1.0)
    if name == "low_volatility":
        return -prices.pct_change().rolling(252).std()
    if name == "trend_200d":
        return prices / prices.rolling(200).mean() - 1.0
    raise ValueError(f"Unknown signal {name!r}. Available: {', '.join(SIGNALS)}")


def run(
    prices: pd.DataFrame,
    *,
    signal: str = "momentum_12_1",
    rebalance: str = "ME",
    long_pct: float = 0.2,
    short_pct: float = 0.0,
    cost_bps: float = 10.0,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    """Rank, hold, rebalance, charge costs. Returns stats plus an honesty report."""
    if prices.empty:
        raise ValueError("No price data — nothing to backtest")

    prices = prices.sort_index().ffill()
    if start:
        prices = prices.loc[prices.index >= pd.Timestamp(start)]
    if end:
        prices = prices.loc[prices.index <= pd.Timestamp(end)]

    if len(prices) < 300:
        raise ValueError(
            f"Only {len(prices)} trading days available. A cross-sectional "
            "backtest needs at least ~300 to form a 12-month signal."
        )

    scores = _signal(prices, signal)
    daily_returns = prices.pct_change()

    rebalance_dates = prices.resample(rebalance).last().index
    rebalance_dates = [d for d in rebalance_dates if d in prices.index]

    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    holdings: pd.Series | None = None
    turnover_log: list[tuple[pd.Timestamp, float]] = []

    for date in rebalance_dates:
        # Strictly before the rebalance date: the signal cannot peek at today.
        available = scores.loc[scores.index < date]
        if available.empty:
            continue
        latest = available.iloc[-1].dropna()
        if len(latest) < 4:
            continue

        ranked = latest.sort_values(ascending=False)
        n_long = max(1, int(round(len(ranked) * long_pct)))
        target = pd.Series(0.0, index=prices.columns)
        target[ranked.index[:n_long]] = 1.0 / n_long

        if short_pct > 0:
            n_short = max(1, int(round(len(ranked) * short_pct)))
            target[ranked.index[-n_short:]] = -1.0 / n_short

        if holdings is not None:
            turnover_log.append((date, float((target - holdings).abs().sum())))
        else:
            turnover_log.append((date, float(target.abs().sum())))

        holdings = target
        weights.loc[weights.index >= date] = target.values

    if holdings is None:
        raise ValueError("Signal never produced enough cross-section to trade")

    gross = (weights.shift(1) * daily_returns).sum(axis=1)

    costs = pd.Series(0.0, index=gross.index)
    for date, turnover in turnover_log:
        if date in costs.index:
            costs.loc[date] = turnover * (cost_bps / 10_000.0)

    net = (gross - costs).dropna()
    net = net.loc[net.index >= pd.Timestamp(rebalance_dates[0])]

    stats = _stats(net)
    stats["gross_annual_return"] = _annualized(gross.dropna())
    stats["cost_drag_annual"] = round(
        stats["gross_annual_return"] - stats["annual_return"], 4
    )
    stats["average_turnover_per_rebalance"] = round(
        float(np.mean([t for _, t in turnover_log])), 3
    )
    stats["rebalances"] = len(turnover_log)

    spec = {
        "signal": signal,
        "rebalance": rebalance,
        "long_pct": long_pct,
        "short_pct": short_pct,
        "cost_bps": cost_bps,
        "universe_size": int(prices.shape[1]),
        "start": str(net.index[0].date()),
        "end": str(net.index[-1].date()),
    }

    # Deflated Sharpe is defined at the observation frequency. Feeding it an
    # annualized Sharpe alongside a daily observation count would overstate
    # significance by roughly sqrt(252), which is exactly the kind of quiet
    # error this module exists to catch.
    per_obs_sharpe = (
        float(net.mean() / net.std()) if float(net.std()) > 0 else 0.0
    )
    trials = honesty.record_trial(spec, per_obs_sharpe)

    report = honesty.deflated_sharpe(
        per_obs_sharpe,
        n_obs=len(net),
        skew=float(net.skew()),
        kurtosis=float(net.kurtosis() + 3.0),
        trials=trials,
    )
    report["specs_tried_this_session"] = trials
    report["annualized_sharpe"] = stats["sharpe"]

    split = len(net) // 2
    report["first_half_sharpe"] = _stats(net.iloc[:split])["sharpe"]
    report["second_half_sharpe"] = _stats(net.iloc[split:])["sharpe"]

    return {
        "spec": spec,
        "stats": stats,
        "honesty": report,
        "returns": {str(d.date()): round(float(v), 6) for d, v in net.items()},
    }


def _annualized(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    total = float((1 + returns).prod())
    years = len(returns) / TRADING_DAYS
    if years <= 0 or total <= 0:
        return 0.0
    return round(total ** (1 / years) - 1, 4)


def _stats(returns: pd.Series) -> dict[str, Any]:
    if returns.empty:
        return {"sharpe": 0.0, "annual_return": 0.0, "annual_volatility": 0.0}
    vol = float(returns.std() * np.sqrt(TRADING_DAYS))
    mean = float(returns.mean() * TRADING_DAYS)
    curve = (1 + returns).cumprod()
    drawdown = curve / curve.cummax() - 1.0
    return {
        "sharpe": round(mean / vol, 3) if vol > 0 else 0.0,
        "annual_return": _annualized(returns),
        "annual_volatility": round(vol, 4),
        "max_drawdown": round(float(drawdown.min()), 4),
        "hit_rate": round(float((returns > 0).mean()), 4),
        "observations": len(returns),
    }
