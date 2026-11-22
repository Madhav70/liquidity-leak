"""Reproduce every figure and number in the README.

    python experiments/run_all.py            # full run (~2 minutes)
    python experiments/run_all.py --quick    # fewer paths, for a smoke test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.pyplot as plt  # noqa: E402

from ammsim import amm  # noqa: E402
from ammsim.orderbook import OrderBook  # noqa: E402
from ammsim.plotting import SERIES, TEXT_2, label_end, style, subtitle  # noqa: E402
from ammsim.sandwich import sandwich_curve  # noqa: E402
from ammsim.simulate import PoolConfig, annualised_pct, run  # noqa: E402

FIG = ROOT / "figures"
RES = ROOT / "results"
EXT = "svg"   # vector figures: sharp at any zoom, small, render natively on GitHub


def exp_impermanent_loss(n_paths):
    """Fig 1: simulated LP-vs-HODL with no fees matches the closed form."""
    cfg = PoolConfig(sigma=0.8, trade_prob=0.0, days=90, n_paths=n_paths, seed=11)
    r = run(cfg, 0.0)
    sim_il = (r["pool_T"][0] / r["hodl_T"][0] - 1.0) * 100
    ratio = r["price_ratio"]
    theory = amm.impermanent_loss(ratio) * 100
    max_abs_err = float(np.max(np.abs(sim_il - theory)))

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    grid = np.linspace(0.18, 2.6, 300)
    ax.plot(grid, amm.impermanent_loss(grid) * 100, color=SERIES[0],
            label="Closed form  2√r/(1+r) − 1")
    ax.scatter(ratio, sim_il, s=22, color=SERIES[1], edgecolor="white",
               linewidth=0.8, zorder=3, label="Simulated pools (one per path)")
    ax.set_xlabel("Price ratio r = final price / initial price")
    ax.set_ylabel("LP value vs. just holding (%)")
    ax.set_title("Impermanent loss: simulation matches theory", pad=22)
    subtitle(ax, f"{n_paths} paths, 90 days, 80% vol, no fees · max gap {max_abs_err:.1e} pp")
    ax.legend(loc="lower center")
    fig.savefig(FIG / f"fig1_impermanent_loss.{EXT}")
    plt.close(fig)
    return {"max_abs_error_pp": max_abs_err}


def exp_lvr(n_paths):
    """Fig 2: loss-versus-rebalancing equals sigma^2 / 8 per year."""
    sigmas = np.array([0.2, 0.4, 0.6, 0.8, 1.0, 1.2])
    sim, se = [], []
    for s in sigmas:
        r = run(PoolConfig(sigma=s, trade_prob=0.0, n_paths=n_paths), 0.0)
        a = annualised_pct(-r["lp_excess"][0], r["v0"], r["years"])
        sim.append(a.mean())
        se.append(a.std(ddof=1) / np.sqrt(len(a)))
    sim, se = np.array(sim), np.array(se)
    theory = sigmas**2 / 8 * 100

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    g = np.linspace(0.15, 1.25, 200)
    ax.plot(g * 100, g**2 / 8 * 100, color=SERIES[0], label="Theory  σ²/8")
    ax.errorbar(sigmas * 100, sim, yerr=1.96 * se, fmt="o", color=SERIES[1],
                markeredgecolor="white", capsize=3, zorder=3,
                label="Simulation (95% CI)")
    ax.set_xlabel("Annualised volatility of X (%)")
    ax.set_ylabel("Loss to arbitrageurs (% of pool / year)")
    ax.set_title("Arbitrage losses grow with the square of volatility", pad=22)
    subtitle(ax, "Zero-fee pool, arbitraged every minute, vs. a fairly-priced rebalancing portfolio")
    ax.legend(loc="upper left")
    fig.savefig(FIG / f"fig2_lvr_vs_volatility.{EXT}")
    plt.close(fig)
    return {"sigma": sigmas.tolist(), "theory_pct": theory.round(3).tolist(),
            "sim_pct": sim.round(3).tolist(), "sim_se": se.round(4).tolist()}


def exp_fee_grid(n_paths):
    """Fig 3: LP excess return vs fee, for four volatility regimes."""
    fees_bps = np.array([1, 5, 10, 20, 30, 50, 75, 100])
    sigmas = [0.2, 0.5, 0.8, 1.2]
    out = {"fees_bps": fees_bps.tolist(), "rows": []}
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for i, s in enumerate(sigmas):
        r = run(PoolConfig(sigma=s, n_paths=n_paths), fees_bps / 1e4)
        ex = annualised_pct(r["lp_excess"], r["v0"], r["years"])
        mean = ex.mean(1)
        se = ex.std(1, ddof=1) / np.sqrt(ex.shape[1])
        share = r["noise_volume_amm"].sum(1) / r["noise_volume_all"].sum(1)
        best = int(np.argmax(mean))
        out["rows"].append({
            "sigma": s, "lp_excess_pct": mean.round(3).tolist(),
            "se": se.round(3).tolist(), "best_fee_bps": int(fees_bps[best]),
            "best_excess_pct": round(float(mean[best]), 3),
            "amm_share_of_noise_volume": share.round(3).tolist(),
            "noise_fee_pct": annualised_pct(r["fee_noise"], r["v0"], r["years"]).mean(1).round(3).tolist(),
            "arb_fee_pct": annualised_pct(r["fee_arb"], r["v0"], r["years"]).mean(1).round(3).tolist(),
        })
        ax.plot(fees_bps, mean, color=SERIES[i], marker="o",
                markeredgecolor="white", label=f"{int(s*100)}% vol")
        ax.scatter([fees_bps[best]], [mean[best]], s=90, facecolor="none",
                   edgecolor=SERIES[i], linewidth=1.6, zorder=4)
    ax.axhline(0, color=TEXT_2, linewidth=1)
    ax.set_xscale("log")
    ax.set_xticks(fees_bps)
    ax.set_xticklabels([str(f) for f in fees_bps])
    ax.set_xlabel("Pool fee (basis points, log scale)")
    ax.set_ylabel("LP return vs. rebalancing (% / year)")
    ax.set_title("The LP-optimal fee rises with volatility", pad=22)
    subtitle(ax, "Circles mark the best fee in each regime · noise traders route to the cheaper venue")
    ax.legend(loc="lower right", ncol=2)
    ax.set_xlim(0.8, 130)
    fig.savefig(FIG / f"fig3_optimal_fee.{EXT}")
    plt.close(fig)
    return out


def exp_execution_cost():
    """Fig 4: all-in execution cost of a market order, AMM vs order book."""
    p, x = 2000.0, 1000.0
    y = x * p
    book = OrderBook()
    sizes = np.geomspace(0.1, 100, 60)
    amm_cost = np.array([amm.execution_cost_bps(x, y, q, +1, 0.003, p) for q in sizes])
    lob_cost = book.cost_bps_closed_form(sizes)
    cross = sizes[np.argmax(amm_cost < lob_cost)] if np.any(amm_cost < lob_cost) else None

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(sizes, amm_cost, color=SERIES[0], label="AMM (30 bp fee, \\$4M pool)")
    ax.plot(sizes, lob_cost, color=SERIES[1], label="Order book (5 bp half-spread)")
    label_end(ax, sizes[-1], amm_cost[-1], "AMM")
    label_end(ax, sizes[-1], lob_cost[-1], "Order book")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Order size (units of X, log scale)")
    ax.set_ylabel("All-in cost (bps of fair price, log scale)")
    ax.set_title("A $4M AMM pool charges far more for size than a deep order book".replace("$", r"\$"), pad=22)
    subtitle(ax, "Cost of buying X = fee + spread + price impact · this gap is why most flow routes to the book")
    ax.legend(loc="upper left")
    ax.set_xlim(0.1, 220)
    fig.savefig(FIG / f"fig4_execution_cost.{EXT}")
    plt.close(fig)
    pick = lambda q: float(np.interp(np.log(q), np.log(sizes), amm_cost))  # noqa: E731
    pickb = lambda q: float(book.cost_bps_closed_form(np.array([q]))[0])  # noqa: E731
    return {"amm_bps": {q: round(pick(q), 2) for q in (1, 10, 50)},
            "book_bps": {q: round(pickb(q), 2) for q in (1, 10, 50)},
            "amm_cheaper_from_size": None if cross is None else round(float(cross), 2)}


def exp_sandwich():
    """Fig 5: a looser slippage tolerance invites a bigger sandwich attack."""
    p, x = 2000.0, 1000.0
    y = x * p
    q = 10.0                      # victim buys 10 X (~$20k)
    taus = np.linspace(0.0, 0.03, 61)
    c = sandwich_curve(x, y, q, taus, 0.003)
    notional = q * p

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(taus * 100, c["victim_extra_cost"] / notional * 1e4, color=SERIES[0],
            label="Victim's extra cost")
    ax.plot(taus * 100, c["attacker_profit"] / notional * 1e4, color=SERIES[1],
            label="Attacker's profit")
    label_end(ax, taus[-1] * 100, c["victim_extra_cost"][-1] / notional * 1e4, "Victim loses")
    label_end(ax, taus[-1] * 100, c["attacker_profit"][-1] / notional * 1e4, "Attacker gains")
    ax.set_xlabel("Victim's slippage tolerance (%)")
    ax.set_ylabel("bps of the victim's trade")
    ax.set_title("Sandwich attacks: slippage tolerance is an invitation", pad=22)
    subtitle(ax, r"\$20k buy in a \$4M pool with a 30 bp fee · gap between lines = fees paid to LPs")
    ax.legend(loc="upper left")
    ax.set_xlim(0, 3.6)
    fig.savefig(FIG / f"fig5_sandwich.{EXT}")
    plt.close(fig)
    i1 = int(np.argmin(np.abs(taus - 0.01)))
    first = taus[np.argmax(c["attacker_profit"] > 0)]
    return {"tau_1pct_victim_extra_bps": round(float(c["victim_extra_cost"][i1] / notional * 1e4), 2),
            "tau_1pct_attacker_profit_bps": round(float(c["attacker_profit"][i1] / notional * 1e4), 2),
            "min_tolerance_for_profitable_attack_pct": round(float(first * 100), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    n = 40 if args.quick else 200
    FIG.mkdir(exist_ok=True)
    RES.mkdir(exist_ok=True)
    style()
    summary = {
        "impermanent_loss": exp_impermanent_loss(n),
        "lvr": exp_lvr(n),
        "fee_grid": exp_fee_grid(n),
        "execution_cost": exp_execution_cost(),
        "sandwich": exp_sandwich(),
        "n_paths": n,
    }
    (RES / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
