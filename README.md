# lánareiknir — verðtryggt vs óverðtryggt mortgage analysis

A Python engine and interactive calculator for comparing Icelandic indexed
(verðtryggt) and non-indexed (óverðtryggt) mortgages, focused on a strategy no
existing Icelandic calculator models: taking the indexed loan but committing to
the non-indexed loan's higher monthly payment, with the surplus applied as an
overpayment (aukaafborgun) directly against the principal.

**Live calculator:** `web/index.html` (static, no dependencies — host anywhere)

## Why this exists

Existing tools (lanareiknivel.is, bank calculators) compare the two loan forms
at their *required* payments, which conflates two different decisions: which
contract to sign, and how much to pay. This tool separates them, and adds two
things the existing tools don't have:

1. **A historical backtest** on real Icelandic CPI and policy-rate paths
   (2015–2025, including the 2021→2024 inflation and rate shock), rather than
   forward-looking assumptions only.
2. **The match-payment number**: the extra monthly payment required on the
   indexed loan to match the non-indexed loan's real equity-building pace at a
   chosen horizon — the price of equal eignamyndun.

## Methodology

- Indexed loans are simulated in **real (base-index) krónur**; nominal amounts
  are derived through the cumulative CPI factor. A nominal overpayment X in
  month t reduces the real balance by X/f_t — early krónur buy down the most
  real principal, which is the entire source of the strategy's edge.
- All comparisons are reported in **real (CPI-deflated) krónur**. Nominal
  totals are meaningless across inflation scenarios: the non-indexed loan
  benefits from inflation eroding its fixed krónur while the indexed loan does
  not, and only real accounting captures that.
- Both **jafnar greiðslur** (annuity) and **jafnar afborganir** (equal
  principal) structures are supported.
- Overpayments follow the *stytta lánstíma* convention (payment unchanged,
  term shortens). If your bank applies *lækka greiðslubyrði* and you then pay
  only the new lower minimum, amortisation will be slower than modelled.
- The backtest applies the two-month verðbætur lag and models the variable
  óverðtryggt rate with payment resets as the policy rate moves.

## Headline results (43m ISK, 4% real / 9% nominal, 30 years, annuity)

- The fixed-payment strategy breaks even against the óverðtryggt loan at
  **~5.5% average inflation**; growing the committed payment with inflation
  pushes breakeven to **~6.6%**. Below those lines the strategy wins, above
  them the óverðtryggt loan wins despite the overpayments.
- The decision therefore collapses to one question: will Icelandic inflation
  average above or below ~5.5% over the loan's life? (Seðlabanki target: 2.5%.)
- Passive verðtryggt (paying only the required minimum) is the worst real-cost
  outcome in every scenario tested.

## Structure

```
lanareiknir/
  engine.py     core simulation: both loan types, both payment structures,
                time-varying inflation/rates, overpayment strategies,
                breakeven and match-payment solvers
  data.py       Hagstofa PX-Web CPI + Seðlabanki rate fetchers (cached),
                with approximate offline fallback series
  backtest.py   2015–2025 historical run
tests/          7 tests: closed-form annuity, zero-inflation equivalence,
                equal-principal mechanics, Fisher breakeven region,
                match-payment verification
web/index.html  self-contained interactive calculator (Icelandic UI);
                JS engine cross-validated against the Python engine
                to the króna
```

## Run

```bash
pip install numpy pandas pytest
python -m pytest tests/
python -m lanareiknir.backtest      # uses fallback data offline;
                                    # fetches live Hagstofa data when online
```

## Caveats

This is a model, not financial advice. Backtest results are sensitive to the
assumed óverðtryggt rate spread and reset behaviour — verify against the
actual quotes and reset terms your bank offers. The bundled fallback series
are approximate annual averages; run `data.fetch_cpi()` online to replace
them with the official monthly series before citing backtest numbers.
