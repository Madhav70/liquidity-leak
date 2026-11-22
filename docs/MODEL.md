# The model

## 1. The constant-product pool

Reserves `x` (risky token X) and `y` (numeraire Y). Every trade keeps `k = x·y`
fixed, net of fees. The pool's marginal price is `P = y/x`.

A fee `f` is charged on the input of each trade; write `γ = 1 − f`.

**Buying q units of X.** New reserves are `x' = x − q` and `y' = k/x'`. The trader
pays `(y' − y)/γ` in Y, of which a fraction `f` is the fee.

**Selling q units of X.** Only `γq` enters the pool: `x' = x + γq` and `y' = k/x'`.
The trader receives `y − y'`.

## 2. Optimal arbitrage

Let `p` be the true price. Buying a tiny amount of X from the pool costs `P/γ`,
and selling a tiny amount earns `γP`. So no trade is profitable while

        γ p ≤ P ≤ p / γ          (the no-arbitrage band)

If `P < γp`, the pool is too cheap. The arbitrageur buys X until the marginal
cost `P'/γ` equals `p`, i.e. `P' = γp`. If `P > p/γ`, she sells X until `P' = p/γ`.
Because `k` is fixed, reserves at any price `P'` are

        x' = √(k / P'),   y' = √(k · P').

So the optimal trade has a closed form and needs no numerical search
(`amm.arbitrage`). The unit tests confirm that trading 5% more or 5% less earns
strictly less.

## 3. Impermanent loss

With no fees and continuous arbitrage, the pool's value at price `p` is
`V(p) = 2√(k p)`. Holding the initial tokens instead is worth `x₀ p + y₀`.
With `r = p_T / p₀`:

        V_T / HODL_T − 1 = 2√r / (1 + r) − 1   ≤ 0.

By the AM-GM inequality, this is zero only at `r = 1`. It depends only on the
final price, not the path, which is why simulation and formula agree to about
10⁻¹² (Fig. 1).

## 4. Loss-versus-rebalancing (LVR)

Impermanent loss compares the LP with someone who never trades. A sharper
benchmark is someone who holds **the same amount of X as the pool at every
moment** but trades at the fair price `p`:

        R_T = V_0 + Σ_t x_t (p_{t+1} − p_t).

The pool makes the same trades, but at worse prices, because it trades with
arbitrageurs who already know `p`. Milionis et al. (2022) show that for a
constant-product pool with no fees,

        E[ R_T − V_T ] ≈ (σ² / 8) · V · T,

so the loss grows with the **square** of volatility. Applying Itô's lemma to
`V(p) = 2√(kp)` gives the second derivative `V'' = −½√k p^{−3/2}`, and the loss
rate is `−½ V'' σ² p² = σ² V / 8`.

In the simulation (Fig. 2), the zero-fee pool with minute-by-minute arbitrage
comes within about 1% of this. The small shortfall at high volatility is a
discreteness effect: arbitrage happens once a minute, not continuously.

The LP's performance is then

        LP excess = (V_T + fee income) − R_T,

that is, fees earned minus value lost to informed flow, plus whatever noise
traders pay in price impact.

## 5. Noise traders and venue choice

Each minute, with probability 0.10, a noise trader arrives:

- **Order size:** lognormal with median 2 X (about $4k) and log-s.d. 1.
- **Direction:** buy or sell with probability ½ each.
- **Personal cost `c` of using the centralised exchange:** exponential with mean
  25 bps. This stands in for KYC, withdrawals, bridging and custody.

She trades on the AMM if

        AMM all-in cost  ≤  order-book cost + c.

This makes AMM demand **elastic in the fee**, which creates the trade-off behind
Fig. 3:

- A low fee wins volume but leaks value to arbitrageurs.
- A high fee taxes arbitrageurs but loses ordinary traders.

## 6. The order book

Level `j = 0, 1, 2, …` sits at relative distance `h + j·τ` from the true price.
Here `h` is the half-spread (5 bps), `τ` the tick (1 bp), and each level holds
`d = 5` units of X.

For an order of `q` units, let `n = ⌊q/d⌋` be the number of levels it consumes
completely. Its average cost in price units is

        [ d (n h + τ n(n−1)/2) + (q − n d)(h + n τ) ] / q.

The unit tests check this closed form against an explicit walk through the book.

## 7. Sandwich attacks

A victim buys `q` X with slippage tolerance `τ`. The attacker:

1. Buys `a` X first, pushing the price up.
2. Lets the victim trade at the worse price.
3. Sells `a` back.

The victim's price is increasing in `a`, so the attacker picks the largest `a`
that keeps the victim within tolerance; this is found by bisection. If round-trip
fees exceed the gain, the attacker does not attack.

The victim's loss exceeds the attacker's gain. The difference is extra fee income
for LPs, from both legs of the attack and from the victim's larger payment.
