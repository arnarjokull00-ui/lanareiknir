import numpy as np
import pytest

from lanareiknir.engine import (
    annuity_payment, breakeven_inflation, compare, match_payment, simulate_loan,
)

P, RR, NR, Y = 43_000_000, 0.04, 0.09, 30


def test_annuity_closed_form():
    # 10m @ 6%/12 for 120 months — standard closed-form check
    assert annuity_payment(10_000_000, 0.06 / 12, 120) == pytest.approx(111_020, rel=1e-3)


def test_zero_inflation_equivalence():
    """With 0% inflation, an indexed loan at rate r == non-indexed at rate r."""
    a = simulate_loan(P, 0.05, Y, indexed=True, inflation=0.0)
    b = simulate_loan(P, 0.05, Y, indexed=False, inflation=0.0)
    assert a.total_paid_nominal == pytest.approx(b.total_paid_nominal, rel=1e-9)
    assert a.months_to_payoff == b.months_to_payoff == 360


def test_equal_principal_declines_and_sums():
    r = simulate_loan(P, 0.05, Y, indexed=False, payment_type="equal_principal")
    pays = r.schedule.payment_nominal.values
    assert np.all(np.diff(pays) < 0)                       # declining payments
    # principal installments must sum to the principal
    interest = r.schedule.balance_nominal.shift(1).fillna(P).values * 0.05 / 12
    assert (pays - interest).sum() == pytest.approx(P, rel=1e-6)


def test_overpayment_shortens_term():
    base = simulate_loan(P, RR, Y, indexed=True, inflation=0.05)
    first = base.schedule.payment_nominal.iloc[0]
    over = simulate_loan(P, RR, Y, indexed=True, inflation=0.05,
                         target_total_payment=float(first) * 1.5)
    assert over.months_to_payoff < base.months_to_payoff
    assert over.total_paid_real < base.total_paid_real


def test_fisher_breakeven_region():
    """Breakeven should sit near the rate gap (9% − 4% = 5 pts), slightly above."""
    be = breakeven_inflation(P, RR, NR, Y, strategy="fixed")
    assert 0.045 < be < 0.06


def test_match_payment_solver():
    m = match_payment(P, RR, NR, Y, annual_inflation=0.05, horizon_months=120)
    assert m["extra_per_month"] > 0
    # verify: simulate at the solved payment, real balance ≈ target at horizon
    r = simulate_loan(P, RR, Y, indexed=True, inflation=0.05,
                      target_total_payment=float(m["total_payment_to_match"]))
    got = float(r.schedule.balance_real.iloc[m["horizon_months"]])
    assert got == pytest.approx(m["target_real_balance"], rel=0.01)


def test_compare_orders_sensibly_low_inflation():
    s = compare(P, RR, NR, Y, Y, annual_inflation=0.025)
    assert (s.loc["verðtryggt + fixed óvt payment"].total_real
            < s.loc["óverðtryggt"].total_real)             # strategy wins at CB target


def test_recalc_mode():
    """Monthly recalculation (bank default) absorbs overpayments: the loan
    runs full term and costs MORE than under a held schedule."""
    non = simulate_loan(P, NR, Y, indexed=False, inflation=0.052)
    pay0 = float(non.schedule.payment_nominal.iloc[0])
    rc = simulate_loan(P, RR, Y, indexed=True, inflation=0.052,
                       recalc_schedule=True, target_total_payment=pay0)
    fs = simulate_loan(P, RR, Y, indexed=True, inflation=0.052,
                       target_total_payment=pay0)
    assert rc.months_to_payoff == Y * 12          # stretched back to full term
    assert fs.months_to_payoff < rc.months_to_payoff
    assert rc.total_paid_real > fs.total_paid_real  # recalc mode costs more
    # required payment still overtakes the fixed commitment eventually
    assert rc.schedule.payment_nominal.max() > pay0 * 1.1
