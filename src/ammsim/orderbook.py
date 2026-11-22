"""A stylised limit order book (LOB), as on a centralised exchange.

A market maker posts a ladder of limit orders around the reference price p:
level j (j = 0, 1, 2, ...) sits at a relative distance  half_spread + j * tick
from p, and each level holds `depth` units of X. A market order "walks the
book": it fills the best level first, then the next, and so on.

This is deliberately simple - real books are deeper near the touch and
change shape over time - but it captures the key contrast with an AMM:
a LOB's cost is a spread plus a step-wise impact, whereas an AMM's impact
grows smoothly with trade size relative to pool reserves.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class OrderBook:
    half_spread: float = 0.0005   # 5 bps from mid to the best quote
    tick: float = 0.0001          # 1 bp between successive levels
    depth: float = 5.0            # units of X resting at each level
    n_levels: int = 500

    def levels(self, p: float, side: int) -> tuple[np.ndarray, np.ndarray]:
        """Prices and sizes a market order of the given side would hit.

        side = +1 (buy X) hits the asks above p; side = -1 hits the bids below.
        """
        j = np.arange(self.n_levels)
        rel = self.half_spread + j * self.tick
        prices = p * (1.0 + side * rel)
        sizes = np.full(self.n_levels, self.depth)
        return prices, sizes

    def fill(self, p: float, q: float, side: int) -> float:
        """Average execution price for a market order of q units of X."""
        if q <= 0:
            raise ValueError("order size must be positive")
        prices, sizes = self.levels(p, side)
        cum = np.cumsum(sizes)
        if q > cum[-1]:
            raise ValueError("order exceeds total book depth")
        full = np.searchsorted(cum, q)          # index of last level touched
        filled_before = cum[full - 1] if full > 0 else 0.0
        notional = np.sum(prices[:full] * sizes[:full])
        notional += prices[full] * (q - filled_before)
        return notional / q

    def execution_cost_bps(self, p: float, q: float, side: int) -> float:
        avg = self.fill(p, q, side)
        return side * (avg / p - 1.0) * 1e4

    def cost_bps_closed_form(self, q: np.ndarray) -> np.ndarray:
        """Vectorised execution cost in bps for many order sizes at once
        (cost does not depend on p or side for this symmetric book)."""
        q = np.asarray(q, dtype=float)
        n_full = np.floor(q / self.depth)
        rem = q - n_full * self.depth
        # sum over full levels of (h + j*tick)*depth, plus the partial level
        full_sum = self.depth * (n_full * self.half_spread
                                 + self.tick * n_full * (n_full - 1) / 2.0)
        part = rem * (self.half_spread + n_full * self.tick)
        return (full_sum + part) / q * 1e4
