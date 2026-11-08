# Proposed X post — for review, not submitted

Can public LONG signals beat buying the dip? We tested 114 Centaur-tracked first LONG calls after 24h altcoin dips. Their simulated 24h return beat matched dip peers by +0.98 pp (earlier sample) and +2.69 pp (later), after assumed costs. Promising, but not a proven edge.

## What the graphic actually shows

**Idea.** Use the first source-checked public LONG opening call from a trader for a given altcoin in seven days, *when that coin had already fallen over the preceding 24 hours*. Assess the dip using only the last observable hourly price at publication. Simulate entry at the next Binance spot hourly open and exit 24 hours later. Apply an illustrative 0.30 percentage-point round-trip cost. Treat overlapping calls on the same coin as one trade.

**Test.** Compare each qualifying signal with an equally timed basket of three other coins that were also in a known 24-hour dip, charging the same cost. The earlier publication window covers observations from **August 10 to October 24, 2026** (97 comparable calls), and the later window runs **October 25 to November 6, 2026** (17 comparable calls).

**Results.** Earlier signals averaged **+1.515%** hypothetical net return versus **+0.535%** for dip peers (**+0.980 percentage points**). Later signals averaged **+3.700%** versus **+1.006%** (**+2.693 percentage points**). These are *per-signal averages*, not portfolio returns or a claim of realized trading profits.

**What to distrust.** Only **49.5%** of earlier-period signals beat their same-hour peers, and the earlier *median* relative result was **−0.015 pp**. Remove the five earlier trades with the largest absolute relative results and the mean advantage falls to **+0.392 pp**. Both periods helped select this strategy; **neither is untouched out-of-sample evidence**. A tougher same-coin historical dip comparison produces confidence intervals that include zero. The cached 812 Centaur-derived observations and 35 Binance spot price series are a restricted, previously selected sample. Raw source posts are absent from this folder, so publication times cannot be independently authenticated from the packaged inputs. Actual fills, funding, spreads and market impact were not measured. This is a candidate for forward testing, not a validated live trading signal.

**Practical use.** For a trading app or research client, this is a screen for trader calls worth testing against a plain market baseline before surfacing them as actionable signals.

## Rebuild and check

From the `x-assignment` branch root, after restoring the two local datasets (see `README.md`):

```bash
python3 -m unittest -q test_backtest.py
python3 backtest.py
python3 graphics/render_infographic.py
```

The infographic requires Pillow (`python3 -m pip install pillow` if missing). Both its figures and the detailed checks come from `results.json`. Keep the cached offline datasets and API credentials private; check redistribution rights before releasing any raw input data.
