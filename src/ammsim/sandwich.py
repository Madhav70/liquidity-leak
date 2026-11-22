"""Sandwich attacks (front-running) on an AMM.

A victim submits "buy q units of X" with a slippage tolerance tau: the trade
reverts if the price she pays exceeds (1 + tau) times the price quoted when
she signed it. A block builder / searcher who sees the pending order can:

  1. front-run: buy a units of X first, pushing the pool price up;
  2. let the victim trade at the worse price (still within her tolerance);
  3. back-run: sell the a units back into the now-higher-priced pool.

The attacker picks the largest front-run a that keeps the victim's trade
inside her tolerance; larger tolerance -> larger attack -> larger loss.
"""
from __future__ import annotations

import numpy as np

from . import amm


def victim_avg_price(x, y, q, fee):
    _, _, paid, _ = amm.buy_x(x, y, q, fee)
    return paid / q


def sandwich(x: float, y: float, q: float, tau: float, fee: float,
             tol: float = 1e-10) -> dict:
    """Optimal sandwich against a buy order of q X with slippage tolerance tau.

    Returns attacker profit (in Y), the victim's extra cost versus trading
    without the attack (in Y), and the front-run size.
    """
    quoted = victim_avg_price(x, y, q, fee)
    limit = quoted * (1.0 + tau)

    def victim_price_after(a):
        x1, y1, _, _ = amm.buy_x(x, y, a, fee)
        return victim_avg_price(x1, y1, q, fee)

    # bisection on front-run size a in [0, a_max): victim price increases in a
    lo, hi = 0.0, (x - q) * 0.999
    if victim_price_after(hi) <= limit:
        lo = hi
    else:
        while hi - lo > tol * max(1.0, x):
            mid = 0.5 * (lo + hi)
            if victim_price_after(mid) <= limit:
                lo = mid
            else:
                hi = mid
    a = lo

    # execute the three trades
    x1, y1, cost_front, _ = amm.buy_x(x, y, a, fee)
    x2, y2, victim_paid, _ = amm.buy_x(x1, y1, q, fee)
    _, _, back_proceeds, _ = amm.sell_x(x2, y2, a, fee)
    profit = back_proceeds - cost_front
    if profit <= 0:          # attack not worth it (fees exceed the gain)
        return {"front_run_size": 0.0, "attacker_profit": 0.0,
                "victim_extra_cost": 0.0, "victim_paid": quoted * q}
    return {
        "front_run_size": a,
        "attacker_profit": profit,
        "victim_extra_cost": victim_paid - quoted * q,
        "victim_paid": victim_paid,
    }


def sandwich_curve(x, y, q, taus, fee):
    rows = [sandwich(x, y, q, t, fee) for t in np.atleast_1d(taus)]
    return {k: np.array([r[k] for r in rows]) for k in rows[0]}
