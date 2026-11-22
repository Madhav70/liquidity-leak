"""Constant-product automated market maker (Uniswap v2 style).

Notation
--------
x : reserve of the risky token X (e.g. ETH)
y : reserve of the numeraire token Y (e.g. USDC)
k = x * y is the invariant that every swap preserves (net of fees).
P = y / x is the pool's marginal (spot) price of X in units of Y.
fee f is charged on the *input* of every swap; gamma = 1 - f.

Modelling choice: fees are paid to liquidity providers in a separate
account instead of being added back to the reserves (as Uniswap v3 does).
This keeps k constant and makes the accounting of fee income explicit.

All functions are vectorised: x, y and the trade inputs may be numpy
arrays, one entry per simulated path.
"""
from __future__ import annotations

import numpy as np


def spot_price(x, y):
    """Marginal price of X in units of Y."""
    return y / x


def buy_x(x, y, q, fee):
    """Trader buys q units of X from the pool, paying in Y.

    Returns (new_x, new_y, y_paid_gross, fee_in_y).
    y_paid_gross includes the fee; only (1 - fee) of it enters the reserves.
    """
    q = np.asarray(q, dtype=float)
    if np.any(q >= x):
        raise ValueError("cannot buy more X than the pool holds")
    gamma = 1.0 - fee
    k = x * y
    new_x = x - q
    new_y = k / new_x
    y_paid = (new_y - y) / gamma
    return new_x, new_y, y_paid, y_paid * fee


def sell_x(x, y, q, fee):
    """Trader sells q units of X to the pool and receives Y.

    Returns (new_x, new_y, y_received, fee_in_x).
    """
    q = np.asarray(q, dtype=float)
    gamma = 1.0 - fee
    k = x * y
    new_x = x + gamma * q
    new_y = k / new_x
    return new_x, new_y, y - new_y, q * fee


def arbitrage(x, y, p, fee):
    """Optimal one-shot arbitrage against an external reference price p.

    fee may be a scalar or an array with one fee per path.
    With fee f (gamma = 1 - f) a trade is only profitable when the pool price
    P lies outside the no-arbitrage band [gamma * p, p / gamma]. The optimal
    arbitrageur trades exactly until the pool price reaches the band's edge:

        P < gamma * p  -> buy X until  P' = gamma * p
        P > p / gamma  -> sell X until P' = p / gamma

    Since k is constant, reserves at price P' are x' = sqrt(k/P'), y' = sqrt(k P').

    Returns a dict of numpy arrays:
        x, y            new reserves
        fee_x, fee_y    fees paid to LPs (in X and in Y)
        arb_profit      arbitrageur profit valued at the reference price p
                        (net of fees)
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float) * np.ones_like(x)
    fee = np.asarray(fee, dtype=float) * np.ones_like(x)   # scalar or per-path
    gamma = 1.0 - fee
    k = x * y
    P = y / x

    new_x, new_y = x.copy(), y.copy()
    fee_x = np.zeros_like(x)
    fee_y = np.zeros_like(x)
    profit = np.zeros_like(x)

    # Pool too cheap: arbitrageur buys X from the pool and sells it at p.
    cheap = P < gamma * p
    if np.any(cheap):
        g = gamma[cheap]
        target = g * p[cheap]
        nx = np.sqrt(k[cheap] / target)
        ny = np.sqrt(k[cheap] * target)
        y_paid = (ny - y[cheap]) / g
        x_got = x[cheap] - nx
        new_x[cheap], new_y[cheap] = nx, ny
        fee_y[cheap] = y_paid * fee[cheap]
        profit[cheap] = x_got * p[cheap] - y_paid

    # Pool too expensive: arbitrageur buys X at p and sells it to the pool.
    rich = P > p / gamma
    if np.any(rich):
        g = gamma[rich]
        target = p[rich] / g
        nx = np.sqrt(k[rich] / target)
        ny = np.sqrt(k[rich] * target)
        x_in = (nx - x[rich]) / g
        y_got = y[rich] - ny
        new_x[rich], new_y[rich] = nx, ny
        fee_x[rich] = x_in * fee[rich]
        profit[rich] = y_got - x_in * p[rich]

    return {"x": new_x, "y": new_y, "fee_x": fee_x, "fee_y": fee_y,
            "arb_profit": profit}


def execution_cost_bps(x, y, q, side, fee, p):
    """All-in cost of a market order of size q (units of X), in basis points
    relative to the reference price p. Includes fee and price impact.

    side = +1 for buying X, -1 for selling X.
    """
    if side > 0:
        _, _, paid, _ = buy_x(x, y, q, fee)
        avg = paid / q
        return (avg / p - 1.0) * 1e4
    _, _, got, _ = sell_x(x, y, q, fee)
    avg = got / q
    return (1.0 - avg / p) * 1e4


def impermanent_loss(r):
    """Closed-form impermanent loss of a constant-product LP position (no fees)
    after the price moves by a factor r = p_T / p_0, relative to holding:

        IL(r) = 2 sqrt(r) / (1 + r) - 1   (always <= 0, zero only at r = 1)
    """
    r = np.asarray(r, dtype=float)
    return 2.0 * np.sqrt(r) / (1.0 + r) - 1.0
