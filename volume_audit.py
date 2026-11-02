#!/usr/bin/env python3
"""Compare historical builder-routed volume to wallet-wide Hyperliquid fills.

Only aggregate results leave the private .cache directory. The 30-day window ends
at each selected wallet's original HyperTracker download timestamp (UTC assumed).
An API page capped at 2,000 trades needs time-based pagination. Even fully
paginated results can differ from the source's coverage and accounting.
"""
import argparse
import collections
import concurrent.futures
import datetime as dt
import hashlib
import json
import math
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = 'https://api.hyperliquid.xyz/info'
PAGE_SIZE = 2000
MAX_PAGES = 150


def sha(address):
    return hashlib.sha256(address.encode()).hexdigest()[:14]


def parse_date(s):
    # Source dates have no timezone; the HyperTracker dataset is treated as UTC.
    parsed = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    return parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed.astimezone(dt.timezone.utc)


def load_observations(folder):
    wallets = collections.defaultdict(lambda: {'builders': {}, 'downloads': []})
    builder_wallets = collections.defaultdict(list)
    for file in sorted((folder / 'wallets').glob('*_30d.json')):
        data = json.loads(file.read_text())
        cols = data['columns']
        address_idx, volume_idx = cols.index('address'), cols.index('volume')
        builder = data['builder'].lower()
        for row in data['rows']:
            address = row[address_idx].lower()
            volume = float(row[volume_idx] or 0)
            wallets[address]['builders'][builder] = volume
            wallets[address]['downloads'].append(data['downloaded'])
            builder_wallets[builder].append((address, volume))
    return wallets, builder_wallets


def stratified(entries, count_per_decile):
    ordered = sorted(entries, key=lambda a: (sum(wallet['builders'].values()) if (wallet := entries[a]) else 0, a))
    result = []
    for k in range(10):
        bucket = ordered[len(ordered) * k // 10:len(ordered) * (k + 1) // 10]
        # Spread selection across each volume decile, reproducibly.
        if bucket:
            count = min(count_per_decile, len(bucket))
            result += [bucket[min(len(bucket)-1, (i * len(bucket) + len(bucket)//2) // count)] for i in range(count)]
    return result


def choose_sample(folder, overlap_per_decile=10, single_per_decile=5, top_impact=25):
    wallets, builder_wallets = load_observations(folder)
    overlap = {addr: w for addr, w in wallets.items() if len(w['builders']) > 1}
    single = {addr: w for addr, w in wallets.items() if len(w['builders']) == 1}
    sample = collections.defaultdict(set)
    for addr in stratified(overlap, overlap_per_decile):
        sample[addr].add('overlap_decile')
    for addr in stratified(single, single_per_decile):
        sample[addr].add('single_decile')

    impact = sorted(overlap, key=lambda a:(-sum(wallets[a]['builders'].values()), a))[:top_impact]
    for addr in impact:
        sample[addr].add('high_volume_overlap')

    leaderboard = json.loads((folder / 'leaderboards' / 'list_30d.json').read_text())['builders']
    top30 = [b for b in leaderboard if b.get('refCode') and float(b['volume']) > 1e6]
    top30.sort(key=lambda b:-float(b['volume']))
    # One typical (middle-volume) source-wallet from each of the 30 leading codes.
    for builder in top30[:30]:
        users = sorted(builder_wallets[builder['address'].lower()], key=lambda v:(v[1],v[0]))
        if users:
            sample[users[len(users)//2][0]].add('top30_builder_median_wallet')
    overlap_deciles = {}
    ordered_overlap = sorted(overlap, key=lambda a:(sum(wallets[a]['builders'].values()),a))
    for k in range(10):
        for addr in ordered_overlap[len(ordered_overlap)*k//10:len(ordered_overlap)*(k+1)//10]:
            overlap_deciles[addr] = k+1
    return {a: {'selected_volume':sum(wallets[a]['builders'].values()),
                'largest_builder_volume':max(wallets[a]['builders'].values()),
                'builder_count':len(wallets[a]['builders']),
                'overlap_volume_decile':overlap_deciles.get(a),
                'end':max(wallets[a]['downloads']), 'strata':sorted(groups)}
            for a,groups in sorted(sample.items())}


def audit_fills(fills, observed):
    if not isinstance(fills, list):
        return {'status':'error', 'reason':'API did not return a fills array'}
    if len(fills) >= 2000:
        return {'status':'capped', 'fill_count':len(fills)}
    try:
        total = sum(float(f['px']) * float(f['sz']) for f in fills)
    except (TypeError, ValueError, KeyError):
        return {'status':'error', 'reason':'Malformed price/size in fills response'}
    if not math.isfinite(total) or total < 0:
        return {'status':'error', 'reason':'Invalid trade notional'}
    if total <= 0:
        return {'status':'zero_total', 'fill_count':len(fills), 'total_volume':total}
    # A 1% tolerance reflects rounding and small differences between source
    # download instants; larger inversion means source scopes still disagree.
    status = 'inconsistent' if observed > total * 1.01 else 'complete'
    return {'status':status, 'fill_count':len(fills), 'total_volume':total}


def request_page(request_data):
    for attempt in range(5):
        try:
            req = urllib.request.Request(API, data=json.dumps(request_data).encode(),
                 headers={'Content-Type':'application/json','User-Agent':'Centaur-VolumeAudit/1.1'})
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            if attempt == 4:
                raise
            time.sleep((12 if isinstance(exc, urllib.error.HTTPError) and exc.code == 429 else 2) * (attempt+1))


def collect_pages(address, start_ms, end_ms, observed, max_pages=MAX_PAGES, page_request=request_page):
    """Walk the historical range, retaining fill keys only at page boundaries.

    startTime is inclusive. Re-query the last timestamp to avoid dropping
    same-millisecond fills, then subtract the repeated boundary fills.
    A full page confined to one millisecond cannot be paginated safely.
    """
    current = start_ms
    previous_boundary = None
    boundary_keys = set()
    total = 0.0
    count = 0
    first_time = None
    last_time = None
    for page in range(1, max_pages+1):
        request_data = {'type':'userFillsByTime','user':address,
                        'startTime':current,'endTime':end_ms,'aggregateByTime':False}
        fills = page_request(request_data)
        if not isinstance(fills, list):
            return {'status':'error','reason':'Expected fills list', 'api_pages':page}
        try:
            times = [int(f['time']) for f in fills]
            if any(a>b for a,b in zip(times,times[1:])):
                raise ValueError('Non-chronological fills response')
            if any(t < current or t > end_ms for t in times):
                raise ValueError('Fill timestamp outside requested range')
            last = times[-1] if times else None
            newest_boundary_keys = set()
            for f,t in zip(fills,times):
                key = (f.get('tid'),f.get('oid'),t,f.get('coin'),f.get('side'),
                       f.get('px'),f.get('sz'),f.get('hash'))
                if t == previous_boundary and key in boundary_keys:
                    continue
                notional = float(f['px'])*float(f['sz'])
                if not math.isfinite(notional) or notional < 0:
                    raise ValueError('Invalid price * size')
                total += notional
                count += 1
                first_time = t if first_time is None else min(first_time,t)
                last_time = t
                if t == last:
                    newest_boundary_keys.add(key)
            if last == previous_boundary:
                newest_boundary_keys |= boundary_keys
        except (KeyError, TypeError, ValueError) as exc:
            return {'status':'error','reason':str(exc)[:160], 'api_pages':page}

        info = {'fill_count':count,'total_volume':total,'api_pages':page,
                'first_fill_ms':first_time,'last_fill_ms':last_time}
        if len(fills) < PAGE_SIZE:
            if total <= 0:
                return {**info,'status':'zero_total'}
            return {**info,'status':'inconsistent' if observed > total*1.01 else 'complete'}
        if last is None or last == current:
            return {**info,'status':'timestamp_limit',
                    'reason':'2,000 fills share a millisecond; cannot paginate safely'}
        if last is not None:
            boundary_keys = newest_boundary_keys
            previous_boundary = last
            current = last
    return {**info,'status':'page_limit',
            'reason':f'Exceeded {max_pages} historical fill pages'}


def fetch_one(address, details, cache, refresh=False):
    path = cache / (sha(address) + '.json')
    if path.exists() and not refresh:
        saved = json.loads(path.read_text())
        if saved.get('source_end') == details['end'] and saved.get('status') in ('complete','inconsistent','zero_total'):
            return saved
    end = parse_date(details['end'])
    start_ms = int((end-dt.timedelta(days=30)).timestamp()*1000)
    end_ms = int(end.timestamp()*1000)
    output = {'wallet':address, 'source_end':details['end'],
              'start_ms':start_ms, 'end_ms':end_ms,
              'queried_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        output.update(collect_pages(address,start_ms,end_ms,details['selected_volume']))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        output.update({'status':'error','reason':str(exc)[:160]})
    path.write_text(json.dumps(output, separators=(',',':')))
    return output


def summarize(sample, cache):
    all_rows = []
    for addr, d in sample.items():
        path = cache / (sha(addr)+'.json')
        result = json.loads(path.read_text()) if path.is_file() else {'status':'not_fetched'}
        status = result['status']
        if result.get('source_end') != d['end'] and status != 'not_fetched':
            status = 'stale_cache'
        row = {**d, 'status':status, 'total_volume':result.get('total_volume'),
               'fill_count':result.get('fill_count'), 'api_pages':result.get('api_pages',0 if status=='not_fetched' else 1),
               'queried_at':result.get('queried_at')}
        if status == 'complete' and d['selected_volume'] > 0:
            row['share'] = d['selected_volume'] / result['total_volume']
            row['largest_share'] = d['largest_builder_volume'] / result['total_volume']
        all_rows.append(row)

    def stats(rows):
        accepted = [r for r in rows if 'share' in r]
        counts = dict(collections.Counter(r['status'] for r in rows))
        result = {'sampled':len(rows), 'valid':len(accepted),'statuses':counts}
        if accepted:
            weights=sum(r['total_volume'] for r in accepted)
            result.update(median_selected_share=statistics.median(r['share'] for r in accepted),
                median_largest_builder_share=statistics.median(r['largest_share'] for r in accepted),
                volume_weighted_selected_share=sum(r['selected_volume'] for r in accepted)/weights,
                median_hyperliquid_total_usd=statistics.median(r['total_volume'] for r in accepted),
                total_hyperliquid_volume_usd=sum(r['total_volume'] for r in accepted),
                selected_builder_volume_usd=sum(r['selected_volume'] for r in accepted),
                observed_below_50pct=sum(r['share'] < .5 for r in accepted),
                observed_below_90pct=sum(r['share'] < .9 for r in accepted),
                over_one_within_tolerance=sum(r['share'] > 1 for r in accepted))
        return result

    matched=[r['queried_at'] for r in all_rows if r.get('queried_at')]
    return {
      'source':'HyperTracker 30d builder-wallet snapshot 2026-10-30; public Hyperliquid userFillsByTime historical execution fills',
      'api_endpoint':API, 'api_request':'Paginated userFillsByTime, startTime 30 days before source download timestamp, endTime at source download timestamp; aggregateByTime=false',
      'source_download_timezone_assumption':'UTC (downloaded strings do not specify offset)',
      'query_first_utc':min(matched) if matched else None, 'query_last_utc':max(matched) if matched else None,
      'method':'Returned trade notional is sum(px * sz) across paginated historical fills, treated as USD equivalent; spot quote conversion is not independently verified; selected volume is sum of wallet builder-routed volume over 125 eligible builder codes. Inclusive timestamp boundaries are deduplicated. Responses that remain unpageable, inverted by more than 1%, or fail are excluded.',
      'selection':'10 addresses spread across each of 10 overlapping-wallet volume deciles; 5 per single-builder decile; 25 highest-volume overlap wallets; middle-volume wallet for each of the 30 largest leaderboard codes. Duplicates queried once.',
      'privacy':'Only aggregates; addresses and individual trade observations are stored under private .cache and excluded from submission.',
      'caveats':['This is a deliberately stratified sample, not an estimate for all wallets or all company volume.',
          'Fills cover available trading across direct access and builders, without execution-builder identifiers; full exchange-history coverage is unverified.',
          'Some cached responses exceed the documented 10,000-fill history restriction; this discrepancy does not establish complete coverage.',
          'Near-snapshot source end times, UTC assumption and data vendor scope can still cause small inconsistencies.',
          '2,000 fills is a per-request limit; the script paginates by fill timestamp. The public API also documents a 10,000-most-recent-fills history restriction, so older trades may not always be recoverable. We cannot independently certify complete exchange history.',
          'Volume share does not attribute wallet-wide profit or loss to a builder.'],
      'total_api_pages_recorded':sum(r['api_pages'] for r in all_rows if r.get('api_pages')),
      'overall':stats(all_rows),
      'overlapping_wallets':stats([r for r in all_rows if r['builder_count']>1]),
      'single_selected_builder_wallets':stats([r for r in all_rows if r['builder_count']==1]),
      'high_volume_overlap':stats([r for r in all_rows if 'high_volume_overlap' in r['strata']]),
      'top30_builder_median_wallets':stats([r for r in all_rows if 'top30_builder_median_wallet' in r['strata']]),
      'volume_deciles_overlapping':[{'decile':k, **stats([r for r in all_rows if 'overlap_decile' in r['strata'] and r['overlap_volume_decile']==k])} for k in range(1,11)]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path,default=ROOT/'datasets')
    parser.add_argument('--fetch',action='store_true',help='Retrieve and paginate historical Hyperliquid fills for a deterministic sample')
    parser.add_argument('--refresh',action='store_true',help='Replace cached results')
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    sample=choose_sample(args.data_dir)
    cache=ROOT/'.cache'/'historical_volume';cache.mkdir(parents=True,exist_ok=True)
    if args.fetch:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(4,args.workers))) as pool:
            jobs={pool.submit(fetch_one,addr,details,cache,args.refresh):addr for addr,details in sample.items()}
            for i,fut in enumerate(concurrent.futures.as_completed(jobs),1):
                output=fut.result()
                if i % 25 == 0 or i == len(jobs):
                    print(f'Queried {i}/{len(jobs)} historical wallets; newest: {output["status"]}',flush=True)
    report=summarize(sample,cache)
    (ROOT/'volume_comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Sample:',report['overall']['sampled'],'complete:',report['overall']['valid'], 'status counts:',report['overall']['statuses'])


if __name__=='__main__':main()
