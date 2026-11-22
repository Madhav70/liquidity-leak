"""Monte Carlo simulation of a liquidity pool facing arbitrageurs and noise traders.

Each step (one minute by default):
  1. The reference price moves (GBM).
  2. An arbitrageur trades the pool back to the edge of the no-arbitrage band.
  3. With probability `trade_prob`, an uninformed ("noise") trader arrives with a
     random order. She compares the all-in cost on the AMM with the cost on a
     centralised limit order book plus her personal switching cost of using
     the CEX, and trades on the cheaper venue.

LP performance is measured against the *rebalancing portfolio* of Milionis,
Moallemi, Roughgarden & Zhang (2022): a portfolio that holds, at every
instant, the same amount of X as the pool but trades at the fair reference
price. The difference
        LP excess = (pool value + fee income) - rebalancing portfolio
isolates what LPs earn from fees net of what they lose to arbitrageurs
("loss-versus-rebalancing", LVR). With no fees and continuous arbitrage,
LVR accrues at rate sigma^2 / 8 per unit of pool value per year.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import amm
from .orderbook import OrderBook
from .prices import MINUTES_PER_YEAR, gbm_paths


@dataclass
class PoolConfig:
    p0: float = 2000.0           # initial price of X in Y
    x0: float = 1000.0           # initial X reserve  -> pool value 4,000,000 Y
    sigma: float = 0.8           # annualised volatility of X
    days: float = 30.0
    n_paths: int = 200
    seed: int = 7
    # noise traders
    trade_prob: float = 0.10     # chance a noise trader arrives each minute
    size_median: float = 2.0     # median order size, units of X (lognormal)
    size_logsd: float = 1.0
    switch_cost_mean_bps: float = 25.0   # mean personal cost of using the CEX
    route: bool = True           # if False, every noise trade goes to the AMM
    book: OrderBook = field(default_factory=OrderBook)

    @property
    def n_steps(self) -> int:
        return int(round(self.days * 24 * 60))

    @property
    def years(self) -> float:
        return self.n_steps / MINUTES_PER_YEAR


def _book_cost_bps(book: OrderBook, q: np.ndarray) -> np.ndarray:
    return book.cost_bps_closed_form(q)


def run(cfg: PoolConfig, fees) -> dict:
    """Simulate one configuration for one or several fee levels.

    fees: scalar or 1-D array of fee rates (e.g. 0.003 = 30 bps). All fee
    levels see *the same* price paths and the same noise-trader draws
    (common random numbers), so differences across fees are not noise.

    Returns a dict of arrays with shape (n_fees, n_paths), values in Y.
    """
    fees = np.atleast_1d(np.asarray(fees, dtype=float))
    nf, npaths = len(fees), cfg.n_paths
    prices = gbm_paths(cfg.p0, cfg.sigma, cfg.n_steps, npaths, seed=cfg.seed)
    rng = np.random.default_rng(cfg.seed + 1)

    # Columns = (fee level, path) flattened; price paths tiled across fees.
    fee = np.repeat(fees, npaths)
    ncol = nf * npaths
    x = np.full(ncol, cfg.x0)
    y = np.full(ncol, cfg.x0 * cfg.p0)
    v0 = cfg.x0 * cfg.p0 * 2.0

    reb = np.full(ncol, v0)        # rebalancing-portfolio value
    fee_arb = np.zeros(ncol)       # fee income from arbitrageurs (in Y)
    fee_noise = np.zeros(ncol)     # fee income from noise traders (in Y)
    arb_profit = np.zeros(ncol)
    noise_volume_amm = np.zeros(ncol)   # in Y
    noise_volume_all = np.zeros(ncol)

    p_prev = np.tile(prices[0], nf)
    for t in range(1, cfg.n_steps + 1):
        p = np.tile(prices[t], nf)
        # 1. benchmark: hold the pool's X, trade at fair price
        reb += x * (p - p_prev)
        # 2. arbitrage
        res = amm.arbitrage(x, y, p, fee)
        x, y = res["x"], res["y"]
        fee_arb += res["fee_x"] * p + res["fee_y"]
        arb_profit += res["arb_profit"]
        # 3. noise trader (same draw for every fee level on a given path)
        arrive = rng.random(npaths) < cfg.trade_prob
        if np.any(arrive):
            q1 = cfg.size_median * np.exp(cfg.size_logsd * rng.standard_normal(npaths))
            side1 = np.where(rng.random(npaths) < 0.5, 1, -1)
            switch1 = rng.exponential(cfg.switch_cost_mean_bps, npaths)
            q, side = np.tile(q1, nf), np.tile(side1, nf)
            switch, live = np.tile(switch1, nf), np.tile(arrive, nf)

            bx, by, paid, fy = amm.buy_x(x, y, q, fee)
            sx, sy, got, fx = amm.sell_x(x, y, q, fee)
            cost_amm = np.where(side > 0, (paid / (q * p) - 1.0),
                                (1.0 - got / (q * p))) * 1e4
            cost_cex = _book_cost_bps(cfg.book, q) + switch
            use_amm = live & ((cost_amm <= cost_cex) | (not cfg.route))

            buy = use_amm & (side > 0)
            sell = use_amm & (side < 0)
            x = np.where(buy, bx, np.where(sell, sx, x))
            y = np.where(buy, by, np.where(sell, sy, y))
            fee_noise += np.where(buy, fy, 0.0) + np.where(sell, fx * p, 0.0)
            noise_volume_amm += np.where(use_amm, q * p, 0.0)
            noise_volume_all += np.where(live, q * p, 0.0)
        p_prev = p

    p_T = np.tile(prices[-1], nf)
    pool_T = x * p_T + y
    hodl_T = cfg.x0 * p_T + cfg.x0 * cfg.p0
    fees_total = fee_arb + fee_noise

    def shape(a):
        return a.reshape(nf, npaths)

    return {
        "fees": fees,
        "v0": v0,
        "years": cfg.years,
        "pool_T": shape(pool_T),
        "hodl_T": shape(hodl_T),
        "reb_T": shape(reb),
        "fee_arb": shape(fee_arb),
        "fee_noise": shape(fee_noise),
        "arb_profit": shape(arb_profit),
        "lp_excess": shape(pool_T + fees_total - reb),
        "lp_vs_hodl": shape(pool_T + fees_total - hodl_T),
        "noise_volume_amm": shape(noise_volume_amm),
        "noise_volume_all": shape(noise_volume_all),
        "price_ratio": prices[-1] / prices[0],
    }


def annualised_pct(values: np.ndarray, v0: float, years: float) -> np.ndarray:
    """Convert a P&L in Y into % of initial pool value per year."""
    return values / v0 / years * 100.0
