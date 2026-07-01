"""
lanareiknir.engine — verðtryggt vs óverðtryggt loan simulation
===============================================================

Mechanics
---------
Indexed (verðtryggt) loans are accounted for internally in REAL (base-index)
krónur: the schedule (annuity or equal-principal) is computed at the real rate,
and every real amount is converted to nominal by the cumulative CPI factor f_t.
A nominal overpayment X in month t therefore reduces the real balance by
X / f_t — krónur paid early buy down the most real principal, which is the
entire source of the fixed-payment strategy's edge.

Non-indexed (óverðtryggt) loans run in nominal krónur at the nominal rate.

Payment structures
------------------
* 'annuity'          — jafnar greiðslur: constant payment (real-constant for
                       indexed loans, so nominal payment grows with the index).
* 'equal_principal'  — jafnar afborganir: constant principal installment
                       (real-constant for indexed), payment = installment +
                       interest, so payments decline over time.

Overpayments follow the *stytta lánstíma* convention: the scheduled payment is
unchanged and the loan simply terminates earlier. (Choosing *lækka
greiðslubyrði* at the bank and then paying only the new minimum would slow
amortisation relative to this model — see README.)

All summary costs are reported both nominal and REAL (deflated by the CPI
factor), because nominal totals are meaningless across inflation scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Union

import numpy as np
import pandas as pd

MONTHS = 12


# ----------------------------------------------------------------------------
# paths
# ----------------------------------------------------------------------------

def constant_monthly_path(annual: float, n_months: int) -> np.ndarray:
    """Monthly growth factors for a constant annual rate (geometric)."""
    return np.full(n_months, (1.0 + annual) ** (1.0 / MONTHS))


def annual_to_monthly_path(annual_by_year: Sequence[float], n_months: int) -> np.ndarray:
    """Expand a per-year annual-rate sequence into monthly factors.

    The last value is held flat if the loan outlives the series.
    """
    out = np.empty(n_months)
    for t in range(n_months):
        y = min(t // MONTHS, len(annual_by_year) - 1)
        out[t] = (1.0 + annual_by_year[y]) ** (1.0 / MONTHS)
    return out


def _as_path(x: Union[float, Sequence[float], np.ndarray], n: int) -> np.ndarray:
    """Accept a scalar annual rate or a pre-built monthly-factor path."""
    if np.isscalar(x):
        return constant_monthly_path(float(x), n)
    arr = np.asarray(x, dtype=float)
    if len(arr) < n:
        arr = np.concatenate([arr, np.full(n - len(arr), arr[-1])])
    return arr[:n]


def annuity_payment(principal: float, monthly_rate: float, n_months: int) -> float:
    if monthly_rate == 0:
        return principal / n_months
    a = (1 + monthly_rate) ** n_months
    return principal * monthly_rate * a / (a - 1)


# ----------------------------------------------------------------------------
# simulation
# ----------------------------------------------------------------------------

@dataclass
class LoanResult:
    schedule: pd.DataFrame        # per-month detail
    months_to_payoff: int
    total_paid_nominal: float
    total_paid_real: float        # deflated to base-index krónur

    def summary(self) -> dict:
        return {
            "months": self.months_to_payoff,
            "years": round(self.months_to_payoff / 12, 1),
            "total_nominal": round(self.total_paid_nominal),
            "total_real": round(self.total_paid_real),
        }


def simulate_loan(
    principal: float,
    annual_rate: float,
    years: int,
    *,
    indexed: bool,
    payment_type: str = "annuity",             # 'annuity' | 'equal_principal'
    inflation: Union[float, Sequence[float]] = 0.0,
    rate_path: Optional[Sequence[float]] = None,   # monthly annual-rate values (variable óverðtryggt)
    target_total_payment: Optional[Union[float, Callable[[int], float]]] = None,
    index_lag_months: int = 0,
    max_months: Optional[int] = None,
) -> LoanResult:
    """Simulate one loan month by month.

    target_total_payment — a fixed nominal amount (or fn of month t) the
    borrower commits to paying in total each month. Anything above the
    scheduled payment is applied to principal (aukaafborgun). If it is below
    the scheduled payment, the scheduled payment is paid (no underpaying).

    index_lag_months — verðbætur lag: the CPI factor applied in month t is the
    factor from month t - lag (Icelandic practice ≈ 2 months).

    rate_path — for variable-rate non-indexed loans: annual rate per month.
    The annuity payment is re-derived at each rate change over the remaining
    term (vaxtaendurskoðun payment reset). Ignored for indexed loans.
    """
    n = years * MONTHS
    horizon = max_months or n * 3
    infl_factors = _as_path(inflation, horizon)
    cum_index = np.concatenate([[1.0], np.cumprod(infl_factors)])   # f_0 = 1

    def index_at(t: int) -> float:
        return cum_index[max(0, t - index_lag_months)]

    monthly_rate = annual_rate / MONTHS
    rows = []

    if indexed:
        # real-krónur accounting
        bal = principal                     # real balance
        sched_annuity = annuity_payment(principal, monthly_rate, n)
        installment = principal / n
        t = 0
        while bal > 1e-6 and t < horizon:
            f = index_at(t)
            interest = bal * monthly_rate                       # real
            if payment_type == "annuity":
                sched_real = min(sched_annuity, bal + interest)
            else:
                sched_real = min(installment + interest, bal + interest)
            sched_nom = sched_real * f
            total_nom = sched_nom
            if target_total_payment is not None:
                tgt = target_total_payment(t) if callable(target_total_payment) else target_total_payment
                total_nom = max(sched_nom, tgt)
            total_real = total_nom / f
            # cap at full payoff
            total_real = min(total_real, bal + interest)
            total_nom = total_real * f
            bal = bal + interest - total_real
            rows.append((t, total_nom, total_real, bal * f, bal))
            t += 1
    else:
        bal = principal                     # nominal balance
        rates = (np.asarray(rate_path, dtype=float)[:horizon]
                 if rate_path is not None else None)
        cur_rate = annual_rate
        sched = annuity_payment(principal, cur_rate / MONTHS, n)
        installment = principal / n
        t = 0
        while bal > 1e-6 and t < horizon:
            if rates is not None and t < len(rates) and rates[t] != cur_rate:
                cur_rate = rates[t]                              # payment reset
                sched = annuity_payment(bal, cur_rate / MONTHS, max(n - t, 1))
            mr = cur_rate / MONTHS
            interest = bal * mr
            if payment_type == "annuity":
                sched_nom = min(sched, bal + interest)
            else:
                sched_nom = min(installment + interest, bal + interest)
            total_nom = sched_nom
            if target_total_payment is not None:
                tgt = target_total_payment(t) if callable(target_total_payment) else target_total_payment
                total_nom = max(sched_nom, tgt)
            total_nom = min(total_nom, bal + interest)
            bal = bal + interest - total_nom
            f = index_at(t)
            rows.append((t, total_nom, total_nom / f, bal, bal / f))
            t += 1

    df = pd.DataFrame(rows, columns=["month", "payment_nominal", "payment_real",
                                     "balance_nominal", "balance_real"])
    return LoanResult(
        schedule=df,
        months_to_payoff=len(df),
        total_paid_nominal=float(df.payment_nominal.sum()),
        total_paid_real=float(df.payment_real.sum()),
    )


# ----------------------------------------------------------------------------
# strategies & comparisons
# ----------------------------------------------------------------------------

def compare(
    principal: float,
    real_rate: float,
    nominal_rate: float,
    years_indexed: int,
    years_nonindexed: int,
    *,
    annual_inflation: float,
    payment_type: str = "annuity",
    index_lag_months: int = 0,
) -> pd.DataFrame:
    """The four canonical cases, summarised in real krónur."""
    non = simulate_loan(principal, nominal_rate, years_nonindexed, indexed=False,
                        payment_type=payment_type, inflation=annual_inflation)
    vt_passive = simulate_loan(principal, real_rate, years_indexed, indexed=True,
                               payment_type=payment_type, inflation=annual_inflation,
                               index_lag_months=index_lag_months)
    first_non_payment = float(non.schedule.payment_nominal.iloc[0])
    vt_fixed = simulate_loan(principal, real_rate, years_indexed, indexed=True,
                             payment_type=payment_type, inflation=annual_inflation,
                             target_total_payment=first_non_payment,
                             index_lag_months=index_lag_months)
    g = (1.0 + annual_inflation) ** (1.0 / MONTHS)
    vt_grown = simulate_loan(principal, real_rate, years_indexed, indexed=True,
                             payment_type=payment_type, inflation=annual_inflation,
                             target_total_payment=lambda t: first_non_payment * g ** t,
                             index_lag_months=index_lag_months)
    out = pd.DataFrame(
        [non.summary(), vt_passive.summary(), vt_fixed.summary(), vt_grown.summary()],
        index=["óverðtryggt", "verðtryggt (passive)",
               "verðtryggt + fixed óvt payment", "verðtryggt + óvt payment grown @infl"],
    )
    return out


def match_payment(
    principal: float,
    real_rate: float,
    nominal_rate: float,
    years: int,
    *,
    annual_inflation: float,
    horizon_months: int = 120,
    payment_type: str = "annuity",
) -> dict:
    """Extra monthly payment on the indexed loan needed to match the
    óverðtryggt loan's real equity-building pace at a chosen horizon.

    Solves (bisection) for the constant total nominal payment T such that the
    indexed loan's REAL balance at `horizon_months` equals the non-indexed
    loan's real balance at the same point.
    """
    non = simulate_loan(principal, nominal_rate, years, indexed=False,
                        payment_type=payment_type, inflation=annual_inflation)
    h = min(horizon_months, non.months_to_payoff - 1)
    target_bal = float(non.schedule.balance_real.iloc[h])

    def real_bal_at(total_payment: float) -> float:
        r = simulate_loan(principal, real_rate, years, indexed=True,
                          payment_type=payment_type, inflation=annual_inflation,
                          target_total_payment=total_payment)
        if h >= r.months_to_payoff:
            return 0.0
        return float(r.schedule.balance_real.iloc[h])

    base = simulate_loan(principal, real_rate, years, indexed=True,
                         payment_type=payment_type, inflation=annual_inflation)
    lo = float(base.schedule.payment_nominal.iloc[0])
    hi = lo * 4
    while real_bal_at(hi) > target_bal:
        hi *= 1.5
    for _ in range(60):
        mid = (lo + hi) / 2
        if real_bal_at(mid) > target_bal:
            lo = mid
        else:
            hi = mid
    total = (lo + hi) / 2
    return {
        "required_indexed_payment_m0": round(float(base.schedule.payment_nominal.iloc[0])),
        "total_payment_to_match": round(total),
        "extra_per_month": round(total - float(base.schedule.payment_nominal.iloc[0])),
        "horizon_months": h,
        "target_real_balance": round(target_bal),
    }


def breakeven_inflation(
    principal: float,
    real_rate: float,
    nominal_rate: float,
    years: int,
    *,
    strategy: str = "fixed",           # 'fixed' | 'grown'
    payment_type: str = "annuity",
    lo: float = 0.0,
    hi: float = 0.15,
) -> float:
    """Average annual inflation at which the indexed-loan strategy's real cost
    equals the óverðtryggt loan's real cost. Above it, óverðtryggt wins."""
    def diff(infl: float) -> float:
        s = compare(principal, real_rate, nominal_rate, years, years,
                    annual_inflation=infl, payment_type=payment_type)
        row = ("verðtryggt + fixed óvt payment" if strategy == "fixed"
               else "verðtryggt + óvt payment grown @infl")
        return s.loc[row].total_real - s.loc["óverðtryggt"].total_real
    for _ in range(50):
        mid = (lo + hi) / 2
        if diff(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
