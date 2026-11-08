"""Causal-timing, peer matching, historical-control and frozen-data tests."""
import unittest
from collections import defaultdict
from datetime import datetime, timezone

from backtest import (
    COST, DATA_DIR, DAY, HOUR, analyze, analyze_same_coin, annotate, cluster_ci, controls_for,
    dip_peers, index_publications, load_saved_data, no_prior_call_same_asset, no_recent_call,
    nonoverlap, prepare_events, select, execution_delay_sensitivity, validate_prices,
)


class CausalEntryTests(unittest.TestCase):
    def test_dip_uses_price_available_when_signal_was_published(self):
        t = int(datetime(2026, 9, 15, 13, tzinfo=timezone.utc).timestamp())
        # At signal publication (t - 40min), the latest hourly open is t-1h.
        # That trend is negative, even though the future trade entry opens up.
        coin = {t-DAY-HOUR: 100, t-HOUR: 98,
                t-DAY: 100, t: 101, t+DAY: 102}
        btc = {t-DAY-HOUR: 100, t-HOUR: 99}
        stamp = datetime.fromtimestamp(t-2400, tz=timezone.utc).isoformat()
        row = {'asset': 3, 'side': 1, 'trader': 7,
               'timestamp': stamp, 'entry_epoch': t, 'fresh': True,
               'price_24h': 1.0, 'ret24': 100*(102/101-1)-COST}
        prepared = prepare_events([row], {1: btc, 3: coin})[0]
        self.assertAlmostEqual(prepared['decision_24h_pct'], -2.0)
        self.assertAlmostEqual(prepared['decision_market_24h_pct'], -1.0)
        self.assertEqual(len(select([prepared])), 1)
        self.assertEqual(prepared['price_24h'], 1.0)

    def test_reject_misdated_or_inconsistent_cached_returns(self):
        t = 20000*HOUR
        stamp = datetime.fromtimestamp(t-1000, tz=timezone.utc).isoformat()
        coin = {t-DAY-HOUR:100,t-HOUR:98,t-DAY:100,t:101,t+DAY:102}
        btc = {t-DAY-HOUR:100,t-HOUR:99}
        row = {'asset':3,'side':1,'trader':7,'timestamp':stamp,'entry_epoch':t,
               'price_24h':1,'ret24':100*(102/101-1)-COST}
        self.assertEqual(len(prepare_events([row],{1:btc,3:coin})),1)
        with self.assertRaises(ValueError):
            prepare_events([{**row,'ret24':100}],{1:btc,3:coin})
        with self.assertRaises(ValueError):
            prepare_events([row,row],{1:btc,3:coin})
        with self.assertRaises(ValueError):
            prepare_events([{**row,'timestamp':datetime.fromtimestamp(t+1,timezone.utc).isoformat()}],
                           {1:btc,3:coin})

    def test_same_entry_hour_keeps_earliest_public_signal(self):
        t = 20000*HOUR
        def call(trader, sec_before):
            return {'entry_epoch': t, 'asset': 3,'trader': trader,
                    'timestamp': datetime.fromtimestamp(t-sec_before,timezone.utc).isoformat()}
        early = call(99, 3000)
        later = call(1, 600)
        after = {**call(2, 600), 'entry_epoch': t+DAY,
                 'timestamp': datetime.fromtimestamp(t+DAY-600,timezone.utc).isoformat()}
        chosen = nonoverlap([later,after,early],24)
        self.assertEqual([r['trader'] for r in chosen], [99,2])

    def test_cooldown_spans_the_date_window_boundary(self):
        first = int(datetime(2026,10,25,0,tzinfo=timezone.utc).timestamp())
        second = first + HOUR
        rows = [
            {'entry_epoch':first,'asset':9,'trader':5,
             'timestamp':'2026-10-24T23:50:00+00:00'},
            {'entry_epoch':second,'asset':9,'trader':6,
             'timestamp':'2026-10-25T00:50:00+00:00'},
        ]
        self.assertEqual(len(nonoverlap(rows,24)),1)
        self.assertEqual(nonoverlap(rows,24)[0]['trader'],5)

    def test_entry_date_clusters_include_midnight_crossovers(self):
        base = 20000*HOUR
        items = [{'timestamp':'2026-08-01T23:45:00+00:00',
                  'entry_epoch':base+i*DAY,'diff':float(i)} for i in range(3)]
        self.assertIsNotNone(cluster_ci(items,'day',repetitions=100))

    def test_reject_missing_hourly_prices_and_invalid_quotes(self):
        t = 20000*HOUR
        validate_prices({1:{t:100,t+HOUR:99},2:{t:1,t+HOUR:1.01}})
        with self.assertRaises(ValueError):
            validate_prices({1:{t:100,t+2*HOUR:99}})
        with self.assertRaises(ValueError):
            validate_prices({1:{t:100,t+HOUR:float('nan')}})


class MarketPeerTests(unittest.TestCase):
    def test_peers_match_prior_hour_dips_not_entry_hour_moves(self):
        t = 20000*HOUR
        def series(yesterday, last_open, at_entry, tomorrow):
            return {t-DAY-HOUR:yesterday, t-HOUR:last_open,
                    t:at_entry,t+DAY:tomorrow}
        bars = {
            1:series(100,99,100,101),
            3:series(100,98,110,110),  # traded asset; excluded from peers
            4:series(100,98,98,100),   # closest pre-entry dip
            5:series(100,99,99,80),    # second closest dip
            6:series(100,96,96,90),    # third closest dip
            7:series(100,101,98,200),  # rises before entry, excluded even though it dips at entry
        }
        row = {'asset':3,'entry_epoch':t,'decision_24h_pct':-2.0}
        p4 = 100*(100/98-1)-COST
        self.assertAlmostEqual(dip_peers(row,bars,1),p4)
        p5, p6 = 100*(80/99-1)-COST,100*(90/96-1)-COST
        self.assertAlmostEqual(dip_peers(row,bars,3),(p4+p5+p6)/3)
        self.assertIsNone(dip_peers(row,bars,4))

    def test_missing_forward_price_cannot_make_other_peer_look_closer(self):
        t=20000*HOUR
        def series(last, tomorrow=None):
            row={t-DAY-HOUR:100,t-HOUR:last,t:100}
            if tomorrow is not None:row[t+DAY]=tomorrow
            return row
        bars={1:series(100,101),3:series(97,101),
              4:series(98),5:series(99,105)}
        row={'asset':3,'entry_epoch':t,'decision_24h_pct':-2.0}
        self.assertIsNone(dip_peers(row,bars,1))

    def test_historical_price_only_control_is_before_signal_and_filters_posts(self):
        t = 20000 * HOUR
        prices = {t+h*HOUR: 100*(.99**(h/24)) for h in range(-15*24,26)}
        row = {'asset':3,'entry_epoch':t,'decision_24h_pct':-1}
        empty = defaultdict(list)
        control = no_prior_call_same_asset(row,{3:prices},empty)
        self.assertIsNotNone(control)
        self.assertLess(control,0)
        future = defaultdict(list,{3:[t+HOUR]})
        self.assertAlmostEqual(control,no_prior_call_same_asset(row,{3:prices},future))
        dense_prior = defaultdict(list,{3:[t-h*HOUR for h in range(1,16*24)]})
        self.assertIsNone(no_prior_call_same_asset(row,{3:prices},dense_prior))


class MatchedCoinControls(unittest.TestCase):
    def test_recent_call_filter_does_not_look_into_future(self):
        t=100*DAY
        self.assertTrue(no_recent_call(t,[]))
        self.assertTrue(no_recent_call(t,[t+HOUR]))
        self.assertTrue(no_recent_call(t,[t-25*HOUR,t+HOUR]))
        self.assertFalse(no_recent_call(t,[t-24*HOUR]))
        self.assertFalse(no_recent_call(t,[t-HOUR,t+HOUR]))
        self.assertFalse(no_recent_call(t,[t]))

    def test_actual_publication_seconds_control_recent_call_boundary(self):
        t = 100*DAY
        # A post 24h + 30m ago is outside the window. Rounding it forward
        # to the next hourly entry would wrongly exclude this control hour.
        post_older = t - DAY - 30*60
        self.assertTrue(no_recent_call(t,[post_older]))
        self.assertFalse(no_recent_call(t,[t - DAY + 30*60]))
        # A message published AFTER the potential control entry is future data.
        self.assertTrue(no_recent_call(t,[t+30*60]))
        rows = [{'asset':9,'timestamp':datetime.fromtimestamp(post_older,timezone.utc).isoformat()},
                {'asset':9,'timestamp':datetime.fromtimestamp(t+30*60,timezone.utc).isoformat()}]
        indexed = index_publications(rows)
        self.assertEqual(indexed[9],[post_older,t+30*60])
        self.assertTrue(no_recent_call(t,indexed[9]))

    def test_same_coin_btc_dips_and_24h_spacing(self):
        t0=100*DAY
        coin,btc={},{}
        eligible=[t0-7*DAY,t0-5*DAY,t0-3*DAY]
        wrong_regime=t0-DAY
        for idx,t in enumerate(eligible):
            coin.update({t-DAY-HOUR:100.,t-HOUR:99.,t:99.,t+DAY:101.+idx})
            btc.update({t-DAY-HOUR:100.,t-HOUR:99.})
        t=wrong_regime
        coin.update({t-DAY-HOUR:100.,t-HOUR:99.,t:99.,t+DAY:130.})
        btc.update({t-DAY-HOUR:100.,t-HOUR:101.})
        row={'entry_epoch':t0,'asset':9,'decision_24h_pct':-1.,
             'decision_market_24h_pct':-1.}
        result=controls_for(row,{9:coin,1:btc},defaultdict(list),
                            days=7,forward=False,count=3)
        self.assertEqual({c[2] for c in result},set(eligible))
        self.assertTrue(all(c[2] <= t0-DAY for c in result))
        self.assertTrue(all(abs(a[2]-b[2])>=DAY
                            for i,a in enumerate(result) for b in result[i+1:]))
        posts=defaultdict(list,{9:[eligible[0]-HOUR]})
        self.assertEqual(controls_for(row,{9:coin,1:btc},posts,
                                      days=7,forward=False,count=3),[])
        future_posts=defaultdict(list,{9:[t0+HOUR]})
        self.assertEqual(controls_for(row,{9:coin,1:btc},future_posts,
                                      days=7,forward=False,count=3),result)

    def test_forward_controls_are_not_used_as_prior_controls(self):
        t0=100*DAY
        after=[t0+2*DAY,t0+4*DAY,t0+6*DAY]
        coin,btc={},{}
        for t in after:
            coin.update({t-DAY-HOUR:100.,t-HOUR:99.,t:99.,t+DAY:102.})
            btc.update({t-DAY-HOUR:100.,t-HOUR:99.})
        row={'entry_epoch':t0,'asset':9,'decision_24h_pct':-1.,
             'decision_market_24h_pct':-1.}
        self.assertEqual(controls_for(row,{9:coin,1:btc},defaultdict(list),
                                      days=7,forward=False,count=3),[])
        self.assertEqual({c[2] for c in controls_for(
            row,{9:coin,1:btc},defaultdict(list),days=7,forward=True,count=3)},set(after))


@unittest.skipUnless(
    (DATA_DIR / 'observations.json').is_file() and (DATA_DIR / 'spot_hourly.json').is_file(),
    'Private historical datasets are not present; synthetic tests still run',
)
class FrozenInputRegression(unittest.TestCase):
    def test_cached_seven_day_freshness_flags_are_chronologically_consistent(self):
        """Accepted calls must agree with earlier cached same-trader/coin/side calls."""
        events, _ = load_saved_data(DATA_DIR/'observations.json', DATA_DIR/'spot_hourly.json')
        most_recent = {}
        for row in sorted(events, key=lambda r: r['timestamp']):
            key = (row['trader'], row['asset'], row['side'])
            posted_at = datetime.fromisoformat(row['timestamp'])
            previous = most_recent.get(key)
            expected_fresh = previous is None or (posted_at - previous).total_seconds() >= 7*DAY
            self.assertEqual(row['fresh'], expected_fresh, f'Freshness mismatch: {key} at {posted_at}')
            most_recent[key] = posted_at

    def test_all_cached_observations_and_selected_results(self):
        events,bars=load_saved_data(DATA_DIR/'observations.json',DATA_DIR/'spot_hourly.json')
        self.assertEqual(len(events),812)
        self.assertEqual(len(bars),35)
        validate_prices(bars)
        prepared=prepare_events(events,bars)
        chosen=nonoverlap([e for e in select(prepared) if e['fresh']],24)
        self.assertEqual(len(chosen),115)
        reports=analyze(annotate([e for e in select(prepared) if e['fresh']],bars),bars,prepared)
        self.assertEqual(reports['earlier']['original_n'],98)
        self.assertEqual(reports['recent']['original_n'],17)
        self.assertEqual(reports['earlier']['3_matched_peers']['n'],97)
        self.assertEqual(reports['recent']['3_matched_peers']['n'],17)
        self.assertAlmostEqual(reports['earlier']['3_matched_peers']['mean_excess_pp'],.980,places=3)
        self.assertAlmostEqual(reports['recent']['3_matched_peers']['mean_excess_pp'],2.693,places=3)
        self.assertEqual(reports['earlier']['historical_price_only_dip']['n'],96)
        self.assertAlmostEqual(reports['earlier']['historical_price_only_dip']['mean_excess_pp'],.636,places=3)
        delays=execution_delay_sensitivity(annotate([e for e in select(prepared) if e['fresh']],bars),bars)
        self.assertEqual(delays['earlier']['1h']['n'],97)
        self.assertAlmostEqual(delays['earlier']['1h']['mean_excess_pp'],.935,places=3)
        self.assertEqual(delays['recent']['1h']['n'],17)
        self.assertAlmostEqual(delays['recent']['1h']['mean_excess_pp'],1.937,places=3)

    def test_historical_controls_use_exact_post_times(self):
        rows,bars=load_saved_data(DATA_DIR/'observations.json',DATA_DIR/'spot_hourly.json')
        prepared=prepare_events(rows,bars)
        control=analyze_same_coin(prepared,bars)
        earlier=control['earlier']['preceding_14d']
        recent=control['recent']['preceding_14d']
        self.assertEqual((earlier['n'],recent['n']), (92,16))
        self.assertEqual((earlier['paired_excess_pp'],recent['paired_excess_pp']), (.829,2.096))


if __name__ == '__main__':
    unittest.main()
