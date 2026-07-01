"""
lanareiknir.backtest — the 2015–2025 historical run
====================================================

Runs the four canonical cases through the actual Icelandic inflation and rate
path, including the 2021→2024 shock: a borrower who signed in early 2015 and
committed to the fixed-payment strategy versus one who took the óverðtryggt
loan with a variable rate that reset upward through 2022–24.

Two-month verðbætur lag applied to the indexed loan, per Icelandic practice.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import annual_inflation_series, variable_rate_series
from .engine import MONTHS, annual_to_monthly_path, simulate_loan


def run_backtest(principal: float = 43_000_000,
                 real_rate: float = 0.04,
                 nominal_spread: float = 0.030,
                 real_floor: float = 0.035,
                 years: int = 30) -> pd.DataFrame:
    """One historical run at a given óverðtryggt spread.

    nominal_spread — margin over the policy rate for the óverðtryggt loan.
    Íslandsbanki's published range is 2.25%–3.35% by LTV (policy + margin);
    3.0% is a mid-LTV midpoint. real_floor — the indexed loan's rate floor
    (Íslandsbanki 3.50%–4.75% by LTV); the real rate is held at max(real_rate,
    real_floor).
    """
    real_rate = max(real_rate, real_floor)
    infl_annual = annual_inflation_series()
    rate_annual = variable_rate_series(spread=nominal_spread)
    n_hist = len(infl_annual) * MONTHS

    infl_path = annual_to_monthly_path(infl_annual, n_hist)
    rate_path = np.repeat(rate_annual, MONTHS)

    non = simulate_loan(principal, rate_annual[0], years, indexed=False,
                        inflation=infl_path, rate_path=rate_path,
                        max_months=n_hist)
    first_pay = float(non.schedule.payment_nominal.iloc[0])

    vt_passive = simulate_loan(principal, real_rate, years, indexed=True,
                               inflation=infl_path, index_lag_months=2,
                               max_months=n_hist)
    vt_fixed = simulate_loan(principal, real_rate, years, indexed=True,
                             inflation=infl_path, index_lag_months=2,
                             target_total_payment=first_pay,
                             max_months=n_hist)

    rows = []
    for name, r in [("óverðtryggt (variable rate)", non),
                    ("verðtryggt (passive)", vt_passive),
                    ("verðtryggt + fixed strategy", vt_fixed)]:
        s = r.schedule
        rows.append({
            "case": name,
            "paid_real_m": round(s.payment_real.sum() / 1e6, 1),
            "end_balance_real_m": round(s.balance_real.iloc[-1] / 1e6, 1),
            "net_position_real_m": round(
                (s.payment_real.sum() + s.balance_real.iloc[-1]) / 1e6, 1),
        })
    return pd.DataFrame(rows).set_index("case")


def sensitivity_band(principal: float = 43_000_000,
                     real_rate: float = 0.04,
                     real_floor: float = 0.035,
                     spreads=(0.0225, 0.030, 0.0335),
                     years: int = 30) -> pd.DataFrame:
    """Backtest net real position across Íslandsbanki's documented óverðtryggt
    spread range (2.25%–3.35% by LTV). Shows how the strategy-vs-óverðtryggt
    verdict depends on the one assumption we can't observe directly.
    """
    rows = []
    for sp in spreads:
        bt = run_backtest(principal, real_rate, nominal_spread=sp,
                          real_floor=real_floor, years=years)
        ovt = bt.loc["óverðtryggt (variable rate)", "net_position_real_m"]
        strat = bt.loc["verðtryggt + fixed strategy", "net_position_real_m"]
        rows.append({
            "spread": f"{sp*100:.2f}%",
            "óvt_net_real_m": ovt,
            "strategy_net_real_m": strat,
            "strategy_edge_m": round(ovt - strat, 1),   # + = strategy cheaper
            "winner": "strategy" if strat < ovt else "óverðtryggt",
        })
    return pd.DataFrame(rows).set_index("spread")


if __name__ == "__main__":
    print("Base run (spread 3.0%, floor 3.50%):\n")
    print(run_backtest().to_string())
    print("\nSensitivity across Íslandsbanki óverðtryggt spread range:\n")
    print(sensitivity_band().to_string())
