# Interview guide: understand this project well enough to defend it

Work through this guide before putting the project on your resume. An
interviewer will pick one line from your CV and keep asking "why?" until you
either explain it or get stuck.

## Part 1: the story in 60 seconds (memorise this)

> "Decentralised exchanges like Uniswap don't use an order book. They use a pool
> of two tokens that prices trades with a formula, x times y equals k. The people
> who deposit tokens into the pool earn trading fees, but they also lose money,
> because arbitrageurs trade against the pool whenever its price is stale.
>
> I built a Monte Carlo simulator to measure that trade-off. First I validated it
> against two known closed-form results: impermanent loss, and the σ²/8 formula
> for loss-versus-rebalancing. Then I used it to find the fee that maximises LP
> returns. The optimal fee rises with volatility, from about 20 bps at 20% vol to
> 30–50 bps at 80% vol. At very high volatility no fee makes LPs whole. The
> reason is a trade-off: a higher fee taxes the arbitrageurs, but it also pushes
> ordinary traders to the centralised order book. I also modelled sandwich
> attacks and showed how slippage tolerance determines what a trader loses."

## Part 2: glossary

| Term | Plain English |
|---|---|
| **AMM** (automated market maker) | A smart contract holding two tokens that quotes prices from a formula instead of from people's orders. |
| **Liquidity provider (LP)** | Someone who deposits both tokens into the pool and earns the trading fees. |
| **Constant product, x·y = k** | After every trade the product of the two balances stays the same. Buying X makes X scarcer in the pool, so its price `y/x` rises. |
| **Limit order book (LOB)** | What stock exchanges and Binance use: a list of buy and sell orders at different prices. |
| **Spread** | The gap between the best buy and best sell price. The half-spread is the gap from the mid-price to either side. |
| **Basis point (bp)** | 0.01%. So 30 bps = 0.30%. |
| **Arbitrage** | Buying where something is cheap and selling where it's expensive, at the same time. |
| **Impermanent loss** | How much worse an LP does than someone who simply held the two tokens. "Impermanent" because it disappears if the price returns to where it started. |
| **LVR** (loss-versus-rebalancing) | A stricter benchmark. It compares the LP with someone who makes the *same* trades but at the fair price. The gap is pure value leaked to arbitrageurs. |
| **GBM** (geometric Brownian motion) | The standard random-walk model for prices: returns are normal, prices stay positive. It's also what Black–Scholes assumes. |
| **Monte Carlo** | Simulate many random futures and average them. |
| **Volatility (σ)** | Annualised standard deviation of returns. Here 80% means a typical yearly move of ±80%. Crypto is this volatile; stocks are usually 15–30%. |
| **Sandwich attack** | A bot sees your pending trade, buys just before you and sells just after, profiting from the price move you cause. |
| **Slippage tolerance** | The worst price you'll accept, e.g. "fail the trade if the price is more than 1% worse than quoted." |
| **Common random numbers** | Giving every fee level the *same* random price paths, so differences between them aren't luck. |

## Part 3: how the code works (read it in this order)

1. **`src/ammsim/amm.py`.** Start with `buy_x` and `sell_x`, which are only a few
   lines of algebra. Then read `arbitrage`. The key idea is that the arbitrageur
   pushes the pool price to the edge of the band `[γp, p/γ]`, and because `xy = k`,
   the reserves at that price have a formula. Check you can derive
   `x' = √(k/P')` yourself: from `x'y' = k` and `y'/x' = P'`, so `x'² = k/P'`.
2. **`src/ammsim/prices.py`.** One function. Make sure you can explain the
   `−σ²/2` term: it keeps the *average* price flat.
3. **`src/ammsim/simulate.py`.** This is the loop. Each minute:
   1. Price moves.
   2. The benchmark portfolio is updated.
   3. The arbitrageur trades.
   4. Maybe a noise trader arrives and picks a venue.

   The "columns" trick runs every path and every fee level at once in NumPy.
4. **`src/ammsim/orderbook.py`** and **`src/ammsim/sandwich.py`**.
5. **`tests/test_ammsim.py`.** Each test is a fact you should be able to state,
   for example "an arbitrageur never loses money" or "a round trip always costs
   money."
6. **`experiments/run_all.py`.** This turns simulations into figures.

**Exercises.** Do at least three before an interview:

1. Change `switch_cost_mean_bps` from 25 to 10 and to 50 in `simulate.py`, then
   rerun `experiments/run_all.py`. How does the optimal fee move, and why?
2. Set `route=False`, so every noise trader uses the AMM. What happens to the
   optimal fee, and why does it go up?
3. Double the pool size (`x0 = 2000`). Does LVR as a *percentage* change? (It
   shouldn't. Explain why.)
4. Add a 2 bp "gas cost" that the arbitrageur pays per trade, so she only trades
   if her profit exceeds it. What happens to LVR?

## Part 4: questions you will probably get

**Q: Why does LVR scale with σ² and not σ?**
Arbitrage losses come from the *curvature* of the pool's value function. The pool
is effectively short volatility, much like an option seller. Itô's lemma says
curvature times variance gives the drift loss, and variance is σ².

**Q: How did you know your simulator was right?**
I tested it against two closed-form results before trusting it on anything new.
Impermanent loss matched to about 10⁻¹² and LVR to within about 1%. There are
also unit tests, for example that arbitrage profit is maximised exactly at my
closed-form trade size.

**Q: Why does the optimal fee rise with volatility?**
Arbitrage losses grow with σ², but noise-trader fee income barely depends on
volatility. When volatility is high, taxing the arbitrageurs matters more than
keeping the noise traders, so the fee should go up.

**Q: Why is the simulated LVR slightly below σ²/8 at high volatility?**
Arbitrage happens once a minute rather than continuously. Between blocks some
price moves reverse before anyone trades on them, which reduces losses a little.

**Q: What is the weakest assumption?**
The noise traders' switching cost. I assumed an exponential distribution with
mean 25 bps, and the optimal fee depends on it. Next I would calibrate it from
real data on how volume splits between Uniswap and Binance. Also constant
volatility: real crypto has jumps, which would increase LVR.

**Q: Isn't impermanent loss a bad measure?**
It ignores the *path*. A pool that ends at the starting price shows zero
impermanent loss, yet it may have leaked a lot to arbitrageurs along the way.
LVR captures that, which is why I used it.

**Q: Why use common random numbers?**
To compare fees fairly. With independent draws, a difference between 30 and
50 bps could be luck. With the same paths, the difference comes only from the fee.

**Q: How would a CEX market maker think about this differently?**
A market maker on an order book can *update quotes* when news arrives. The AMM
can't, so it is picked off. That is the economic core of LVR. Proposed fixes
include dynamic fees, auctions for the right to arbitrage, and oracle-based pricing.

**Q: How do you stop sandwich attacks?**
- Traders: set tight slippage tolerances, or use private transaction relays so
  bots can't see the order.
- Protocol design: batch auctions, as in CoW Swap, which execute all orders at
  one price.

**Q: Walk me through the round-trip test. Why must it lose money?**
Buying raises the price, and selling then lowers it. The trader buys high and
sells low along the curve, and pays the fee twice.

## Part 5: resume bullets (numbers from `results/summary.json`)

Use one or two of these, not all:

- Built a vectorised Monte Carlo simulator of Uniswap-style AMMs in Python
  (NumPy), validated against closed-form impermanent-loss and
  loss-versus-rebalancing (σ²/8) results to within 1%.
- Showed that the LP-optimal pool fee rises with volatility (about 20 → 30–50 bps
  as vol goes from 20% to 80%) by modelling noise traders choosing between the
  AMM and a centralised order book.
- Quantified sandwich-attack losses: at 1% slippage tolerance, a $20k trade loses
  about 101 bps to a front-runner extracting about 71 bps.

**For consulting interviews**, lead with the business question: "What fee should a
DeFi exchange charge?" Answer it ("it depends on volatility, and here is the
trade-off") before mentioning any code.

**For quant interviews**, lead with validation: "Before using the simulator I
checked it against two analytical results." Quant interviewers care about that
more than anything else.
