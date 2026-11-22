import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ammsim import amm  # noqa: E402
from ammsim.orderbook import OrderBook  # noqa: E402
from ammsim.sandwich import sandwich  # noqa: E402
from ammsim.simulate import PoolConfig, annualised_pct, run  # noqa: E402

X, P = 1000.0, 2000.0
Y = X * P


def test_swaps_preserve_invariant():
    nx, ny, _, _ = amm.buy_x(X, Y, 5.0, 0.003)
    assert nx * ny == pytest.approx(X * Y)
    nx, ny, _, _ = amm.sell_x(X, Y, 5.0, 0.003)
    assert nx * ny == pytest.approx(X * Y)


def test_round_trip_loses_exactly_the_fees_and_impact():
    # buying then selling the same amount can never make money
    nx, ny, paid, _ = amm.buy_x(X, Y, 10.0, 0.003)
    _, _, got, _ = amm.sell_x(nx, ny, 10.0, 0.003)
    assert got < paid


@pytest.mark.parametrize("p", [1500.0, 1990.0, 2000.0, 2010.0, 2600.0])
def test_arbitrage_moves_price_to_band_edge(p):
    fee = 0.003
    g = 1 - fee
    res = amm.arbitrage(np.array([X]), np.array([Y]), p, fee)
    P_new = res["y"][0] / res["x"][0]
    assert g * p - 1e-9 <= P_new <= p / g + 1e-9
    assert res["arb_profit"][0] >= -1e-9          # never a loss for the arb
    if Y / X < g * p:
        assert P_new == pytest.approx(g * p)
    elif Y / X > p / g:
        assert P_new == pytest.approx(p / g)
    else:
        assert res["arb_profit"][0] == 0.0         # inside the band: no trade


def test_arbitrage_profit_is_optimal():
    # trading slightly more or less than the optimum earns less
    fee, p = 0.003, 2100.0
    res = amm.arbitrage(np.array([X]), np.array([Y]), p, fee)
    q_star = X - res["x"][0]

    def profit(q):
        _, _, paid, _ = amm.buy_x(X, Y, q, fee)
        return q * p - paid

    assert profit(q_star) == pytest.approx(res["arb_profit"][0])
    assert profit(q_star * 0.95) < profit(q_star)
    assert profit(q_star * 1.05) < profit(q_star)


def test_impermanent_loss_formula():
    assert amm.impermanent_loss(1.0) == 0.0
    assert amm.impermanent_loss(4.0) == pytest.approx(-0.2)   # 2*2/5 - 1
    assert np.all(amm.impermanent_loss(np.linspace(0.1, 10, 50)) <= 0)


def test_orderbook_walk_matches_closed_form():
    book = OrderBook(half_spread=0.0005, tick=0.0001, depth=5.0)
    for q in [0.5, 5.0, 7.3, 42.0]:
        walk = book.execution_cost_bps(P, q, +1)
        closed = book.cost_bps_closed_form(np.array([q]))[0]
        assert walk == pytest.approx(closed)
        assert book.execution_cost_bps(P, q, -1) == pytest.approx(closed)


def test_sandwich_respects_victim_tolerance():
    q, tau, fee = 10.0, 0.01, 0.003
    _, _, quoted_paid, _ = amm.buy_x(X, Y, q, fee)
    s = sandwich(X, Y, q, tau, fee)
    assert s["victim_paid"] <= quoted_paid * (1 + tau) + 1e-6
    assert s["attacker_profit"] > 0
    assert s["victim_extra_cost"] > s["attacker_profit"]   # LPs keep the fees


def test_no_attack_with_zero_tolerance():
    s = sandwich(X, Y, 10.0, 0.0, 0.003)
    assert s["attacker_profit"] == 0.0


def test_lvr_matches_sigma_squared_over_eight():
    cfg = PoolConfig(sigma=0.6, trade_prob=0.0, days=10, n_paths=100, seed=3)
    r = run(cfg, 0.0)
    lvr = annualised_pct(-r["lp_excess"][0], r["v0"], r["years"]).mean()
    assert lvr == pytest.approx(0.6**2 / 8 * 100, rel=0.03)


def test_common_random_numbers_across_fees():
    cfg = PoolConfig(sigma=0.5, days=1, n_paths=20)
    r = run(cfg, [0.001, 0.003])
    assert np.allclose(r["hodl_T"][0], r["hodl_T"][1])        # same price paths
    assert np.allclose(r["noise_volume_all"][0], r["noise_volume_all"][1])
