"""Reference ("true" / centralised-exchange) price process."""
from __future__ import annotations

import numpy as np

MINUTES_PER_YEAR = 365 * 24 * 60


def gbm_paths(p0: float, sigma: float, n_steps: int, n_paths: int,
              dt_years: float = 1.0 / MINUTES_PER_YEAR, mu: float = 0.0,
              seed: int | None = 0) -> np.ndarray:
    """Geometric Brownian motion paths, shape (n_steps + 1, n_paths).

    sigma is annualised volatility; dt_years the step length in years
    (default: one minute). mu = 0 gives a driftless price on average up to the
    usual -sigma^2/2 log correction, so results are not driven by trend.
    """
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n_steps, n_paths))
    log_inc = (mu - 0.5 * sigma**2) * dt_years + sigma * np.sqrt(dt_years) * z
    log_p = np.vstack([np.zeros((1, n_paths)), np.cumsum(log_inc, axis=0)])
    return p0 * np.exp(log_p)
