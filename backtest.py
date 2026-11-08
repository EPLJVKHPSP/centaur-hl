#!/usr/bin/env python3
"""Standalone, offline backtest: first verified public altcoin LONG after a dip.

Data: Centaur source-verified public calls and Binance spot hourly opens.
Research-only, no API key/network/trading required. Both periods informed
rule selection; returns are simulated and are not confirmed trader fills.
"""
import argparse
import bisect
import json
import math
import random
import statistics as stats
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
HOUR = 3600
DAY = 86400
HOLD_HOURS = 24
COST = 0.30  # Illustrative round-trip cost in percentage points, not measured.
EARLIER_START, EARLIER_END = "2026-08-01", "2026-10-24"
RECENT_START, RECENT_END = "2026-10-25", "2026-11-06"


def load_saved_data(observation_path, price_path):
    with open(observation_path, encoding='utf-8') as handle:
        rows = json.load(handle)
    with open(price_path, encoding='utf-8') as handle:
        prices = json.load(handle)
    bars = {int(asset): {int(epoch): float(price) for epoch, price in series.items()}
            for asset, series in prices.items()}
    return rows, bars


def validate_prices(bars):
    """Reject gaps, invalid hourly timestamps and corrupt/nonpositive prices."""
    if not bars or 1 not in bars:
        raise ValueError('Missing BTC benchmark or empty hourly price panels')
    for asset, series in bars.items():
        if not series:
            raise ValueError(f'Empty price panel for asset {asset}')
        times = sorted(series)
        if any(t % HOUR for t in times):
            raise ValueError(f'Non-hourly timestamp for asset {asset}')
        if any(not math.isfinite(p) or p <= 0 for p in series.values()):
            raise ValueError(f'Invalid spot opening price for asset {asset}')
        if any(b - a != HOUR for a, b in zip(times, times[1:])):
            raise ValueError(f'Missing or duplicated hourly candle for asset {asset}')


def prepare_events(rows, bars):
    """Attach 24h trend observable when the public call appears.

At a 12:34 publication the 12:00 hourly open is known; the 13:00
execution open is not. Never screen or match a trade using its fill price.
Preserve the source's entry-open feature for independent audit only.
"""
    prepared = []
    seen = set()
    for row in rows:
        t = row['entry_epoch']
        stamp = datetime.fromisoformat(row['timestamp'])
        if stamp.tzinfo is None or t % HOUR or not stamp.timestamp() < t <= stamp.timestamp() + HOUR:
            raise ValueError('Invalid public-to-entry timing')
        key = (row['trader'], row['asset'], row['side'], row['timestamp'])
        if key in seen:
            raise ValueError(f'Duplicate observation {key}')
        seen.add(key)
        coin = bars[row['asset']]
        btc = bars[1]
        # The last hourly OPEN observable by the timestamp of publication.
        pre_entry = t - HOUR
        dip = price_change(coin, pre_entry - DAY, 24)
        market = price_change(btc, pre_entry - DAY, 24)
        if dip is None or market is None:
            raise ValueError(f'Missing pre-publication trend for {key}')
        cached = price_change(coin, t - DAY, 24)
        if cached is None or abs(cached * row['side'] - row['price_24h']) > 1e-7:
            raise ValueError(f'Cached price_24h differs from raw bars for {key}')
        exit_change = price_change(coin, t, HOLD_HOURS)
        if exit_change is None or abs(row['ret24'] - (row['side'] * exit_change - COST)) > 1e-7:
            raise ValueError(f'Cached net 24h return differs from raw bars for {key}')
        if row['side'] not in (-1, 1):
            raise ValueError(f'Unexpected trade side: {row["side"]}')
        prepared.append({**row, 'decision_24h_pct': dip,
                         'decision_market_24h_pct': market})
    return prepared


def cluster_ci(rows, key, field='diff', repetitions=2500, seed=20261108):
    """Percentile bootstrap clustered by ENTRY date or signal trader/asset.

    Descriptive uncertainty only: repeated assets and the strategy-search
    process are not fully handled by these intervals.
    """
    grouped = defaultdict(list)
    for row in rows:
        k = datetime.fromtimestamp(row['entry_epoch'], tz=timezone.utc).date().isoformat() if key == 'day' else row[key]
        grouped[k].append(row[field])
    if len(grouped) < 3:
        return None
    keys = list(grouped)
    rng = random.Random(seed)
    boot = []
    for _ in range(repetitions):
        sampled = rng.choices(keys, k=len(keys))
        boot.append(stats.mean(value for group in sampled for value in grouped[group]))
    boot.sort()
    return (round(boot[int(.025 * repetitions)], 3),
            round(boot[int(.975 * repetitions) - 1], 3))


def nonoverlap(rows, horizon):
    """Select only non-overlapping signals for each asset, chronologically."""
    next_entry = defaultdict(int)
    chosen = []
    for row in sorted(rows, key=lambda x:(x['entry_epoch'],x['timestamp'],x['asset'],x['trader'])):
        if row['entry_epoch'] < next_entry[row['asset']]:
            continue
        chosen.append(row)
        next_entry[row['asset']] = row['entry_epoch']+horizon*3600
    return chosen


def price_change(bars, epoch, hours):
    first, last = bars.get(epoch), bars.get(epoch + hours * 3600)
    return (100 * (last / first - 1)
            if first is not None and last is not None
            and math.isfinite(first) and math.isfinite(last)
            and first > 0 and last > 0 else None)


def dip_candidates(row, bars, restrict_asset=None, restrict_day=None):
    """Dip observed before entry; future return used ONLY to score controls."""
    signal_t = row['entry_epoch']
    for asset, series in bars.items():
        if asset == 1 or (restrict_asset is not None and asset != restrict_asset):
            continue
        if restrict_day is None:
            entry_times = (signal_t,)
        else:
            day = signal_t // 86400 * 86400
            entry_times = (day + h * 3600 for h in range(24))
        for t in entry_times:
            prior = price_change(series, t - HOUR - DAY, 24)
            after = price_change(series, t, HOLD_HOURS)
            if prior is None or after is None or prior >= 0:
                continue
            yield asset, t, prior, after-COST


def same_asset_day_dip_placebo(row, bars, min_count=3):
    """Hindsight-selected same-asset/day dip hours, excluding close hours.

    This is a diagnostic, not an actionable control: one cannot know which
    calendar dates will later have a public trader call.
    """
    candidates = [(abs(prior-row['decision_24h_pct']), t, future)
                  for _, t, prior, future in dip_candidates(
                      row,bars,restrict_asset=row['asset'],restrict_day=True)
                  if abs(t-row['entry_epoch']) >= 2*3600]
    if len(candidates) < min_count:
        return None
    return stats.mean(x[2] for x in sorted(candidates)[:min_count])


def select(rows):
    return [r for r in rows if r['asset'] != 1 and r['side']==1
            and r['decision_24h_pct'] < 0 and EARLIER_START <= r['timestamp'][:10] <= RECENT_END]


def annotate(rows,bars):
    found=[]
    for row in rows:
        score=price_change(bars[row['asset']],row['entry_epoch'],HOLD_HOURS)
        if score is None:continue
        item={**row, 'ret':score-COST,
              'same_asset_day_dip':same_asset_day_dip_placebo(row,bars)}
        found.append(item)
    return found


def closest_dip_peer_ids(row, bars, k):
    """Find the k closest dips using prices known at PUBLICATION, no outcomes."""
    t = row['entry_epoch']
    viable = []
    for aid, series in bars.items():
        if aid in (1, row['asset']):
            continue
        prior = price_change(series, t-HOUR-DAY, 24)
        if prior is None or prior >= 0:
            continue
        viable.append((abs(prior-row['decision_24h_pct']), aid))
    if len(viable) < k:
        return None
    return [aid for _,aid in sorted(viable)[:k]]


def dip_peers(row, bars, k):
    """Score fixed pre-entry peer selection; never replace a missing outcome."""
    ids = closest_dip_peer_ids(row, bars, k)
    if ids is None:
        return None
    returns = [price_change(bars[aid],row['entry_epoch'],HOLD_HOURS)
               for aid in ids]
    if any(v is None for v in returns):
        return None
    return stats.mean(v - COST for v in returns)


def no_prior_call_same_asset(row, bars, events, k=3, window_days=14):
    """Compare with same-asset earlier dip entries lacking a recent public call.

    Price-only controls use *only* timestamps preceding the Centaur signal by
    at least 24h and have no known prior Centaur public call in the preceding
    24h.  The matching rule deliberately conditions on the later Centaur call,
    so this is an explanatory benchmark, not a deployable counterfactual.
    """
    t0 = row['entry_epoch']
    series = bars[row['asset']]
    calls = events[row['asset']]  # Actual public publication seconds, not rounded entry hours.
    choices = []
    for steps in range(25, window_days*24 + 1):
        t = t0 - steps*3600
        start = series.get(t)
        prior = series.get(t - HOUR - DAY)
        last_known = series.get(t - HOUR)
        later = series.get(t + HOLD_HOURS*3600)
        if not all((start, prior, last_known, later)):
            continue
        dip = 100 * (last_known/prior - 1)
        if dip >= 0 or any(t - 86400 <= call <= t for call in calls):
            continue
        changes = 100*(later/start-1) - COST
        choices.append((abs(dip-row['decision_24h_pct']), t, changes))
    selected = []
    for cand in sorted(choices):
        if all(abs(cand[1]-other[1]) >= 86400 for other in selected):
            selected.append(cand)
            if len(selected) == k:
                return stats.mean(x[2] for x in selected)
    return None


def clean_peak(rows, field, percentile=0.05):
    """Remove largest absolute winners AND losers: outlier-neutral sensitivity."""
    leave_out = int(len(rows) * percentile)
    if leave_out == 0:
        return rows
    return sorted(rows, key=lambda r: abs(r[field]))[:-leave_out]


def summary(rows, cost=COST):
    """Report observed means, tails, concentration, and clustered dispersion."""
    if not rows:
        return None
    by_asset, by_trader = defaultdict(list), defaultdict(list)
    for r in rows:
        by_asset[r['asset']].append(r)
        by_trader[r['trader']].append(r)
    peak_asset = max(by_asset, key=lambda a: len(by_asset[a]))
    peak_trader = max(by_trader, key=lambda a: len(by_trader[a]))
    excess = [r['diff'] for r in rows]
    return {
        'n': len(rows), 'dates': len({r['timestamp'][:10] for r in rows}),
        'traders': len(by_trader), 'assets': len(by_asset),
        'mean_net_signal_pct': round(stats.mean(r['net']-cost for r in rows),3),
        'median_net_signal_pct': round(stats.median(r['net']-cost for r in rows),3),
        'win_rate_pct': round(100*sum(r['net']>cost for r in rows)/len(rows),1),
        'worst_net_signal_pct': round(min(r['net']-cost for r in rows),3),
        'best_net_signal_pct': round(max(r['net']-cost for r in rows),3),
        'mean_net_peer_pct': round(stats.mean(r['peer'] for r in rows),3),
        'mean_excess_pp': round(stats.mean(excess),3),
        'median_excess_pp': round(stats.median(excess),3),
        'beats_peer_pct': round(100*sum(x>0 for x in excess)/len(excess),1),
        'equal_asset_excess_pp': round(stats.mean(stats.mean(x['diff'] for x in group)
                                              for group in by_asset.values()),3),
        'equal_trader_excess_pp': round(stats.mean(stats.mean(x['diff'] for x in group)
                                               for group in by_trader.values()),3),
        'trim_5pct_abs_excess_pp': round(stats.mean(r['diff'] for r in clean_peak(rows,'diff')),3),
        'without_five_largest_abs_excess_pp': round(
            stats.mean(r['diff'] for r in sorted(rows, key=lambda r: abs(r['diff']))[:-5]), 3
        ) if len(rows) > 5 else None,
        'without_top_asset_excess_pp': round(stats.mean(r['diff'] for r in rows
                                                       if r['asset'] != peak_asset),3),
        'top_asset': peak_asset, 'top_asset_n': len(by_asset[peak_asset]),
        'without_top_trader_excess_pp': round(stats.mean(r['diff'] for r in rows
                                                        if r['trader'] != peak_trader),3),
        'top_trader': peak_trader, 'top_trader_n': len(by_trader[peak_trader]),
        'date_cluster_ci_pp': cluster_ci(rows,'day',field='diff',repetitions=2000),
        'asset_cluster_ci_pp': cluster_ci(rows,'asset',field='diff',repetitions=2000),
        'trader_cluster_ci_pp': cluster_ci(rows,'trader',field='diff',repetitions=2000),
    }


def direct_dip_rising_comparison(all_events):
    """Competing fresh LONG calls: dip vs rise with shared asset cooldown.

    This is descriptive, not a causal experiment. Selecting nonoverlapping
    events *before* splitting prevents counting simultaneous asset exposures
    in both sides of the comparison. Entry-price 24h momentum is known then.
    """
    eligible = [r for r in all_events
                if EARLIER_START <= r['timestamp'][:10] <= RECENT_END
                and r['asset'] != 1 and r['side'] == 1 and r['fresh']]
    global_chosen = nonoverlap(eligible, HOLD_HOURS)
    out = {}
    for name, begin, end in [('earlier', EARLIER_START, EARLIER_END),
                             ('recent', RECENT_START, RECENT_END)]:
        chosen = [r for r in global_chosen if begin <= r['timestamp'][:10] <= end]
        dip = [r for r in chosen if r['decision_24h_pct'] < 0]
        rising = [r for r in chosen if r['decision_24h_pct'] >= 0]
        trader_groups, asset_groups = defaultdict(lambda: [[], []]), defaultdict(lambda: [[], []])
        for r in chosen:
            bucket = 0 if r['decision_24h_pct'] < 0 else 1
            trader_groups[r['trader']][bucket].append(r['ret24'])
            asset_groups[r['asset']][bucket].append(r['ret24'])
        def paired(groups):
            return [stats.mean(dip_side) - stats.mean(rising_side)
                    for dip_side, rising_side in groups.values()
                    if dip_side and rising_side]
        trader_deltas, asset_deltas = paired(trader_groups), paired(asset_groups)
        out[name] = {
            'nonoverlap_all_fresh_longs': len(chosen),
            'dip_n': len(dip), 'rising_n': len(rising),
            'dip_mean_net_pct': round(stats.mean(r['ret24'] for r in dip), 3) if dip else None,
            'rising_mean_net_pct': round(stats.mean(r['ret24'] for r in rising), 3) if rising else None,
            'unadjusted_dip_minus_rising_pp': round(
                stats.mean(r['ret24'] for r in dip) - stats.mean(r['ret24'] for r in rising), 3
            ) if dip and rising else None,
            'traders_with_both': len(trader_deltas),
            'equal_trader_dip_minus_rising_pp': round(stats.mean(trader_deltas), 3) if trader_deltas else None,
            'assets_with_both': len(asset_deltas),
            'equal_asset_dip_minus_rising_pp': round(stats.mean(asset_deltas), 3) if asset_deltas else None,
        }
    return out


def analyze(rows, bars, all_events):
    indexed = index_publications(all_events)
    global_chosen = nonoverlap(rows, HOLD_HOURS)
    output = {}
    for name, begin, end in [('earlier',EARLIER_START,EARLIER_END),
                             ('recent',RECENT_START,RECENT_END)]:
        chosen = [r for r in global_chosen if begin <= r['timestamp'][:10] <= end]
        results = {'date_window':[begin,end], 'original_n':len(chosen)}
        for k in (1,3,5):
            items = []
            for row in chosen:
                peer = dip_peers(row,bars,k)
                if peer is None:
                    continue
                items.append({**row,'net':row['ret']+COST,'peer':peer,
                              'diff':row['ret']-peer})
            results[f'{k}_matched_peers'] = summary(items)
            if k == 3:
                results['by_month'] = {m:summary([r for r in items if r['month']==m])
                                       for m in sorted({r['month'] for r in items})}
                results['cost_sensitivity_pct'] = {
                    str(cost): round(stats.mean(r['net']-cost for r in items),3)
                    for cost in (0.1,0.3,0.6,1.0,2.0,3.0)}
                results['same_asset_day_dip'] = summary([
                    {**r,'peer':r['same_asset_day_dip'],
                     'diff':r['ret']-r['same_asset_day_dip']}
                    for r in items if r['same_asset_day_dip'] is not None])
                rows_without_call=[]
                for r in items:
                    candidate=no_prior_call_same_asset(r,bars,indexed)
                    if candidate is None:
                        continue
                    rows_without_call.append({**r,'peer':candidate,'diff':r['ret']-candidate})
                results['historical_price_only_dip'] = summary(rows_without_call)
        output[name] = results
    return output


def execution_delay_sensitivity(rows, bars):
    """Buy one or more hours late, and hold 24h; fixed pre-call peer matches.

    These are sensitivity scenarios, not reruns with reoptimized parameters.
    """
    chosen = nonoverlap(rows, HOLD_HOURS)
    output = {}
    for name, begin, end in [('earlier', EARLIER_START, EARLIER_END),
                             ('recent', RECENT_START, RECENT_END)]:
        selected = [r for r in chosen if begin <= r['timestamp'][:10] <= end]
        result = {}
        for delay in (0, 1, 2, 3):
            pairs = []
            for row in selected:
                if dip_peers(row,bars,3) is None:
                    continue  # Keep the same valid original peer universe.
                peer_ids = closest_dip_peer_ids(row,bars,3)
                t = row['entry_epoch'] + delay*HOUR
                base = price_change(bars[row['asset']], t, HOLD_HOURS)
                peer_returns = [price_change(bars[aid],t,HOLD_HOURS) for aid in peer_ids]
                if base is None or any(v is None for v in peer_returns):
                    continue
                net = base - COST
                pairs.append((net, net - stats.mean(v - COST for v in peer_returns)))
            result[f'{delay}h'] = {
                'n': len(pairs),
                'mean_net_signal_pct': round(stats.mean(p[0] for p in pairs),3) if pairs else None,
                'mean_excess_pp': round(stats.mean(p[1] for p in pairs),3) if pairs else None,
            }
        output[name] = result
    return output


def index_publications(rows):
    """Index actual public timestamps, preserving their minute/second precision."""
    posted = defaultdict(list)
    for row in rows:
        posted[row['asset']].append(datetime.fromisoformat(row['timestamp']).timestamp())
    for asset in posted:
        posted[asset].sort()
    return posted


def no_recent_call(entry, sorted_publication_seconds, hours=24):
    """Exclude public calls in the preceding window, never later messages."""
    i = bisect.bisect_right(sorted_publication_seconds, entry)
    return i == 0 or entry - sorted_publication_seconds[i-1] > hours*HOUR


def controls_for(row, bars, posted_by_coin, days=7, forward=True, count=3):
    """Price dips in the same coin and neighboring weeks, with BTC-regime match.

    Feature matching: identical coin; 24h negative spot move; same sign of
    trailing 24h BTC spot move; nearest coin dip size and BTC move. Controls
    are >=24h away from the signal and from one another, and require no known
    Centaur post for the coin in the previous 24h. All inputs to the matching
    score are available at each potential entry hour, although selecting
    observations on dates after a signal is retrospective.
    """
    t0 = row['entry_epoch']
    coin, btc = bars[row['asset']], bars[1]
    expected_coin, expected_btc = row['decision_24h_pct'], row['decision_market_24h_pct']
    begin = t0 - days*DAY
    end = t0 + days*DAY if forward else t0 - DAY
    candidate = []
    for t in range(begin, end + 1, HOUR):
        if abs(t-t0) < DAY or not no_recent_call(t, posted_by_coin[row['asset']]):
            continue
        a, future = coin.get(t), coin.get(t+DAY)
        last_known, prev = coin.get(t-HOUR), coin.get(t-HOUR-DAY)
        b, b_prev = btc.get(t-HOUR), btc.get(t-HOUR-DAY)
        if not all((a,prev,last_known,future,b,b_prev)):
            continue
        dip = 100*(last_known/prev - 1)
        market = 100*(b/b_prev - 1)
        if dip >= 0 or (market < 0) != (expected_btc < 0):
            continue
        # Each feature is known by its potential entry; use equal pp units.
        score = abs(dip - expected_coin) + abs(market - expected_btc)
        candidate.append((score, abs(t-t0), t, 100*(future/a-1)-COST))
    chosen = []
    for item in sorted(candidate):
        if all(abs(item[2]-other[2])>=DAY for other in chosen):
            chosen.append(item)
            if len(chosen) == count:
                break
    return chosen if len(chosen) == count else []


def describe(signal_rows, bars, posted, days, forward):
    paired=[]
    for row in signal_rows:
        choices = controls_for(row, bars, posted, days=days, forward=forward)
        if not choices:
            continue
        baseline=stats.mean(x[3] for x in choices)
        paired.append({
            'timestamp':row['timestamp'], 'asset':row['asset'],
            'entry_epoch':row['entry_epoch'],
            'trader':row['trader'], 'diff':row['ret']-baseline,
            'signal':row['ret'], 'benchmark':baseline,
        })
    if not paired:
        return {'n':0, 'available_signal_n':len(signal_rows)}
    d=[r['diff'] for r in paired]
    by_month=defaultdict(list)
    for r in paired:
        by_month[r['timestamp'][:7]].append(r['diff'])
    return {
        'n':len(paired), 'available_signal_n':len(signal_rows),
        'dates':len({r['timestamp'][:10] for r in paired}),
        'traders':len({r['trader'] for r in paired}),
        'assets':len({r['asset'] for r in paired}),
        'signal_net_mean_pct':round(stats.mean(r['signal'] for r in paired),3),
        'same_coin_price_only_mean_pct':round(stats.mean(r['benchmark'] for r in paired),3),
        'paired_excess_pp':round(stats.mean(d),3),
        'paired_median_pp':round(stats.median(d),3),
        'beats_controls_pct':round(100*stats.mean(x>0 for x in d),1),
        'day_cluster_ci_pp':cluster_ci(paired,'day',repetitions=1500),
        'trader_cluster_ci_pp':cluster_ci(paired,'trader',repetitions=1500),
        'by_month':{m:{'n':len(vals),'mean_pp':round(stats.mean(vals),3)}
                    for m,vals in sorted(by_month.items())},
    }


def analyze_same_coin(all_rows,bars):
    posted = index_publications(all_rows)
    shortlisted=annotate([r for r in select(all_rows) if r['fresh']],bars)
    globally_selected=nonoverlap(shortlisted,HOLD_HOURS)
    output={}
    for period,start,end in [('earlier',EARLIER_START,EARLIER_END),
                             ('recent',RECENT_START,RECENT_END)]:
        signals=[r for r in globally_selected if start<=r['timestamp'][:10]<=end]
        output[period]={'signals':len(signals)}
        for days,forward in ((7,False),(14,False),(7,True),(14,True)):
            name=('preceding' if not forward else 'around')+f'_{days}d'
            output[period][name]=describe(signals,bars,posted,days,forward)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations', type=Path, default=DATA_DIR / 'observations.json')
    parser.add_argument('--prices', type=Path, default=DATA_DIR / 'spot_hourly.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'results.json')
    args = parser.parse_args()

    missing = [str(p) for p in (args.observations, args.prices) if not p.is_file()]
    if missing:
        parser.error(
            "Missing private local input file(s): " + ", ".join(missing)
            + ". Restore data/observations.json and data/spot_hourly.json "
            + "as explained in README.md."
        )

    saved_events, hourly_prices = load_saved_data(args.observations, args.prices)
    validate_prices(hourly_prices)
    events = prepare_events(saved_events, hourly_prices)
    selected = [row for row in select(events) if row['fresh']]
    signals = annotate(selected, hourly_prices)
    result = {
        'method': 'Historical exploratory analysis; both date windows used in selection; no exchange fills',
        'primary_filter': 'Fresh (7d) source-verified public altcoin LONG with negative 24h spot move known at publication; buy at next hourly open, hold 24h',
        'feature_timing': 'Dip and BTC trend use prior observable hourly opening price (entry hour minus 1h); selection never uses next-hour fill price',
        'market': 'Binance spot hourly price proxy, fixed illustrative 0.30 percentage-point round-trip cost',
        'results': analyze(signals, hourly_prices, events),
        'direct_fresh_long_dip_vs_rising': direct_dip_rising_comparison(events),
        'same_coin_btc_controls': analyze_same_coin(events, hourly_prices),
        'execution_delay_sensitivity': execution_delay_sensitivity(signals,hourly_prices),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    for label, block in result['results'].items():
        primary = block['3_matched_peers']
        control = result['same_coin_btc_controls'][label]['preceding_14d']
        print(f"{label} ({', '.join(block['date_window'])}):")
        print(f"  {primary['n']} calls; mean net {primary['mean_net_signal_pct']:+.2f}% "
              f"vs similar dip peers {primary['mean_net_peer_pct']:+.2f}%; "
              f"excess {primary['mean_excess_pp']:+.3f} pp")
        print(f"  same coin / similar BTC conditions: {control['n']} matched; "
              f"excess {control['paired_excess_pp']:+.2f} pp; "
              f"date-cluster interval {control['day_cluster_ci_pp']}")
    print('Exploratory, in-sample only. Results:', args.output)


if __name__ == '__main__':
    main()
