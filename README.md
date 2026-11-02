# Hyperliquid builder profitability

Open `dashboard.html` to see the completed interactive dashboard, including the scatter chart and three caveated findings at the top. It works offline on a laptop or phone. `dashboard_template.html` is the source layout; opening it redirects to `dashboard.html` in the same folder. `findings.html` is the one-page findings note; `findings.pdf` is its checked A4 print export. `RESEARCH.md` contains the methods and full answers to all four questions.

Metrics cover 122 companies, while the assignment's product-type research covers the top 30 by volume. All top 30 have one of the five required types. The other 92 are marked **Not researched (outside top 30)** in the dashboard. The underlying generated CSV uses `Unclassified` as a missing-label value; it is not a sixth type.

## Reproduce

Use Python 3.10 or newer; the core build needs only its standard library. Keep the original data pack under `datasets/`, with plain JSON wallet files as described in `datasets/DATA_README.md`:

```bash
python3 build.py
```

This regenerates the dashboard (including the type aggregates), HTML findings, company metrics and validation from the data pack and `labels.csv`. It also embeds the saved aggregate historical API comparison if present. For a different data location:

```bash
python3 build.py --data-dir /path/to/datasets
```

The supplied pack remains private. The submission archive excludes `datasets/`, `.cache/`, individual wallet records and API responses. The recipient needs their original data pack to rerun the calculation. No website has been published.

## What is included

| File | Purpose |
|---|---|
| `dashboard.html` | Selectable scatter, sortable/searchable company leaderboard, labels, evidence, stress tests and three findings |
| `findings.html`, `findings.pdf` | Three surprising results first, followed by type comparison and what to distrust; one printed page |
| `company_metrics.csv` | All eight required metrics for 122 companies, plus fees and coverage checks |
| `labels.csv`, `label_rules.md` | One row per top-30 company, with distinct type, form factor and product tags columns, sources, confidence and classification rules |
| `RESEARCH.md` | Four answers, denominators, source traps and attribution limits |
| `AI_LOG.md` | Short account of prompts, AI work and checks, with human decisions clearly distinguished |
| `build.py`, `dashboard_template.html` | Offline calculation and presentation source |
| `make_labels.py` | Recorded evidence seed; regenerates `labels.csv` and overwrites CSV-only edits |
| `volume_audit.py`, `volume_comparison.json` | Sampled historical routing comparison and cached aggregate result |
| `validation.json` | Reconciliations, shared-wallet checks and unique-account totals; type aggregates are embedded in the dashboard |
| `tests/test_build.py` | Independent metric and edge-case tests |

Open **`labels.csv`** for the complete top-30 classification table. The first columns show company rank/name, **type**, **form_factor**, and **product_tags** separately. Each row also preserves the type and form-factor evidence URLs, text and confidence. Product-tag research was **AI-assisted and then reviewed against the source evidence and inclusion rules**, with manual judgment on ambiguous decisions. The assignment says **“any product tags”**, so zero tags are allowed: 24 companies have at least one verified tag, while six (including Liquid) retain empty cells rather than unsupported guesses. The `tag_evidence` cell is a JSON list of sources and reasons for positive tags. The `tag_review` cell contains **all 10 tag decisions per company (300 total)**, with a source, explanation and one of three statuses: `Verified`, `No qualifying feature found`, or `Insufficient evidence`. The second status means a feature was not identified in the inspected material, *not* proof of absence; the third flags weaker or inaccessible evidence. Form factor `both` means usable mobile and desktop/web experiences. On 2 November the user explicitly reviewed and agreed to the four targeted evidence judgments documented in `label_rules.md`. `python3 make_labels.py` regenerates this file from the reviewed research seed and overwrites edits made only in the CSV. It does not call an LLM at build time.

## Calculation choices

Named builders with strictly more than $1m of 30d volume; builder codes sharing an X account are grouped. Volume and fees come from the leaderboard. Wallet count, net/median PnL and concentration use wallets deduplicated within the company. Only `perpPnl` is used.

Profitable wallets = positive / (positive + negative) valid PnLs. **Profitable volume = winning wallets' routed volume / all observed routed wallet volume**, including volume with zero or missing PnL. Missing PnL remains unknown; its volume share is exposed separately. The old conditional nonzero-volume rate is retained under the explicit alternate name `pct_profitable_by_nonzero_volume`.

Wallet PnL covers an account, not a builder execution route. Cross-company sums repeat some accounts; population gains/losses use one PnL per unique wallet. Type comparisons are descriptive and depend on classification choices. See `RESEARCH.md` for the limits.

## Historical API comparison

The saved comparison summarizes 204 sampled wallets: 196 usable returned histories, five source-volume inconsistencies and three empty histories. It is not a population estimate or proof of complete history. Public API history limits, quote currencies and source timing prevent exact ledger reconciliation.

To summarize the private cache again, then rebuild:

```bash
python3 volume_audit.py
python3 build.py
```

A fresh machine without the cache can query the public API with `python3 volume_audit.py --fetch --workers 1`. The script samples, caches and paginates; later API availability can change the result. The normal build uses the included aggregate JSON and does not contact the API. The checked PDF is a print export; printing regenerated `findings.html` with A4 paper and CSS margins refreshes it.

## Verify

```bash
python3 -m unittest discover -s tests -v
```

The 20 Python tests independently recompute all eight required metrics for 122 companies (976 company-metric comparisons) and cover missing/zero PnL, company grouping, exclusions, taxonomy, page boundaries, timezones and volume-decile membership. Checks confirmed 125 eligible builder codes and three company merges. AI-operated Chromium inspections used 1440px, 390px and 320px viewports to check sorting, filters, search, detail panels, confidence labels, axes and offline layout; the embedded JavaScript passed a syntax check. The A4 PDF was visually checked to be one page. The optional source-link checker reached 67/67 distinct URLs at the time of inspection; reachability alone cannot validate product claims.

**Human inspection and decisions:** I inspected the outputs while developing the assignment, raised questions about the results and formatting, and checked that the requested metrics, four questions, labels, dashboard and findings note were addressed. I personally settled four ambiguous primary types, confirmed mobile availability for Axiom and Outcome, requested a single clearly structured `labels.csv`, and reviewed and approved four targeted evidence/confidence decisions on 2 November. These were focused reviews and analytical judgments; the automated calculations, browser runs, link checks and print tests were executed with AI assistance. See `AI_LOG.md` for the division of work and `RESEARCH.md` for the traps that remain.

The original source-link audit and historical form-factor research are kept locally under `research_evidence/`, outside the 16-file submission. Final classification data and evidence are in `labels.csv` and `label_rules.md`.
