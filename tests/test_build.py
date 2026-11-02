import unittest,sys,json,collections,tempfile,csv,statistics,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import metric,exclusion,key,group,analyze,types_aggregate,findings,default_data_dir,DEFAULT_DATASET_DIR,ROOT,labels_load,sign_flips,TYPES,FORM_FACTORS,PRODUCT_TAGS,LABEL_FIELDS
from volume_audit import audit_fills, choose_sample, collect_pages, summarize, sha, parse_date
DATA=ROOT/DEFAULT_DATASET_DIR

class CalculationTests(unittest.TestCase):
 def test_labels_csv_has_separate_readable_columns(self):
  with (ROOT/'labels.csv').open(newline='',encoding='utf-8') as fh:
   reader=csv.DictReader(fh);rows=list(reader)
  self.assertEqual(tuple(reader.fieldnames),LABEL_FIELDS)
  self.assertEqual(len(rows),30)
  self.assertEqual([int(row['rank']) for row in rows],list(range(1,31)))
  for row in rows:
   self.assertIn(row['type'],TYPES)
   self.assertIn(row['form_factor'],FORM_FACTORS)
   self.assertEqual([x['label'] for x in json.loads(row['tag_evidence'])],
                    row['product_tags'].split(' | ') if row['product_tags'] else [])
   review=json.loads(row['tag_review'])
   self.assertEqual([x['label'] for x in review],list(PRODUCT_TAGS))
   self.assertEqual({x['label'] for x in review if x['status']=='Verified'},
                    set(row['product_tags'].split(' | ')) if row['product_tags'] else set())
 def test_decile_summary_uses_volume_membership_not_address_order(self):
  with tempfile.TemporaryDirectory() as d:
   cache=Path(d);sample={}
   for address,decile,observed in [('a',10,900),('z',1,100)]:
    sample[address]=dict(selected_volume=observed,largest_builder_volume=observed,builder_count=2,
                         end='2026-10-30',strata=['overlap_decile'],overlap_volume_decile=decile)
    (cache/(sha(address)+'.json')).write_text(json.dumps(dict(status='complete',source_end='2026-10-30',total_volume=1000)))
   result=summarize(sample,cache)['volume_deciles_overlapping']
   self.assertEqual(result[0]['median_selected_share'],.1)
   self.assertEqual(result[9]['median_selected_share'],.9)
   self.assertEqual(sum(x['sampled'] for x in result),2)

 def test_zero_after_exclusion_is_not_a_sign_reversal(self):
  companies=[{'net_pnl':10,'without_top10':{'net_pnl':0}},
             {'net_pnl':10,'without_top10':{'net_pnl':-1}},
             {'net_pnl':-10,'without_top10':{'net_pnl':1}},
             {'net_pnl':0,'without_top10':{'net_pnl':1}}]
  self.assertEqual(sign_flips(companies,'without_top10'),(2,4))

 def test_timezone_offset_is_respected(self):
  self.assertEqual(parse_date('2026-10-30T12:00:00+02:00').hour,10)
  self.assertEqual(parse_date('2026-10-30T12:00:00').hour,12)

 def test_historical_pagination_deduplicates_inclusive_timestamp(self):
  # The next API call replays one fill at the previous page's last ms.
  page1=[{'time':100+i,'tid':i,'oid':i,'coin':'BTC','px':'10','sz':'1'} for i in range(2000)]
  page2=[page1[-1],{'time':2100,'tid':2000,'oid':2000,'coin':'BTC','px':'10','sz':'2'}]
  calls=[]
  def fake(request):
   calls.append(request['startTime'])
   return page1 if len(calls)==1 else page2
  outcome=collect_pages('unused',100,2500,100,page_request=fake)
  self.assertEqual(calls,[100,2099])
  self.assertEqual(outcome['status'],'complete')
  self.assertEqual((outcome['api_pages'],outcome['fill_count'],outcome['total_volume']), (2,2001,20020))

 def test_historical_pagination_flags_unpageable_millisecond(self):
  pages=lambda _: [{'time':100,'tid':i,'oid':i,'px':'1','sz':'1'} for i in range(2000)]
  response=collect_pages('unused',100,1000,50,page_request=pages)
  self.assertEqual(response['status'],'timestamp_limit')

 def test_historical_fill_volume_rejects_capped_and_inverted_results(self):
  fills=[{'px':'100','sz':'2'},{'px':'50','sz':'2'}]
  result=audit_fills(fills,250)
  self.assertEqual(result['status'],'complete')
  self.assertEqual(result['total_volume'],300)
  self.assertEqual(audit_fills(fills,310)['status'],'inconsistent')
  self.assertEqual(audit_fills(fills*1000,250)['status'],'capped')
  self.assertEqual(audit_fills([],50)['status'],'zero_total')
  self.assertEqual(audit_fills([{'px':'x','sz':'2'}],20)['status'],'error')
 def test_default_dataset_directory_and_missing_error(self):
  with tempfile.TemporaryDirectory() as temp:
   parent=Path(temp);project=parent/'project';project.mkdir()
   with self.assertRaises(FileNotFoundError):default_data_dir(project)
   (parent/DEFAULT_DATASET_DIR).mkdir()
   with self.assertRaises(FileNotFoundError):default_data_dir(project)
   project_data=project/DEFAULT_DATASET_DIR;project_data.mkdir()
   self.assertEqual(default_data_dir(project),project_data)
 def test_zero_and_missing_are_different(self):
  rows=[{'address':str(i),'pnl':p,'volume':v} for i,(p,v) in enumerate([(4,10),(-2,20),(0,30),(None,40)])]
  m=metric(rows,100)
  self.assertEqual((m['valid_pnl_wallets'],m['nonzero_pnl_wallets'],m['winning_wallets']), (3,2,1))
  self.assertAlmostEqual(m['pct_profitable'],.5)
  self.assertAlmostEqual(m['pct_profitable_by_volume'],.1)
  self.assertAlmostEqual(m['pct_profitable_by_nonzero_volume'],1/3)
  self.assertAlmostEqual(m['excluded_volume_share'],.7)
  self.assertEqual(m['net_pnl'],2)
  self.assertEqual(m['gross_positive_wallet_pnl'],4)
  self.assertEqual(m['gross_negative_wallet_pnl'],-2)
  self.assertEqual(m['median_pnl'],0)
  self.assertAlmostEqual(m['pnl_per_dollar'],.02)
  self.assertEqual(m['top10_concentration'],1)
 def test_exclusions_and_small_sample(self):
  rows=[{'address':str(i),'pnl':p,'volume':10} for i,p in enumerate([100,-20,-10,5,0,None])]
  ex=exclusion(rows,60,1)
  self.assertEqual(ex['net_pnl'],-25)
  self.assertEqual(ex['winning_wallets'],1)
  self.assertEqual(ex['nonzero_pnl_wallets'],3)
  self.assertAlmostEqual(ex['pnl_per_dollar'],-.5)
  self.assertIsNone(exclusion(rows,60,10))
 def test_company_key_is_x_uid_and_address_fallback(self):
  self.assertEqual(key({'xUserId':' 123 '},'0xABC'),'x:123')
  self.assertEqual(key({},'0xABC'),'builder:0xabc')
  a=[{'address':'0xA'},{'address':'0xB'},{'address':'0xC'}]
  groups=group(a,{'0xa':{'info':{'xUserId':'123'}},'0xb':{'info':{'xUserId':'123'}},'0xc':{'info':{}}})
  self.assertEqual(sorted(map(len,groups.values())),[1,2])

 def test_label_loader_rejects_invalid_values_and_duplicate_or_missing_factor(self):
  review=[dict(label=tag,status='Verified' if tag=='Bots' else 'No qualifying feature found',source_url='https://example.com',note='Relevant feature checked.') for tag in PRODUCT_TAGS]
  base=dict(rank='1',company='Example',company_id='x:test',builder_codes='Example',type='Wallet',form_factor='unknown',product_tags='Bots',type_confidence='High',type_source_url='https://example.com',type_evidence='Wallet keys and balances.',form_factor_confidence='Low',form_factor_source_url='https://example.com',form_factor_evidence='Distribution not documented.',tag_evidence=json.dumps([dict(label='Bots',source='https://example.com',confidence='High',evidence='Bots execute orders.')]),tag_review=json.dumps(review))
  cases=[
   [dict(base,form_factor='')],
   [dict(base,form_factor='iOS app')],
   [dict(base,type='Unclassified')],
   [dict(base,product_tags='Perpetuals')],
   [dict(base,product_tags='Bots | Bots')],
   [dict(base,product_tags='Bots | Pro')],
   [dict(base,tag_evidence='not JSON')],
   [dict(base,tag_evidence=json.dumps([dict(label='Pro',source='https://example.com',confidence='High',evidence='Pro.')]))],
   [dict(base,type_source_url='')],
   [dict(base,form_factor_evidence='')],
   [dict(base,type_confidence='Unverified')],
   [dict(base,tag_review='[]')],
   [dict(base,tag_review=json.dumps([dict(r,status='Verified') for r in review]))],
   [base,base],
  ]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'test_labels.csv'
   for rows in cases:
    with p.open('w',newline='') as f:
     writer=csv.DictWriter(f,fieldnames=LABEL_FIELDS);writer.writeheader();writer.writerows(rows)
    with self.assertRaises(ValueError):labels_load(p)
   with p.open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=LABEL_FIELDS);writer.writeheader();writer.writerow(base)
   item=labels_load(p)['x:test']
   self.assertEqual(item['forms'],['unknown'])
   self.assertEqual(item['tags'],['Bots'])
   self.assertEqual([x['dimension'] for x in item['sources']],['type','form_factor','product_tag'])

@unittest.skipUnless((DATA/'leaderboards/list_30d.json').exists(),'Dataset directory unavailable')
class OriginalDatasetChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.rows,cls.validation,_=analyze(DATA)
 def test_expected_selection_and_merges(self):
  self.assertEqual((self.validation['selected_builders'],len(self.rows)),(125,122))
  groups={c['name']:c for c in self.rows}
  self.assertEqual(len(groups['MetaMask']['builder_codes']),2)
  self.assertEqual(len(groups['Pear Protocol']['builder_codes']),2)
  self.assertEqual(len(groups['Markets Mobile']['builder_codes']),2)
 def test_platform_wide_24h_volume_cannot_supply_wallet_30d_denominator(self):
  audit=self.validation['platform_volume_24h']
  values=[]
  for c in self.rows:
   for address in c['builder_addresses']:
    profile=json.loads((DATA/'profiles'/f'{address}.json').read_text())
    values.append(float(profile['hyperliquidVolume24h']))
  self.assertEqual(len(values),125)
  self.assertEqual(audit['profiles_checked'],125)
  self.assertEqual(audit['profiles_with_value'],125)
  self.assertEqual(audit['period'],'24h')
  self.assertIn('Entire Hyperliquid platform',audit['scope'])
  self.assertIn('not an individual wallet 30-day',audit['limitation'])
  self.assertAlmostEqual(audit['min_usd'],min(values))
  self.assertAlmostEqual(audit['max_usd'],max(values))
  self.assertTrue(15e9 < min(values) <= max(values) < 16e9)
  self.assertLess(max(values)-min(values),30000)
 def test_independent_large_small_and_merged_spots(self):
  leaderboard=json.loads((DATA/'leaderboards/list_30d.json').read_text())['builders']
  for name in ('HyperDash','slushy','MetaMask','Pear Protocol'):
   c=next(c for c in self.rows if c['name']==name)
   self.assertAlmostEqual(c['volume'],sum(b['volume'] for b in leaderboard if b['address'].lower() in c['builder_addresses']),places=4)
   wallet={}
   for addr in c['builder_addresses']:
    v=json.loads((DATA/'wallets'/f'{addr}_30d.json').read_text())
    for r in v['rows']:
     w=dict(zip(v['columns'],r));wallet_address=w['address'].lower()
     if wallet_address not in wallet:wallet[wallet_address]=w['perpPnl']
   self.assertEqual(c['wallets'],len(wallet))
   self.assertAlmostEqual(c['net_pnl'],sum(x for x in wallet.values() if x is not None),places=4)
 def test_all_company_core_metrics_independently_from_source(self):
  leader=json.loads((DATA/'leaderboards/list_30d.json').read_text())['builders']
  raw_groups=collections.defaultdict(list)
  for b in leader:
   if not isinstance(b.get('refCode'),str) or not b['refCode'].strip() or float(b['volume'])<=1e6:continue
   info=json.loads((DATA/'profiles'/(b['address'].lower()+'.json')).read_text())['info']
   uid=str(info.get('xUserId') or (info.get('xUser') or {}).get('xUserId') or '').strip().lower()
   cid='x:'+uid if uid else 'builder:'+b['address'].lower()
   raw_groups[cid].append(b)
  computed={c['company_id']:c for c in self.rows}
  self.assertEqual(set(computed),set(raw_groups))
  for cid,members in raw_groups.items():
   accounts={}
   for b in members:
    data=json.loads((DATA/'wallets'/(b['address'].lower()+'_30d.json')).read_text())
    for values in data['rows']:
     w=dict(zip(data['columns'],values));addr=w['address'].lower()
     if addr in accounts:
      self.assertEqual(accounts[addr]['pnl'],w['perpPnl'])
      accounts[addr]['volume']+=w['volume'] or 0
     else:accounts[addr]={'pnl':w['perpPnl'],'volume':w['volume'] or 0}
   pnls=[w['pnl'] for w in accounts.values() if w['pnl'] is not None]
   winners=[w for w in accounts.values() if w['pnl'] is not None and w['pnl']>0]
   nonzero=sum(p!=0 for p in pnls);routed=sum(w['volume'] for w in accounts.values())
   abspnl=sorted([abs(p) for p in pnls],reverse=True);volume=sum(b['volume'] for b in members)
   expected=dict(volume=volume,wallets=len(accounts),pct_profitable=len(winners)/nonzero if nonzero else None,
     pct_profitable_by_volume=sum(w['volume'] for w in winners)/routed if routed else None,
     net_pnl=sum(pnls),median_pnl=statistics.median(pnls) if pnls else None,
     pnl_per_dollar=sum(pnls)/volume,top10_concentration=sum(abspnl[:10])/sum(abspnl) if sum(abspnl) else None)
   for field,value in expected.items():
    with self.subTest(company=cid,metric=field):
     if value is None:self.assertIsNone(computed[cid][field])
     else:self.assertTrue(math.isclose(computed[cid][field],value,rel_tol=1e-10,abs_tol=1e-7))

 def test_missing_and_reconciliation_are_reported(self):
  v=self.validation
  self.assertEqual(v['same_builder_duplicate_wallet_rows'],0)
  self.assertEqual(v['overlap_valid_pnl_conflicts'],0)
  self.assertEqual(v['overlap_identical_valid_pnl_count'],v['overlapping_wallets_across_builders'])
  self.assertTrue(any(c['name']=='Atomic' for c in v['company_volume_discrepancies_over_1pct']))
  self.assertTrue(v['missing_perp_pnl_rows']>0)

 def test_historical_sample_is_reproducible_and_private(self):
  one=choose_sample(DATA);two=choose_sample(DATA)
  self.assertEqual(one,two)
  self.assertGreaterEqual(len(one),150)
  self.assertTrue(all(s['end'].startswith('2026-10-30') for s in one.values()))
  self.assertTrue(all(s['selected_volume']>=s['largest_builder_volume']>=0 for s in one.values()))
  report=json.loads((ROOT/'volume_comparison.json').read_text())
  self.assertEqual(report['overall']['sampled'],len(one))
  self.assertGreater(report['overlapping_wallets']['valid'],0)
  self.assertNotIn('0x',json.dumps(report))
  self.assertEqual(report['overall']['sampled'],sum(report['overall']['statuses'].values()))

 def test_four_questions_use_distinct_counts_rates_robustness_and_unique_pnl(self):
  types=types_aggregate(self.rows);v=self.validation
  winners=max(types,key=lambda t:t['winning_wallet_observations'])
  self.assertEqual((winners['type'],winners['winning_wallet_observations']),('Wallet',14921))
  self.assertEqual(max(types,key=lambda t:t['pct_profitable'])['type'],'Trading app')
  for field in ('pct_profitable_by_volume','pnl_per_dollar'):
   self.assertEqual(max(types,key=lambda t:t[field])['type'],'Terminal & analytics')
  self.assertEqual(v['unique_wallets_with_conflicting_pnl'],0)
  self.assertEqual(v['unique_wallets_with_valid_pnl'],v['unique_wallets_positive_pnl']+v['unique_wallets_negative_pnl']+v['unique_wallets_zero_pnl'])
  self.assertEqual(v['unique_wallets_with_valid_pnl'],151312)
  self.assertAlmostEqual(v['unique_wallets_gross_positive_pnl']+v['unique_wallets_gross_negative_pnl'],v['unique_wallets_net_pnl'],places=4)
  self.assertAlmostEqual(sum(c['net_pnl'] for c in self.rows),-103748223.788166,places=4)
  t1=[c for c in self.rows if c['without_top1'] is not None]
  t10=[c for c in self.rows if c['without_top10'] is not None]
  self.assertEqual((len(t1),sum(c['net_pnl']*c['without_top1']['net_pnl']<0 for c in t1)),(120,19))
  self.assertEqual((len(t10),sum(c['net_pnl']*c['without_top10']['net_pnl']<0 for c in t10)),(113,16))
  brief=findings(self.rows,v,types,[])
  self.assertEqual(brief.count('<section class="finding">'),3)
  for phrase in ('14,921','31.62%','2,056','19 of 120','16/113','$10.33m','$34.54m','What to distrust'):
   self.assertIn(phrase,brief)

 def test_top30_exact_label_taxonomy_and_reproducible_proposals(self):
  from make_labels import proposals
  with (ROOT/'labels.csv').open(newline='') as f:
   records=list(csv.DictReader(f))
  self.assertEqual(records,proposals(DATA))
  by_id={}
  for record in records:
   for field in ('type','form_factor'):
    self.assertTrue(record[f'{field}_source_url'].startswith('https://'))
    self.assertTrue(record[f'{field}_evidence'].strip())
    self.assertIn(record[f'{field}_confidence'],('High','Medium','Low'))
   for evidence in json.loads(record['tag_evidence']):
    self.assertTrue(evidence['source'].startswith('https://'))
    self.assertTrue(evidence['evidence'].strip())
    self.assertIn(evidence['confidence'],('High','Medium','Low'))
   self.assertNotIn(record['company_id'],by_id)
   by_id[record['company_id']]=record
  self.assertEqual(len(by_id),30)
  self.assertEqual(set(by_id),{r['company_id'] for r in self.rows[:30]})
  for company in self.rows[:30]:
   record=by_id[company['company_id']]
   tags=record['product_tags'].split(' | ') if record['product_tags'] else []
   self.assertEqual(record['company'],company['name'])
   self.assertEqual(record['type'],company['type'])
   self.assertIn(record['type'],TYPES)
   self.assertIn(record['form_factor'],FORM_FACTORS)
   self.assertTrue(set(tags)<=set(PRODUCT_TAGS))
   self.assertEqual(len(tags),len(set(tags)))
   self.assertEqual(company['forms'],[record['form_factor']])
   self.assertEqual(company['tags'],tags)
  self.assertGreater(sum(2+len(json.loads(r['tag_evidence'])) for r in records),84)
  self.assertEqual(sum(len(json.loads(r['tag_review'])) for r in records),300)
  self.assertEqual(sum(sum(a['status']=='Verified' for a in json.loads(r['tag_review'])) for r in records),
                   sum(len(json.loads(r['tag_evidence'])) for r in records))
  status_counts=collections.Counter(a['status'] for r in records for a in json.loads(r['tag_review']))
  self.assertEqual(status_counts,{'Verified':48,'No qualifying feature found':176,'Insufficient evidence':76})
  self.assertEqual(sum(bool(r['product_tags']) for r in records),24)
  by_name={r['company']:r for r in records}
  self.assertEqual(by_name['Liquid']['product_tags'],'')
  liquid_rewards=next(x for x in json.loads(by_name['Liquid']['tag_review']) if x['label']=='Rewards')
  self.assertEqual(liquid_rewards['status'],'No qualifying feature found')
  self.assertEqual(liquid_rewards['source_url'],'https://www.liquid.trade/affiliates')
  invo_copy=next(x for x in json.loads(by_name['Invo']['tag_evidence']) if x['label']=='Copy trading')
  self.assertEqual(invo_copy['confidence'],'Medium')
  self.assertEqual(invo_copy['source'],'https://www.invoapp.com/guides/managing-trades')
  for name in ('entropy.io','near.com'):
   self.assertEqual((by_name[name]['form_factor'],by_name[name]['form_factor_confidence']),('desktop/web','Medium'))
  self.assertEqual(sum(x['type'] in TYPES for x in self.rows[:30]),30)
  resolved={'entropy.io':'Trading app','HyperLink':'Trading app','near.com':'Wallet','Tria':'Wallet'}
  for name,expected in resolved.items():
   company=next(x for x in self.rows[:30] if x['name']==name)
   self.assertEqual(company['type'],expected)
   self.assertIn('User-reviewed',by_id[company['company_id']]['type_evidence'])
  reviewed_factors={'Insilico':'both','Invo':'both','entropy.io':'desktop/web',
                    'HyperLink':'both','near.com':'desktop/web','Tria':'both','Wallet V':'mobile-first'}
  for name,expected in reviewed_factors.items():
   company=next(x for x in self.rows[:30] if x['name']==name)
   self.assertEqual(company['forms'],[expected])
   form_row=by_id[company['company_id']]
   self.assertTrue(form_row['form_factor_source_url'].startswith('https://'))
   self.assertGreaterEqual(len(form_row['form_factor_evidence']),60)
  self.assertEqual(sum(c['forms']==['unknown'] for c in self.rows[:30]),0)
  onchain=next(c for c in self.rows[:30] if c['name']=='ONCHAINCC')
  self.assertEqual(onchain['forms'],['both'])
  self.assertEqual(by_id[onchain['company_id']]['form_factor_source_url'],'https://onchain.cc/')
  refined={'HyperDash':('both','High'),'TreadFi':('both','High'),
           'HyperLink':('both','High'),'Outcome':('both','Medium'),
           'Axiom':('both','Medium')}
  for name,(expected_form,expected_confidence) in refined.items():
   company=next(c for c in self.rows[:30] if c['name']==name)
   form=by_id[company['company_id']]
   self.assertEqual((form['form_factor'],form['form_factor_confidence']),(expected_form,expected_confidence))
  self.assertEqual(collections.Counter(c['forms'][0] for c in self.rows[:30]),
                   {'both':22,'desktop/web':5,'mobile-first':3})

if __name__=='__main__':unittest.main()
