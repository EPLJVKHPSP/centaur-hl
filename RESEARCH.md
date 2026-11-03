# Hyperliquid builder profitability: methods and four answers

Snapshot: 30 October 2026. Review: 2 November 2026. This file supplements the one-page `findings.html` / `findings.pdf`.

## Prospective-client evidence (added 3 November 2026)

`python3 build.py` recomputes `commercial_evidence.json` from the supplied wallet files. Its three client-facing observations are: (1) the top 100 of 32,886 positive-PnL wallets account for 72.77% of gross winning account perps PnL; (2) 1,509 of 151,423 wallets use more than one grouped company and account for 9.23% of observed builder-routed wallet volume; (3) accounts with negative 30-day `perpPnl` generate 84.86% of observed builder fees. A separate **builder-wallet record-level** comparison using realized `closedPnl` gives 48.05%, because individual wallets can have different `closedPnl` values across builders. The principal figures are **account-level and source-window observations**. The data do not test whether top wallets win consistently over time, why cross-company users choose their applications, or whether losing traders subsequently churn. Those business questions require longitudinal or product-level evidence.

## 1. Which types have the most profitable traders?

| Type | Companies | Profitable / nonzero wallet observations | Profitable wallets | Profitable share of all routed wallet volume | Account PnL / builder dollar | Builder fees |
|---|---:|---:|---:|---:|---:|---:|
| Trading app | 7 | 3,935 / 13,892 | 28.33% | 23.56% | -0.1351% | $0.478m |
| Terminal & analytics | 7 | 1,008 / 3,908 | 25.79% | 31.62% | -0.0572% | $1.020m |
| Wallet | 10 | 14,921 / 67,034 | 22.26% | 14.98% | -0.7248% | $6.261m |
| Social trading | 3 | 10,677 / 53,337 | 20.02% | 13.89% | -0.3910% | $2.039m |
| Automation & AI | 3 | 151 / 831 | 18.17% | 29.77% | -0.0725% | $0.121m |

**The answer changes with the measure.** Wallet has the most winning wallet-company observations (14,921). Trading app has the highest profitable-wallet rate (28.33%). Terminal & analytics leads by profitable volume share (31.62%) and has the least-negative PnL per dollar (-0.0572%). All five types have negative aggregate account PnL. A wallet may recur across companies, so these are not counts of distinct people.

The top 30 companies have one primary type each; the other 92 are unclassified. Labels describe the product, not the observed traders. On review, fomo moved from Trading app to Social trading because its [official product page](https://fomo.family/) emphasizes social discovery, following traders, a feed and alerts. This changes the type rankings. The four previously recorded user choices (entropy.io and HyperLink as Trading app; near.com and Tria as Wallet) remain. HyperLink is Low confidence because the permitted categories do not fit execution infrastructure well. `labels.csv` records evidence and confidence for each type, form factor and tag.

## 2. Is the PnL earned through the builder?

**The data does not establish that.** All 2,056 wallets that appear under several builder codes have identical valid perps PnL in those records, despite different routed volumes. Summing company PnLs gives -$103.748m; counting each wallet once gives -$100.932m. Deduplication fixes repetition, but cannot assign those profits or losses to a particular execution route.

The historical API comparison covers 204 deliberately sampled wallets. Cached responses pass the script's pagination and source-volume consistency checks for 196; 5 have routed volume more than 1% above returned fill volume and 3 return no fills. These exclusions are not treated as zero trading volume.

For 118 usable overlapping wallets out of 125 sampled, the median combined selected-builder / returned Hyperliquid fill-volume share is **94.57%**. The median largest-single-builder share is **70.28%**. Their combined selected-builder volume is $674.007m versus $997.836m in returned fills (67.55%). 20 of these wallets routed less than half their returned volume through the selected codes. None of these sample statistics estimates the full wallet population.

Requests cover the 30 days ending at each wallet's latest source download time; timestamps without offsets are assumed UTC. The [Hyperliquid API documentation](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint) specifies 2,000 fills per response and a restriction to the latest 10,000 fills. The script paginates using inclusive timestamps and removes repeated boundary fills. Some cached responses exceed the documented history limit; this discrepancy is not evidence that all history is available. **An exhausted page sequence is not proof of complete exchange history.** Fills may also span spot and perps markets, so this is a routing comparison with vendor-scope and quote-currency assumptions, not an exact perps ledger reconciliation. The 1% tolerance admits 9 ratios slightly above 100%; those are retained, not clipped.

By contrast, the 85.54% median largest-builder share calculated over all 2,056 overlapping wallets uses *only selected-builder volume* in its denominator. It does not measure total Hyperliquid activity. The repeated profile field `hyperliquidVolume24h` is platform-wide 24-hour volume and cannot supply a wallet's 30-day denominator.

Correction: keep wallet PnL unique for population totals; treat company PnL as an association; obtain trade routing and matched trade-level PnL before attribution. Allocating PnL in proportion to volume would be an estimate, not a measured result. Returned fills expose no builder address that resolves this attribution.

## 3. How much do the largest wallets matter?

Removing each company's largest wallet by **absolute perps PnL** reverses 19/120 eligible company net-PnL signs (15.8%). Removing ten reverses 16/113 (14.2%). Across companies, the median top-ten share of absolute PnL is 90.08%. Trasia changes from +$4.918m to -$0.142m after removing one wallet; Outcome changes from -$1.690m to +$1.655m. Borsa falls from +$7.169m to -$1,987 after removing ten.

For a typical account's result, use **median wallet PnL and the profitable-wallet rate together**, with sample size and the exclusion tests. Net PnL is dominated by extreme results; a win rate alone conceals loss magnitude. Exclusions remove the corresponding observed routed volume from the leaderboard denominator, an approximation because those totals do not fully reconcile. MOONTRADER falls to exactly zero after the top-ten exclusion; that is not counted as a positive-to-negative reversal. Top-one and top-ten tests require more than one and ten valid PnLs respectively.

## 4. Fees versus account gains and losses

Builders earned **$10.333m** on **$26.428bn** of routed volume: **3.91 basis points**. MetaMask earned $2.080m; Trust Wallet $1.663m; fomo $1.635m; Phantom $1.443m; HyperDash $0.600m. The table above gives classified-type fees; unclassified companies earned $0.413m.

Of 151,423 unique observed wallets, 151,312 have valid perps PnL: 32,886 positive, 113,956 negative and 4,470 zero. Winning accounts gained **$34.540m**, losing accounts lost **$135.472m**, and net account PnL was **-$100.932m**. The unique-wallet median is -$3.87. Builder fees equal 7.63% of gross account losses, but that is only a scale comparison: the records do not isolate losses caused by builder-routed trades, or the fees paid specifically by losing wallets. Do not subtract fees from `perpPnl` again without verifying its fee treatment.

## Data audit and definitions

- `leaderboards/list_{7d,30d,all}.json`: aggregate builder volume, fees, users and rate. Only 30d drives this analysis. Profiles hold identity, daily activity, coin distributions (top eight only), wallet-size bands and aggregate totals. Wallet files contain account PnL plus builder-routed volume and fees; equity is a download-time snapshot. `pack_info.json` records collection metadata.
- A wallet counts if it appears in a selected builder's 30d wallet file. Select nonblank public codes with volume strictly above $1m; group builder codes sharing an X account ID; use builder address when no ID exists. This gives 125 codes and 122 companies. Within each company, count each wallet and its PnL once, but sum its routed volume across that company's codes. No conflicting duplicate PnLs or duplicate rows within a builder were found.
- `perpPnl` is the perps account result; `pnl` also includes non-perp holdings, and `closedPnl` is a distinct realized measure. In 60,992 source rows, `pnl` and `perpPnl` differ by more than one cent. Use `perpPnl` throughout. The files do not independently reconcile its realized/unrealized, funding or fee components.
- Wallet profitability = positive / (positive + negative) valid PnLs. Zeros remain in net PnL and median, but not the win-rate denominator. Missing PnL contributes to neither PnL nor win rate.
- **Profitable volume = positive-PnL wallets' routed volume / all observed wallet routed volume.** Zero and missing-PnL wallets remain in this denominator. Missing PnL is not classified as a loss; `missing_pnl_volume_share` reports the uncertain share. The alternate conditional rate using only nonzero-PnL volume is exported as `pct_profitable_by_nonzero_volume`. `excluded_volume_share` applies only to that alternate rate. Use wallet totals for a consistent numerator/denominator scope; reported company volume remains the leaderboard total.
- Net PnL / dollar uses leaderboard volume. Concentration ranks absolute PnL, not positive PnL or trade volume, and divides the largest ten absolute values by all absolute PnL. No absolute PnL means an undefined ratio, not zero.

Three traps to distrust: repeated account PnL mistaken for builder-earned profit; snapshot totals assumed to reconcile; and incomplete fill histories mistaken for total activity. Atomic's wallet volume is 10.46% below its leaderboard total; Outcome wallet fees are 5.65% above revenue; 25 builder user counts differ from wallet row counts. There are 111 missing and 4,475 zero-PnL source rows. The dashboard flags reconciliation differences above 1%.

Verification uses an independent raw-data calculation of all eight required metrics for all 122 companies, plus synthetic denominator, grouping, missing-data, exclusion, pagination and decile tests. Source links were opened; HTTP reachability is recorded separately from the content checks and does not prove a feature works. Product claims and phone-sized browser checks are AI-assisted, not independent human or funded-trade verification.

The 2 November review also corrected volume-decile membership to sort by actual routed volume; a zero residual after removing top wallets is not counted as a sign reversal (19/120 flip after removing the single largest, 16/113 after removing ten). fomo's defining social workflow moved it to `Social trading`, changing the type leaderboard. Source decisions were tightened for Insilico, Bullpen and HyperDash, and all 300 product-tag candidates received an explicit evidence status (48 verified, 176 no qualifying feature found in reviewed material, 76 insufficient evidence). Twenty-four of 30 companies have supported tags, and six deliberately have none. These figures describe the reviewed evidence snapshot rather than a complete independent source audit; the user made targeted decisions documented in `AI_LOG.md`.
