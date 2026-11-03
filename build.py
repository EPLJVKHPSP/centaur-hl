#!/usr/bin/env python3
"""Reproducible offline HyperTracker company analysis, using only Python stdlib."""
import argparse, collections, csv, datetime as dt, hashlib, html, json, math, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEFAULT_DATASET_DIR='datasets'
TYPES=('Wallet','Trading app','Terminal & analytics','Automation & AI','Social trading')
FORM_FACTORS=('mobile-first','desktop/web','both','Telegram','unknown')
PRODUCT_TAGS=('Bots','Agents','Alpha discovery','Community','Copy trading','Trenches (memecoins)','Scalping','Pro','Rewards','Gamified')
LABEL_FIELDS=('rank','company','type','form_factor','product_tags','company_id','builder_codes',
              'type_confidence','type_source_url','type_evidence',
              'form_factor_confidence','form_factor_source_url','form_factor_evidence','tag_evidence','tag_review')

def default_data_dir(project_dir=ROOT):
    """Locate the unpacked snapshot inside this project."""
    data_dir=project_dir/DEFAULT_DATASET_DIR
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Missing dataset directory: {data_dir}. Place the data files under datasets/ or use --data-dir.")
    return data_dir

def num(x):
    try:
        if x is None or isinstance(x,bool):return None
        v=float(x)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):return None

def div(x,y):return x/y if y else None

def metric(rows,volume):
    valid=[w for w in rows if w['pnl'] is not None]; nonzero=[w for w in valid if w['pnl']!=0]; pos=[w for w in nonzero if w['pnl']>0]
    obs=sum(w['volume'] for w in rows); eligible=sum(w['volume'] for w in nonzero)
    absvals=sorted((abs(w['pnl']) for w in valid),reverse=True)
    pnl=sum(w['pnl'] for w in valid)
    return dict(wallets=len(rows),valid_pnl_wallets=len(valid),nonzero_pnl_wallets=len(nonzero),winning_wallets=len(pos),
       missing_pnl_wallets=len(rows)-len(valid),zero_pnl_wallets=len(valid)-len(nonzero),
       pct_profitable=div(len(pos),len(nonzero)),pct_profitable_by_volume=div(sum(w['volume'] for w in pos),obs),
       pct_profitable_by_nonzero_volume=div(sum(w['volume'] for w in pos),eligible),
       missing_pnl_volume_share=div(sum(w['volume'] for w in rows if w['pnl'] is None),obs),
       excluded_volume_share=div(obs-eligible,obs),net_pnl=pnl,
       gross_positive_wallet_pnl=sum(w['pnl'] for w in pos),gross_negative_wallet_pnl=sum(w['pnl'] for w in valid if w['pnl']<0),
       median_pnl=statistics.median(w['pnl'] for w in valid) if valid else None,
       pnl_per_dollar=div(pnl,volume),top10_concentration=div(sum(absvals[:10]),sum(absvals)),
       routed_wallet_volume=obs,eligible_wallet_volume=eligible,positive_wallet_volume=sum(w['volume'] for w in pos))

def exclusion(rows,volume,n):
    valid=sorted((w for w in rows if w['pnl'] is not None),key=lambda w:(-abs(w['pnl']),w['address']))
    if len(valid)<=n:return None
    cut={r['address'] for r in valid[:n]}
    denominator=max(0,volume-sum(w['volume'] for w in valid[:n]))
    return metric([r for r in rows if r['address'] not in cut],denominator)

def key(info,address):
    uid=str(info.get('xUserId') or (info.get('xUser') or {}).get('xUserId') or '').strip().lower()
    return 'x:'+uid if uid else 'builder:'+address.lower()

def digest(wallet):return hashlib.sha256(wallet.encode()).hexdigest()[:14]

def group(builders,profiles):
    ans=collections.defaultdict(list)
    for b in builders:ans[key(profiles[b['address'].lower()]['info'],b['address'])].append(b)
    return ans

def commercial_evidence(wallets, builder_companies, companies, snapshot):
    """Aggregate three client-facing findings from wallet-level source records."""
    winners=[];multi_company_wallets=0;multi_company_volume=0;multi_company_fees=0
    routed_volume=0;wallet_fees=0;fees_by_pnl=collections.defaultdict(float)
    fees_by_closed_pnl=collections.defaultdict(float);multi_company_counts=collections.Counter()
    pnl_conflicts=0;closed_pnl_conflicts=0

    def outcome(value):
        if value is None:return 'missing'
        if value>0:return 'positive'
        if value<0:return 'negative'
        return 'zero'

    for observations in wallets.values():
        values={o['pnl'] for o in observations if o['pnl'] is not None}
        closed_values={o['closed_pnl'] for o in observations if o['closed_pnl'] is not None}
        if len(values)>1:pnl_conflicts+=1
        if len(closed_values)>1:closed_pnl_conflicts+=1
        pnl=next(iter(values)) if len(values)==1 else None
        total_volume=sum(o['volume'] for o in observations)
        total_fees=sum(o['fee'] for o in observations)
        routed_volume+=total_volume;wallet_fees+=total_fees
        fees_by_pnl[outcome(pnl)]+=total_fees
        for observation in observations:
            fees_by_closed_pnl[outcome(observation['closed_pnl'])]+=observation['fee']
        if pnl is not None and pnl>0:winners.append(pnl)
        count=len({builder_companies[o['builder']] for o in observations})
        if count>1:
            multi_company_wallets+=1;multi_company_volume+=total_volume;multi_company_fees+=total_fees
            multi_company_counts[count]+=1

    gross_gains=sum(winners)
    top100_gains=sum(sorted(winners,reverse=True)[:100])
    evidence=dict(
        snapshot=snapshot,period='30d',selected_companies=len(companies),
        selection='Named builder codes with more than $1m 30-day volume, grouped by shared X account',
        pnl_metric='Account-wide perpPnl for each unique wallet (not PnL attributable to builder-routed trades)',
        unique_wallets=len(wallets),winning_accounts=len(winners),
        gross_positive_wallet_pnl_usd=gross_gains,
        top100_positive_wallet_pnl_usd=top100_gains,
        top100_share_gross_gains=div(top100_gains,gross_gains),
        multi_company_wallets=multi_company_wallets,
        multi_company_wallet_share=div(multi_company_wallets,len(wallets)),
        multi_company_routed_volume_usd=multi_company_volume,
        observed_routed_volume_usd=routed_volume,
        multi_company_volume_share=div(multi_company_volume,routed_volume),
        multi_company_fee_share=div(multi_company_fees,wallet_fees),
        multi_company_distribution=dict(sorted(multi_company_counts.items())),
        wallet_fee_sum=wallet_fees,
        losing_wallet_fees_usd=fees_by_pnl['negative'],
        losing_wallet_fee_share=div(fees_by_pnl['negative'],wallet_fees),
        winning_wallet_fee_share=div(fees_by_pnl['positive'],wallet_fees),
        zero_or_missing_wallet_fee_share=div(fees_by_pnl['zero']+fees_by_pnl['missing'],wallet_fees),
        losing_wallet_fee_share_by_closed_pnl=div(fees_by_closed_pnl['negative'],wallet_fees),
        closed_pnl_comparison='Builder-wallet record-level closedPnl classifications, fee weighted; the same wallet can have different closedPnl values across builders',
        conflicting_wallet_pnls=pnl_conflicts,
        conflicting_closed_pnl_wallets=closed_pnl_conflicts,
        limitations=[
            'Top-100 gains are account-wide, deduplicated per wallet; this does not measure persistent profitability.',
            'Multi-company means distinct grouped companies, not merely several builder codes. The data does not reveal why traders chose each product.',
            'Losing wallets have negative 30-day account perpPnl. The realized closedPnl comparison uses each builder-wallet record because closedPnl can differ across builders.',
            'One 30-day wallet snapshot cannot determine whether losing users subsequently leave or keep paying fees.'
        ])
    return evidence

def labels_load(path=None):
    """Read one company per row, preserving evidence for every classification."""
    ans={}
    seen_ranks=set()
    def source(dimension,label,url,confidence,evidence):
        if not isinstance(url,str) or not url.startswith(('https://','http://')) or not isinstance(evidence,str) or not evidence.strip() or confidence not in ('High','Medium','Low'):
            raise ValueError(f'Missing or invalid source for {dimension}: {label}')
        return dict(dimension=dimension,label=label,source=url,confidence=confidence,evidence=evidence)
    with (Path(path) if path is not None else ROOT/'labels.csv').open(newline='',encoding='utf8') as fh:
        reader=csv.DictReader(fh)
        if not reader.fieldnames or set(reader.fieldnames)!=set(LABEL_FIELDS):
            raise ValueError('labels.csv must contain the documented company-level columns')
        for row in reader:
            cid=row['company_id'];typ=row['type'];factor=row['form_factor']
            if not cid or cid in ans or not row['company'].strip() or not row['builder_codes'].strip():
                raise ValueError('Missing or duplicate company identity: '+str(cid))
            try:rank=int(row['rank'])
            except (TypeError,ValueError):raise ValueError('Invalid rank: '+str(row['rank'])) from None
            if rank<1 or rank>30 or rank in seen_ranks:raise ValueError('Invalid or duplicate top-30 rank: '+str(rank))
            seen_ranks.add(rank)
            if typ not in TYPES or factor not in FORM_FACTORS:
                raise ValueError('Invalid type or form factor for '+cid)
            tags=row['product_tags'].split(' | ') if row['product_tags'] else []
            if any(t not in PRODUCT_TAGS for t in tags) or len(tags)!=len(set(tags)):
                raise ValueError('Invalid or duplicate product tag for '+cid)
            try:tag_sources=json.loads(row['tag_evidence'])
            except (TypeError,ValueError) as exc:raise ValueError('Invalid tag evidence JSON for '+cid) from exc
            if not isinstance(tag_sources,list) or len(tag_sources)!=len(tags):
                raise ValueError('Product tags and tag evidence do not match for '+cid)
            sources=[source('type',typ,row['type_source_url'],row['type_confidence'],row['type_evidence']),
                     source('form_factor',factor,row['form_factor_source_url'],row['form_factor_confidence'],row['form_factor_evidence'])]
            for label,detail in zip(tags,tag_sources):
                if not isinstance(detail,dict) or set(detail)!= {'label','source','confidence','evidence'} or detail['label']!=label:
                    raise ValueError('Tag evidence label mismatch for '+cid)
                sources.append(source('product_tag',label,detail['source'],detail['confidence'],detail['evidence']))
            try:reviews=json.loads(row['tag_review'])
            except (TypeError,ValueError) as exc:raise ValueError('Invalid tag review JSON for '+cid) from exc
            if not isinstance(reviews,list) or len(reviews)!=len(PRODUCT_TAGS) or [r.get('label') if isinstance(r,dict) else None for r in reviews]!=list(PRODUCT_TAGS):
                raise ValueError('Expected one review for each permitted tag for '+cid)
            for r in reviews:
                if set(r)!= {'label','status','source_url','note'} or r['status'] not in ('Verified','No qualifying feature found','Insufficient evidence') or not r['source_url'].startswith(('https://','http://')) or not r['note'].strip():
                    raise ValueError('Invalid tag review status or evidence for '+cid)
                if (r['status']=='Verified')!=(r['label'] in tags):
                    raise ValueError('Tag review and assigned tags disagree for '+cid+': '+r['label'])
            ans[cid]=dict(type=typ,confidence=row['type_confidence'],forms=[factor],tags=tags,sources=sources)
    return ans

def analyze(data_dir):
    data_dir=Path(data_dir)
    leader=json.loads((data_dir/'leaderboards/list_30d.json').read_text())['builders']
    builders=[b for b in leader if isinstance(b.get('refCode'),str) and b['refCode'].strip() and (num(b.get('volume')) or 0)>1e6]
    if len(set(b['address'].lower() for b in builders))!=len(builders):raise ValueError('Duplicate address in leaderboard')
    profiles={};wallets={}
    for b in builders:
        address=b['address'].lower();profiles[address]=json.loads((data_dir/'profiles'/f'{address}.json').read_text())
        data=json.loads((data_dir/'wallets'/f'{address}_30d.json').read_text())
        if data.get('builder','').lower()!=address or data['period']!='30d':raise ValueError('Wallet file identity mismatch '+address)
        wallets[address]=[dict(zip(data['columns'],r)) for r in data['rows']]
    pack_info=json.loads((data_dir/'pack_info.json').read_text())
    platform_volumes=[num(p.get('hyperliquidVolume24h')) for p in profiles.values()]
    platform_volumes=[v for v in platform_volumes if v is not None]
    lookup=labels_load(); labeled_ids=set(lookup); all_wallet=collections.defaultdict(list); builder_stats={}; same_builder_duplicate=0;missing=0;zero=0;total_pnl_diff=0
    for b in builders:
        addr=b['address'].lower();seen=set();vol=fees=0
        for w in wallets[addr]:
            wid=str(w['address']).lower();pnl=num(w.get('perpPnl'));pv=num(w.get('pnl'));v=num(w.get('volume')) or 0
            if wid in seen:same_builder_duplicate+=1
            seen.add(wid);missing+=pnl is None;zero+=pnl==0
            if pnl is not None and pv is not None and abs(pv-pnl)>.01:total_pnl_diff+=1
            vol+=v;fees+=num(w.get('builderFee')) or 0
            all_wallet[wid].append(dict(builder=addr,pnl=pnl,closed_pnl=num(w.get('closedPnl')),
                                        volume=v,fee=num(w.get('builderFee')) or 0))
        builder_stats[addr]=dict(code=b['refCode'],leaderboard_volume=num(b['volume']),wallet_volume=vol,leaderboard_users=b['users'],wallet_rows=len(wallets[addr]),leaderboard_revenue=num(b['revenue']),wallet_fees=fees,volume_diff_pct=div(vol-num(b['volume']),num(b['volume'])),fees_diff_pct=div(fees-num(b['revenue']),num(b['revenue'])))
    results=[];company_pnl_conflicts=0
    for cid,members in group(builders,profiles).items():
        members=sorted(members,key=lambda b:b['address']); addresses=[b['address'].lower() for b in members]
        parts=collections.defaultdict(list)
        for addr in addresses:
            for w in wallets[addr]:parts[str(w['address']).lower()].append(dict(address=str(w['address']).lower(),pnl=num(w.get('perpPnl')),volume=num(w.get('volume')) or 0))
        dedup=[]
        for addr,entries in parts.items():
            pvals=[e['pnl'] for e in entries if e['pnl'] is not None]
            if len(set(pvals))>1:company_pnl_conflicts+=1
            pnl=max(set(pvals),key=lambda v:(pvals.count(v),max(e['volume'] for e in entries if e['pnl']==v),-v)) if pvals else None
            dedup.append(dict(address=addr,pnl=pnl,volume=sum(e['volume'] for e in entries)))
        volume=sum(num(m['volume']) for m in members);revenue=sum(num(m['revenue']) for m in members)
        lead=max(members,key=lambda m:num(m['volume'])); label=lookup.get(cid,dict(type='Unclassified',confidence='Unverified',forms=[],tags=[],sources=[]));stats=metric(dedup,volume)
        delta=sum(builder_stats[a]['wallet_volume'] for a in addresses)-volume
        fee_delta=sum(builder_stats[a]['wallet_fees'] for a in addresses)-revenue
        results.append(dict(company_id=cid,name=lead['refCode'],builder_codes=[m['refCode'] for m in members],builder_addresses=addresses,
           type=label['type'],confidence=label['confidence'],forms=label['forms'],tags=label['tags'],sources=label['sources'],
           volume=volume,revenue=revenue,revenue_bps=div(revenue,volume)*10000,revenue_vs_abs_net_pnl=div(revenue,abs(stats['net_pnl'])),
           wallet_volume_delta_pct=div(delta,volume),wallet_volume_discrepancy=delta,wallet_fee_delta_pct=div(fee_delta,revenue),wallet_fee_discrepancy=fee_delta,leaderboard_users_sum=sum(m['users'] for m in members),
           **stats,without_top1=exclusion(dedup,volume,1),without_top10=exclusion(dedup,volume,10)))
    results.sort(key=lambda c:-c['volume'])
    for i,c in enumerate(results,1):c['rank']=i
    researched={c['company_id'] for c in results[:30]}
    if labeled_ids!=researched:
        raise ValueError(f'labels.csv must cover exactly the top 30 companies; missing={researched-labeled_ids}, extra={labeled_ids-researched}')
    overlap={wid:obs for wid,obs in all_wallet.items() if len(set(r['builder'] for r in obs))>1}
    ordered=sorted(overlap.items(),key=lambda w:(-max(abs(x['pnl'] or 0) for x in w[1]),-sum(x['volume'] for x in w[1])))
    top=ordered[:30];largest_shares=[]
    for wid,obs in overlap.items():
        tot=sum(x['volume'] for x in obs)
        if tot:largest_shares.append(max(x['volume'] for x in obs)/tot)
    # A wallet's perpPnl repeats across builder files. Use it once per unique wallet
    # when contrasting account-wide gains/losses with attributable builder fees.
    unique_pnls=[];unique_pnl_conflicts=0
    for obs in all_wallet.values():
        values={r['pnl'] for r in obs if r['pnl'] is not None}
        if len(values)>1:unique_pnl_conflicts+=1
        elif values:unique_pnls.append(next(iter(values)))
    validation=dict(pack_info=pack_info,built_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),source_leaderboard_builders=len(leader),selected_builders=len(builders),selected_companies=len(results),
       platform_volume_24h=dict(source='profiles/*.json: hyperliquidVolume24h',scope='Entire Hyperliquid platform (repeated in each builder profile)',period='24h',
          profiles_checked=len(profiles),profiles_with_value=len(platform_volumes),min_usd=min(platform_volumes) if platform_volumes else None,
          max_usd=max(platform_volumes) if platform_volumes else None,
          limitation='This is not an individual wallet 30-day volume; it cannot be used as the Q2 denominator and should not be summed across profiles.'),
       selection='Non-empty public refCode and strictly over $1m 30-day leaderboard volume',grouping='xUserId normalized to lowercase, else builder address',
       merged_codes=[dict(company_id=c['company_id'],company=c['name'],builder_codes=c['builder_codes'],addresses=c['builder_addresses']) for c in results if len(c['builder_codes'])>1],
       total_leaderboard_volume=sum(c['volume'] for c in results),total_builder_revenue=sum(c['revenue'] for c in results),total_wallet_rows=sum(x['wallet_rows'] for x in builder_stats.values()),
       unique_wallets_all_builders=len(all_wallet),same_builder_duplicate_wallet_rows=same_builder_duplicate,missing_perp_pnl_rows=missing,zero_perp_pnl_rows=zero,total_pnl_differs_from_perp_pnl_rows=total_pnl_diff,
       unique_wallets_with_valid_pnl=len(unique_pnls),unique_wallets_with_conflicting_pnl=unique_pnl_conflicts,
       unique_wallets_positive_pnl=sum(p>0 for p in unique_pnls),unique_wallets_negative_pnl=sum(p<0 for p in unique_pnls),unique_wallets_zero_pnl=sum(p==0 for p in unique_pnls),
       unique_wallets_gross_positive_pnl=sum(p for p in unique_pnls if p>0),unique_wallets_gross_negative_pnl=sum(p for p in unique_pnls if p<0),
       unique_wallets_net_pnl=sum(unique_pnls),unique_wallet_median_pnl=statistics.median(unique_pnls) if unique_pnls else None,
       within_company_duplicate_pnl_conflicts=company_pnl_conflicts,overlapping_wallets_across_builders=len(overlap),
       overlap_identical_valid_pnl_count=sum(len(set(r['pnl'] for r in obs if r['pnl'] is not None))==1 for obs in overlap.values()),
       overlap_valid_pnl_conflicts=sum(len(set(r['pnl'] for r in obs if r['pnl'] is not None))>1 for obs in overlap.values()),
       median_max_selected_builder_share=statistics.median(largest_shares) if largest_shares else None,
       attribution_note='Builder volume / volume across selected builders is an upper-bound proxy; direct and excluded-builder volume is unobserved; full-account perpPnl is not attributable to a builder.',
       per_builder_reconciliation=list(builder_stats.values()),
       company_volume_discrepancies_over_1pct=[dict(name=c['name'],pct=c['wallet_volume_delta_pct']) for c in results if abs(c['wallet_volume_delta_pct'] or 0)>.01],
       company_fee_discrepancies_over_1pct=[dict(name=c['name'],pct=c['wallet_fee_delta_pct']) for c in results if abs(c['wallet_fee_delta_pct'] or 0)>.01],
       wallet_count_discrepancies=[dict(code=s['code'],leaderboard=s['leaderboard_users'],wallet_rows=s['wallet_rows']) for s in builder_stats.values() if s['leaderboard_users']!=s['wallet_rows']],
       classification_top30=sum(c['type'] in TYPES for c in results[:30]),top30_unclassified=[c['name'] for c in results[:30] if c['type']=='Unclassified'],
       limitations=['Account-wide perpPnl appears identically across builder files','Cross-company wallets make summed company PnL non-unique','Leaderboard and wallet files have different snapshot/aggregation timing','Wallet-level volume covers only observed selected builders','Product type does not demonstrate causation','Top-10 exclusion adjusts volume using routed wallet volume, an approximation'])
    builder_companies={b['address'].lower():cid for cid,members in group(builders,profiles).items() for b in members}
    validation['commercial_evidence']=commercial_evidence(all_wallet,builder_companies,results,pack_info.get('data_as_of'))
    return results,validation,top

def types_aggregate(rows):
    groups=collections.defaultdict(list)
    for c in rows:
        if c['type'] in TYPES:groups[c['type']].append(c)
    out=[]
    for typ,items in sorted(groups.items()):
        vol=sum(x['volume'] for x in items);fees=sum(x['revenue'] for x in items);pnl=sum(x['net_pnl'] for x in items);eligible=sum(x['eligible_wallet_volume'] for x in items);active=sum(x['nonzero_pnl_wallets'] for x in items);observed=sum(x['routed_wallet_volume'] for x in items)
        out.append(dict(type=typ,companies=len(items),wallet_observations=sum(x['wallets'] for x in items),nonzero_pnl_wallet_observations=active,volume=vol,revenue=fees,net_pnl=pnl,
          winning_wallet_observations=sum(x['winning_wallets'] for x in items),
          gross_positive_wallet_pnl=sum(x['gross_positive_wallet_pnl'] for x in items),gross_negative_wallet_pnl=sum(x['gross_negative_wallet_pnl'] for x in items),
          pct_profitable=div(sum(x['winning_wallets'] for x in items),active),pct_profitable_by_volume=div(sum(x['positive_wallet_volume'] for x in items),observed),
          pct_profitable_by_nonzero_volume=div(sum(x['positive_wallet_volume'] for x in items),eligible),
          pnl_per_dollar=div(pnl,vol),revenue_bps=div(fees,vol)*10000 if vol else None))
    return out

def money(n):return ('−' if n<0 else '')+'$'+f'{abs(n):,.0f}'
def pct(n):return 'n/a' if n is None else f'{n:.1%}'

def sign_flips(rows, field):
    eligible = [c for c in rows if c[field] is not None]
    return sum(c['net_pnl'] * c[field]['net_pnl'] < 0 for c in eligible), len(eligible)


def insights(rows, val):
    flips, count = sign_flips(rows, 'without_top1')
    concentration = statistics.median(c['top10_concentration'] for c in rows if c['top10_concentration'] is not None)
    return [
        dict(title='The same wallet profit appears under several builders',
             stat=f"{val['overlapping_wallets_across_builders']:,} shared wallets",
             body='Every overlapping wallet has identical perps PnL across its builder records. Adding company totals counts some account results more than once.',
             caveat='Wallet PnL covers the account; it does not identify which builder routed the profitable trades.'),
        dict(title='One wallet can change a company from profit to loss',
             stat=f'{flips} of {count} signs reverse',
             body=f'Removing the largest absolute-PnL wallet reverses these company totals. The median company has {concentration:.1%} of absolute PnL in its ten largest wallets.',
             caveat='Use median wallet PnL and win rate alongside these stress tests. Small samples remain fragile.'),
        dict(title='Builders collect fees while observed accounts lose money',
             stat=f"${val['total_builder_revenue']/1e6:.2f}m in fees",
             body=f"Unique observed wallets gained ${val['unique_wallets_gross_positive_pnl']/1e6:.2f}m and lost ${abs(val['unique_wallets_gross_negative_pnl'])/1e6:.2f}m: ${abs(val['unique_wallets_net_pnl'])/1e6:.2f}m net losses across their accounts.",
             caveat='Fees are builder-specific; account losses include other routes. This comparison does not establish that builders caused the losses.')]


def findings(rows, v, types, ins):
    by_count = max(types, key=lambda t:t['winning_wallet_observations'])
    by_rate = max(types, key=lambda t:t['pct_profitable'])
    by_volume = max(types, key=lambda t:t['pct_profitable_by_volume'])
    by_pnl = max(types, key=lambda t:t['pnl_per_dollar'])
    f10, n10 = sign_flips(rows, 'without_top10')
    audit = v.get('volume_comparison', {})
    overall, overlap = audit.get('overall', {}), audit.get('overlapping_wallets', {})
    historical = (f"The paginated historical API sample returned {overall['valid']}/{overall['sampled']} usable wallet comparisons; "
                  f"{overlap['valid']}/{overlap['sampled']} multi-builder wallets were usable. "
                  f"Their median largest-builder share was {overlap['median_largest_builder_share']:.2%} of returned exchange fill volume; "
                  f"the median combined selected-builder share was {overlap['median_selected_share']:.2%} "
                  f"and the pooled volume share was {overlap['volume_weighted_selected_share']:.2%}. "
                  'The 2,000-fill response cap was handled by pagination.'
                  if overall.get('valid') and overlap.get('valid') else 'The historical API comparison is unavailable.')
    ins = insights(rows, v)
    blocks = ''.join(f'<section class="finding"><h2>{i}. {html.escape(x["title"])}</h2><p><strong>{html.escape(x["stat"])}</strong>. {html.escape(x["body"])}</p><p class="caveat">{html.escape(x["caveat"])}</p></section>' for i,x in enumerate(ins,1))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hyperliquid builder profitability - findings</title><style>
@page{{size:A4;margin:15mm}}*{{box-sizing:border-box}}body{{margin:0;background:#edf2ee;color:#19322f;font:13px/1.42 Arial,sans-serif}}main{{max-width:210mm;margin:24px auto;background:white;padding:15mm}}header{{border-bottom:2px solid #087c6d;padding-bottom:10px}}h1{{font-size:25px;line-height:1.15;margin:5px 0 8px}}.meta,.caveat,footer{{color:#526b65}}.meta{{font-size:11px}}h2{{font-size:15px;margin:14px 0 5px}}p{{margin:5px 0}}strong{{color:#076c60}}.caveat{{font-size:11.5px}}.finding{{break-inside:avoid}}.distrust{{border-top:1px solid #baccc5;margin-top:13px;padding-top:1px}}ul{{padding-left:18px;margin:6px 0}}li{{margin:5px 0}}footer{{border-top:1px solid #baccc5;padding-top:8px;margin-top:13px;font-size:10px}}a{{color:#076c60}}@media(max-width:600px){{main{{padding:22px;margin:0}}}}@media print{{body{{background:white;font-size:11.5px}}main{{margin:0;padding:0;max-width:none}}h2{{margin-top:11px;font-size:14px}}.caveat{{font-size:10.5px}}}}
</style></head><body><main><header><div class="meta">30 October 2026 snapshot | 30-day window | {v['selected_builders']} builder codes / {v['selected_companies']} companies</div><h1>Builder fees and trader profitability</h1></header>{blocks}
<h2>Which types have the most profitable traders?</h2><p>{html.escape(by_count['type'])} has the most profitable wallet-company observations ({by_count['winning_wallet_observations']:,}). {html.escape(by_rate['type'])} leads by wallet rate ({by_rate['pct_profitable']:.2%}); {html.escape(by_volume['type'])} leads by profitable share of all observed routed volume ({by_volume['pct_profitable_by_volume']:.2%}). {html.escape(by_pnl['type'])} also has the least-negative account PnL per routed dollar ({by_pnl['pnl_per_dollar']:.4%}). Every type has a negative aggregate account PnL. These comparisons cover the 30 classified companies.</p>
<div class="distrust"><h2>What to distrust</h2><ul>
<li><b>Attribution:</b> {html.escape(historical)} Coverage is unverified and these ratios cannot allocate PnL. Deduplicate wallets for account totals; builder attribution requires matched trade routing and PnL.</li>
<li><b>Whale-driven totals:</b> removing ten wallets reverses {f10}/{n10} eligible company signs. Prefer median wallet PnL and win rate, with sample size and both exclusion tests.</li>
<li><b>Source agreement:</b> Atomic wallet volume is 10.46% below its leaderboard total; Outcome wallet fees are 5.65% above reported revenue. There are {v['missing_perp_pnl_rows']} missing and {v['zero_perp_pnl_rows']:,} zero-PnL rows. Zero and missing PnL are excluded from wallet win rates, but their volume stays in the volume-share denominator; missing PnL is not assumed to be a loss.</li>
<li><b>Product claims and causation:</b> labels have linked evidence and confidence; four ambiguous types retain user decisions. Products, trader selection and market conditions differ. No result shows that a product type causes profits.</li></ul></div>
<footer>Source: supplied HyperTracker data; <a href="labels.csv">label evidence</a>; <a href="RESEARCH.md">methods and four answers</a>; <a href="validation.json">data checks</a>. Perps PnL only; volume and fees use leaderboard totals. This private assignment report contains no individual wallet records.</footer></main></body></html>'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,help='Directory containing the dataset files (default: ./datasets)');opts=ap.parse_args()
    try:data_dir=opts.data_dir if opts.data_dir is not None else default_data_dir()
    except FileNotFoundError as exc:ap.error(str(exc))
    if not data_dir.is_dir():ap.error(f'Dataset directory not found: {data_dir}')
    print(f'Using datasets: {data_dir}')
    rows,val,_=analyze(data_dir);types=types_aggregate(rows)
    audit_path=ROOT/'volume_comparison.json'
    val['volume_comparison']=json.loads(audit_path.read_text()) if audit_path.is_file() else {'status':'Not run. Execute python3 volume_audit.py --fetch first.'}
    ins=insights(rows,val)
    payload=json.dumps(dict(companies=rows,types=types,insights=ins,validation={k:val[k] for k in ('selected_builders','selected_companies','total_leaderboard_volume','total_builder_revenue','overlapping_wallets_across_builders','overlap_identical_valid_pnl_count','missing_perp_pnl_rows','zero_perp_pnl_rows','classification_top30','volume_comparison','platform_volume_24h')}),ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    template=(ROOT/'dashboard_template.html').read_text()
    (ROOT/'dashboard.html').write_text(template.replace('/*__DATA__*/','const DATA = '+payload+';'))
    (ROOT/'findings.html').write_text(findings(rows,val,types,ins))
    (ROOT/'validation.json').write_text(json.dumps(val,indent=2,ensure_ascii=False,allow_nan=False))
    (ROOT/'commercial_evidence.json').write_text(json.dumps(val['commercial_evidence'],indent=2,ensure_ascii=False,allow_nan=False))
    fields=['rank','company_id','name','builder_codes','type','confidence','form_factor','product_tags','volume','wallets','valid_pnl_wallets','nonzero_pnl_wallets','winning_wallets','missing_pnl_wallets','zero_pnl_wallets','pct_profitable','pct_profitable_by_volume','pct_profitable_by_nonzero_volume','missing_pnl_volume_share','excluded_volume_share','gross_positive_wallet_pnl','gross_negative_wallet_pnl','net_pnl','median_pnl','pnl_per_dollar','top10_concentration','revenue','revenue_bps','revenue_vs_abs_net_pnl','wallet_volume_delta_pct','wallet_fee_delta_pct','routed_wallet_volume']
    def csv_value(company,field):
        if field=='builder_codes':return ' | '.join(company['builder_codes'])
        if field=='form_factor':return company['forms'][0] if company['forms'] else ''
        if field=='product_tags':return ' | '.join(company['tags'])
        return company[field]
    with (ROOT/'company_metrics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in rows:w.writerow({k:csv_value(c,k) for k in fields})
    print(f"Built {val['selected_builders']} codes in {len(rows)} companies, {val['classification_top30']} classified in top 30")

if __name__=='__main__':main()
