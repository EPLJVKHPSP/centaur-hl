# Centaur strategy — first verified public LONG after a 24h dip

**Presentation:** `graphics/dip_signal_infographic.png` is the 1600 × 900 Centaur-style X graphic. Its reproducible generator is `graphics/render_infographic.py` (requires Pillow), and `graphics/post_copy.md` contains a proposed X caption plus the explanatory methodology note. The graphic is a draft for review, **not submitted**.

**Rule:** Follow a source-verified public altcoin LONG opening call when the *same trader* has had no accepted LONG opening call for that coin in the preceding seven days, and the coin's publicly observable 24h spot price change is negative. Buy at the **next Binance spot hourly open** after the public call, then sell **24 hours after entry**. Charge an illustrative **0.30 percentage-point round-trip cost** to both the signal and market comparison. Only accept the first such signal per coin in each 24-hour holding period.

**Timing is critical:** At a 12:34 UTC publication, we assess the dip using the **12:00 hourly open versus the previous day's 12:00 open**, then simulate buying at **13:00**. The 13:00 price must not decide whether to trade or which peers qualify. This was corrected during the November 8 audit; figures from the earlier version of this backtest should be discarded.

## Run (Python 3; offline)

This `x-assignment` branch contains the backtesting code, tests, methodology, and X graphic. The **private Centaur-derived input data are intentionally excluded from Git**, including from this private GitHub repository. To reproduce the reported numerical findings, restore the two local files from the original analysis folder:

```bash
git switch x-assignment
mkdir -p data
cp ~/Desktop/centaur-strategy/data/observations.json data/
cp ~/Desktop/centaur-strategy/data/spot_hourly.json data/
python3 -m unittest -q test_backtest.py
python3 backtest.py
```

The input files are `data/observations.json` (812 previously verified Centaur public observations) and `data/spot_hourly.json` (35 Binance spot hourly asset series). You need authorized copies of both inputs to reproduce the historical numbers; the two `cp` commands above work on the original analysis Mac. The script writes `results.json` locally. Once inputs are present, the backtest needs no API key, network connection or external Python libraries. Alternative paths can be provided using `--observations` and `--prices`.

The tests that use synthetic fixtures work even when private datasets are absent; three frozen-dataset regression tests are explicitly skipped until both files are supplied. The X graphic is included; regenerating it requires `results.json` and Pillow.

## Reproducible results (November 8, 2026 audit)

| Publication period (UTC) | Three-peer matched calls | Mean hypothetical net return | Same-hour three-dip-peer mean | Difference, percentage points |
| --- | ---: | ---: | ---: | ---: |
| Aug 1–Oct 24 | **97** (of 98 non-overlapping signals) | **+1.515%** | **+0.535%** | **+0.980 pp** |
| Oct 25–Nov 6 | **17** | **+3.700%** | **+1.006%** | **+2.693 pp** |

For the first period, the *median* advantage against peers is **−0.015 pp**, and only **49.5%** beat their peer basket. Removing the five trades with the largest absolute excess returns reduces the mean advantage to **+0.392 pp**. For the later period, the median is **+1.307 pp**, and removing those five reduces the mean from +2.693 to **+1.068 pp**. The later period has only 17 signals, and **both periods were examined during strategy discovery**; neither is a clean out-of-sample test.

A tougher retrospective comparison uses **three earlier dip entries in the *same coin***, with a similar direction of the preceding BTC price move and without an observed recent Centaur opening call in our cached sample. After correcting the post-time precision in this control, it finds **+0.829 pp** excess in 92 earlier-period matches (date-cluster bootstrap interval **−0.929 to +2.653 pp**) and **+2.096 pp** in 16 later matches (interval **−0.483 to +4.110 pp**). Both intervals include zero. Historical controls may differ in news and market conditions; they cannot establish causality.

An additional one-hour execution delay reduces the three-peer relative advantage to **+0.935 pp** (97 matched) and **+1.937 pp** (17 matched). At three hours, it is **+0.782 pp** and **+1.586 pp**. The full 0–3h sensitivity, 1/3/5-peer matches, concentration, fees, direct dip-vs-rise comparison and historical controls are reproducible in `results.json`.

## Audit and limitations

- **Checked:** All 812 cached calls' hourly timestamp ordering, stored 24h PnL arithmetic and source-feature consistency against raw price panels; duplicate detection; positivity, finite values, hourly alignment and continuity of the 35 series. All seven-day freshness flags agree with the preceding accepted same-trader/coin/direction calls **within this cached sample** (including all 178 `fresh=false` rows). Independently spot-checked Binance opening prices over the network for 12 asset pairs; all matched cached data. Independently recomputed the 3-peer strategy directly from the input JSON, reproducing both sample sizes and all reported primary means. Added tests for publication-time information, seven-day freshness consistency, tie-breaking, 24h overlap across the period boundary, missing peer outcomes, prior-only controls, BTC matching, price corruption and the fixed-dataset results.
- **Fixed:** The old filter and peer selection used the *future entry-open price* as though available when the public signal appeared. The selection and all controls now use the previous known hourly open. A same-hour conflict now selects the **earliest actual publication**, rather than the lowest trader ID. The coin cooldown now applies across the earlier/recent boundary. Missing future peer prices cannot cause the ranking to switch to a more convenient peer. Another control-only bug rounded all public timestamps forward to entry hours before checking if a control had a recent post; using the exact public post timestamp changes the 14-day historical control sample from **91 to 92** earlier matches and its reported excess from **+0.861 to +0.829 pp**, and changes the later excess from **+2.237 to +2.096 pp** (16 matches). The primary three-peer strategy numbers are unaffected.
- **Still uncertain:** The offline observations were built upstream from Centaur's public-post/event verification, but the raw source messages are **not included**, so their original publication times cannot be independently authenticated from this folder alone. Our 812 fully priced observations are a restricted sample, and earlier unseen posts could affect a no-prior-call control and a seven-day freshness flag. Although the earlier window is labelled August 1–October 24, the earliest cached observation is **August 10**. The source's 24h duplicate suppression applies before its seven-day freshness rule. Publication dates define the periods; the bootstrap clusters by **entry UTC date**. The 35 spot assets are a fixed, selected universe, not every Hyperliquid coin.
- **Trading realism:** Simulated Binance spot open prices are not actual fills or Hyperliquid perps returns. Costs are illustrative (no measured funding, latency, spreads or market impact). Multiple simultaneous coin positions are treated as equal-weight individual trades, not a capital-constrained portfolio. Results may be driven by a few large winners or market moves. They do **not** establish profitable live copy trading or an incremental signal edge over buying dips.

This branch contains the backtest, tests, documentation and X draft graphic. The input data and regenerated `results.json` remain private local files, excluded by `.gitignore`. The larger multi-strategy exploration remains in the separate local `centaur-ideas-analysis` project. Confirm redistribution rights before sharing Centaur-derived raw inputs.
