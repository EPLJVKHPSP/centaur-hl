"""Reproduce source-backed AI-assisted research and reviewed top-30 labels.

AI-assisted research initially left four ambiguous products Unclassified.
The user manually selected their primary types on 1 November 2026.
The user confirmed mobile versions for Axiom and Outcome on 1 Nov 2026.
On 2 Nov the user approved four targeted tag/form-factor evidence adjustments;
other labels remain AI-assisted research proposals, not a complete human audit.
Research is stored as source-backed evidence; this script does not call an LLM.
"""
import csv
import json
from pathlib import Path

from build import ROOT, TYPES, FORM_FACTORS, PRODUCT_TAGS, LABEL_FIELDS, group, num

# Primary type, source, reason supporting main workflow, confidence.
# Unclassified remains a documented exception/status, not a sixth type.
EVIDENCE = {
    'HyperDash': ('Terminal & analytics', 'https://hyperdash.com/start', 'A Hyperliquid power terminal emphasizing trader analytics, whale tracking, heatmaps and advanced execution.', 'High'),
    'fomo': ('Social trading', 'https://fomo.family/', 'The official product describes itself as social-first: discovering and following traders, a feed, alerts and a leaderboard define its trading workflow. Reviewed against the taxonomy on 2 Nov 2026.', 'High'),
    'Phantom': ('Wallet', 'https://help.phantom.com/articles/36482144712083', 'Self-custody wallet manages keys and funds, with trading integrated into the wallet.', 'High'),
    'MetaMask': ('Wallet', 'https://support.metamask.io/start/getting-started-with-metamask', 'The browser/mobile wallet primarily manages crypto private keys and dapp access, although it also offers trades.', 'High'),
    'Rabby': ('Wallet', 'https://rabby.io/', 'The core product is an EVM self-custody wallet.', 'High'),
    'Trust Wallet': ('Wallet', 'https://trustwallet.com/download', 'The core product holds and manages self-custodied crypto assets.', 'High'),
    'Insilico': ('Terminal & analytics', 'https://docs.insilicoterminal.com/documentation/welcome/frequently-asked-questions', 'The official FAQ describes a terminal focused on advanced order execution, latency and slippage for experienced traders.', 'High'),
    'Borsa': ('Terminal & analytics', 'https://www.borsa.cc/', 'A trading front end offering a desktop strategy studio and advanced market tools.', 'Medium'),
    'Liquid': ('Trading app', 'https://www.liquid.trade/', 'Markets and order placement in a non-custodial perpetuals trading application are the primary activity.', 'High'),
    'Invo': ('Social trading', 'https://www.invoapp.com/', 'Trader discovery, social trading and mirroring trader positions are defining features.', 'High'),
    'entropy.io': ('Trading app', 'https://entropy.io/trade', 'User-reviewed classification (1 Nov 2026): the Entropy trading venue provides access to tradable markets; direct trading is the closest primary workflow.', 'Medium'),
    'TreadFi': ('Automation & AI', 'https://www.tread.fi/', 'Trading workflows emphasize configured algorithmic and automated execution.', 'High'),
    'Moonbot': ('Automation & AI', 'https://moonbot.eu/en', 'Manual terminal and automated strategies coexist; automatic execution strategies are central enough for the automation type, though this is borderline.', 'Medium'),
    'OneKey': ('Wallet', 'https://onekey.so/', 'Self-custody wallet hardware and wallet software underpin the product.', 'High'),
    'Axiom': ('Trading app', 'https://www.ycombinator.com/companies/axiom', 'A unified platform for trading memecoins, perpetuals and yield markets.', 'Medium'),
    'METASCALP': ('Terminal & analytics', 'https://metascalp.io/en', 'Professional desktop-style terminal with order book, tape, clusters and rapid order execution.', 'High'),
    'HyperLink': ('Trading app', 'https://github.com/hyperlink-xyz', 'User-reviewed boundary decision (1 Nov 2026): HyperLink provides Hyperliquid prime-broker order-routing/execution access; Trading app is the nearest permitted category, although it is primarily infrastructure rather than a retail trading app.', 'Low'),
    'Legend': ('Social trading', 'https://docs.legend.trade/', 'Trader following, copying, sharing ideas and competitive social ranks define the product.', 'High'),
    'BITGETWALLET': ('Wallet', 'https://web3.bitget.com/', 'The marketed core product is a self-custody wallet for crypto assets.', 'Medium'),
    'Based': ('Wallet', 'https://based.one/about', 'Based foregrounds self-custody wallet management even though it also offers trading and spending.', 'High'),
    'near.com': ('Wallet', 'https://near.com/', 'User-reviewed classification (1 Nov 2026): near.com is a unified account with asset balances, sending and cross-chain swaps; integrated trading is one wallet workflow.', 'High'),
    'Mass': ('Trading app', 'https://mass.money/', 'The consumer app focuses on trading stocks, crypto and perpetuals.', 'High'),
    'Outcome': ('Trading app', 'https://github.com/Outcome-xyz/mintlify-docs/blob/main/outcome-and-hyperliquid.mdx', 'An execution interface for HIP-4 binary outcome markets on Hyperliquid.', 'High'),
    'Trasia': ('Trading app', 'https://play.google.com/store/apps/details?id=xyz.trasia.app', 'Mobile application for trading Hyperliquid perpetual and HIP-3 markets.', 'High'),
    'TIGERCOM': ('Terminal & analytics', 'https://hyperliquid.tiger.com/', 'Specialist desktop trading terminal with depth of market, hotkeys, footprint and cluster analysis.', 'High'),
    'Rainbow': ('Wallet', 'https://rainbow.me/', 'A self-custody crypto wallet supporting onchain assets.', 'High'),
    'ONCHAINCC': ('Terminal & analytics', 'https://onchain.cc/', 'A multi-market terminal with execution and analysis across crypto market types.', 'High'),
    'Tria': ('Wallet', 'https://www.tria.so/', 'User-reviewed classification (1 Nov 2026): a self-custodial account unifies crypto balances, transfers, spending, yield and integrated Hyperliquid trading; wallet/account management anchors the product.', 'High'),
    'Bullpen': ('Terminal & analytics', 'https://docs.bullpen.fi/', 'Multi-market onchain trading terminal with advanced execution and specialist discovery tools.', 'High'),
    'Wallet V': ('Automation & AI', 'https://walletv.io/', 'Autonomous third-party AI trading agents execute configured investment strategies.', 'High'),
}

# Exactly one form factor per researched company. Unknown is generated automatically
# when no supported primary workflow can be established; that is not a claim of absence.
# Values are (factor, source, concrete platform evidence, confidence).
FACTOR_EVIDENCE = {
    'HyperDash': ('both', 'https://hyperdash.com/', 'Official trading website was checked at desktop (1440px) and iPhone-sized (390px) viewports on 1 Nov 2026. Its mobile Trade tab displayed the same core order workflow (market/limit, long/short, size and TP/SL); no order was placed.', 'High'),
    'fomo': ('both', 'https://fomo.family/', 'Official product explicitly lets customers open on phone and close on desktop, with a downloadable app and web trading.', 'High'),
    'Phantom': ('both', 'https://help.phantom.com/articles/48456789393811', 'Officially supports a desktop Chrome extension and iOS/Android wallet apps.', 'High'),
    'MetaMask': ('both', 'https://support.metamask.io/start/getting-started-with-metamask', 'Official install instructions cover browser extension and mobile wallet.', 'High'),
    'Rabby': ('both', 'https://rabby.io/', 'Official Rabby download page lists browser extensions, desktop software and iOS/Android wallet applications.', 'High'),
    'Trust Wallet': ('both', 'https://trustwallet.com/download', 'Official page describes the full wallet on mobile and as a browser extension.', 'High'),
    'Insilico': ('both', 'https://docs.insilicoterminal.com/documentation/welcome/frequently-asked-questions', 'Official Insilico Terminal FAQ confirms the trading terminal runs on mobile browsers with essentially the same functionality as on desktop; the PWA installation guide also documents both devices.', 'High'),
    'Borsa': ('both', 'https://www.borsa.cc/', 'Official product says the full trading terminal runs in a phone browser as well as desktop; desktop additionally has Strategy Studio.', 'High'),
    'Liquid': ('both', 'https://www.liquid.trade/', 'Official app offers browser and iOS/Android trading interfaces.', 'High'),
    'Invo': ('both', 'https://www.invoapp.com/', 'Official landing page links its dedicated web trading interface at app.invoapp.com and separately promotes downloadable mobile trading apps.', 'High'),
    'entropy.io': ('desktop/web', 'https://entropy.io/terms', 'Official terms dated August 2026 describe a web-based trading interface. Comparable mobile trading functionality has not been established by the reviewed evidence, so desktop/web is a provisional classification (manually reviewed 2 Nov 2026).', 'Medium'),
    'TreadFi': ('both', 'https://www.tread.fi/blog/mobile-crypto-algo-trading', 'Official 4 Sep 2025 product release says the Hyperliquid/CEX execution terminal is available on phones with live fills and order adjustment using the same execution engine as desktop. Web-terminal access is separately documented.', 'High'),
    'Moonbot': ('desktop/web', 'https://moon-bot.com/en/download/', 'Official download page calls Moonbot a Windows x64 desktop trading executable and lists PC system requirements.', 'High'),
    'OneKey': ('both', 'https://help.onekey.so/en/articles/11461166-update-your-onekey-app', 'Official instructions cover full desktop, browser-extension and mobile wallets.', 'High'),
    'Axiom': ('both', 'https://docs.axiom.trade/perpetuals/trading-on-hyperliquid', 'Official guide documents desktop/web trading. User confirmed on 1 Nov 2026 that Axiom also has a mobile version (and previously reported a mobile app). Automated access to the trading interface was blocked by Cloudflare, so this platform confirmation is attributed to the user.', 'Medium'),
    'METASCALP': ('desktop/web', 'https://app.metascalp.io/', 'Official product page offers a Windows download for its trading terminal and states macOS is still planned; no mobile interface is documented.', 'High'),
    'HyperLink': ('both', 'https://app.hyperlink.xyz/trade/HYPE', 'Official 29 Sep 2026 @hyperlink_xyz release confirms mobile trading. Browser checks of the direct desktop and iPhone-sized trading routes show live market details, order book tabs, portfolio controls, mobile Trade navigation, and an install-to-home-screen option. No funded trade was tested.', 'High'),
    'Legend': ('both', 'https://docs.legend.trade/', 'Full web terminal plus iOS and Android trading applications are documented.', 'High'),
    'BITGETWALLET': ('both', 'https://web3.bitget.com/', 'Official wallet page links iOS/Android apps alongside a Chrome desktop extension.', 'High'),
    'Based': ('both', 'https://based.one/', 'Official website explicitly describes access via web, desktop app and mobile with one wallet and integrated trading.', 'High'),
    'near.com': ('desktop/web', 'https://near.com/terms', 'The October 2026 terms document browser-based account and swap interfaces. References to mobile access do not establish equivalent mobile trading/account workflows for near.com; desktop/web is provisional (manually reviewed 2 Nov 2026). Separate NEAR ecosystem wallets are distinct products.', 'Medium'),
    'Mass': ('mobile-first', 'https://mass.money/', 'The promoted core trading product is a mobile phone application.', 'High'),
    'Outcome': ('both', 'https://outcome.xyz/', 'Official trading website displays desktop and mobile market interfaces and Trade buttons. User confirmed on 1 Nov 2026 that Outcome has a working mobile web version, without a dedicated mobile app. This confirmation is user-provided; automated browser access to individual market details was blocked by Cloudflare.', 'Medium'),
    'Trasia': ('mobile-first', 'https://play.google.com/store/apps/details?id=xyz.trasia.app', 'Google Play listing documents a native mobile trading experience.', 'High'),
    'TIGERCOM': ('desktop/web', 'https://hyperliquid.tiger.com/', 'Hyperliquid-specific Tiger.com setup requires the desktop trading terminal for Windows/macOS; general Tiger broker mobile app does not establish the same Hyperliquid builder trading workflow.', 'High'),
    'Rainbow': ('both', 'https://rainbow.me/support/extension/supported-browsers-and-systems', 'Official support documents browser-extension wallet on desktop and Rainbow wallet mobile app.', 'High'),
    'ONCHAINCC': ('both', 'https://onchain.cc/', 'Official FAQ states the Onchain trading terminal runs directly in any mobile browser and needs no installation; the same site provides the desktop web terminal.', 'High'),
    'Tria': ('both', 'https://help.tria.so/en/articles/14033999-how-do-i-sign-up-for-tria', 'Tria official help center directs users to either an official app-store mobile app or the Tria Web App to create and use the same Tria account.', 'High'),
    'Bullpen': ('both', 'https://docs.bullpen.fi/features/mobile-desktop-app', 'Official docs describe a progressive web trading application accessible via iOS, Android mobile browsers and desktop browsers.', 'High'),
    'Wallet V': ('mobile-first', 'https://walletv.io/', 'Wallet V official product page links its iOS App Store and Android Google Play applications and directs users to download the app for AI trading; no equivalent desktop trading app is documented.', 'High'),
}

# Feature-specific, independently auditable product tags. The source must establish
# the feature, not merely contain a related buzzword in the company name.
# (tag, official/product source, feature-specific evidence, confidence).
TAG_EVIDENCE = {
    'HyperDash': [
        ('Alpha discovery', 'https://hyperdash.com/start', 'Alpha Leaderboard and smart-money tracking expose candidate traders and capital flows.', 'High'),
        ('Copy trading', 'https://hyperdash.com/copytrading', 'Copytrade feature mirrors top traders automatically.', 'High'),
        ('Pro', 'https://hyperdash.com/start', 'Advanced execution orders, liquidation analytics and detailed trader metrics support specialist use; the reviewed page does not explicitly name professional users.', 'Medium'),
    ],
    'fomo': [
        ('Community', 'https://fomo.family/', 'Social trader feed and leaderboard are part of the trading app.', 'High'),
        ('Alpha discovery', 'https://fomo.family/', 'Discovery feed and notifications identify top traders and what they are buying.', 'High'),
    ],
    'Phantom': [
        ('Alpha discovery', 'https://help.phantom.com/articles/use-the-explore-tab-in-phantom-on-mobile-41523165147667', 'Explore includes top-trader rankings, trader profiles, and curated token lists for finding trading opportunities.', 'High'),
        ('Community', 'https://help.phantom.com/articles/join-live-chats-in-phantom-44454103123731', 'Live token, perp and prediction-market chats allow trader replies, reactions and activity sharing.', 'High'),
    ],
    'MetaMask': [
        ('Rewards', 'https://support.metamask.io/manage-crypto/trade/perps/how-to-trade-perps/', 'MetaMask Rewards levels change perpetuals trading fees; its official Rewards program also runs incentives and campaigns.', 'High'),
        ('Gamified', 'https://support.metamask.io/id/manage-crypto/metamask-rewards/how-to-participate-in-rewards', 'The 9–23 June 2026 Perps Trading Competition awarded campaign prizes to participating traders; this is a historical, time-limited competition.', 'Medium'),
    ],
    'Rabby': [
        ('Rewards', 'https://rabby.io/points', 'Rabby Points is a first-party wallet points and referral-bonus program, accessible through the Rabby app.', 'High'),
    ],
    'Trust Wallet': [
        ('Rewards', 'https://trustwallet.com/blog/company/trust-premium-rewards', 'Trust Premium Reward Center lets qualified users redeem engagement XP for partner-backed perks.', 'High'),
        ('Gamified', 'https://trustwallet.com/blog/announcements/how-to-get-more-from-your-wallet-with-trust-premium', 'Trust Premium explicitly uses daily actions, accumulated XP, and tier progression to unlock benefits.', 'Medium'),
    ],
    'OneKey': [
        ('Rewards', 'https://help.onekey.so/en/articles/11461266-onekey-referral-program-long-term-rewards', 'OneKey App offers referral incentives on eligible Perps trades, Swap services and DeFi products; the official document specifies reward rates and supported services as of 28 October 2026.', 'High'),
    ],
    'Borsa': [
        ('Bots', 'https://www.borsa.cc/', 'Strategy Studio can run user-configured rule-based trading automatically, on-device or via Borsa Cloud.', 'High'),
        ('Pro', 'https://www.borsa.cc/', 'Specialist Strategy Studio, TWAP, Pine scripting and order tooling target advanced traders.', 'Medium'),
        ('Rewards', 'https://www.borsa.cc/', 'Weekly brsPoints rewards are earned from platform activity and staking boosts.', 'High'),
    ],
    'Insilico': [('Pro', 'https://docs.insilicoterminal.com/documentation/welcome/frequently-asked-questions', 'The official FAQ targets advanced traders using sophisticated execution software, with latency and slippage controls.', 'Medium')],
    'Invo': [
        ('Community', 'https://www.invoapp.com/', 'Social trader discovery is a product feature.', 'High'),
        ('Copy trading', 'https://www.invoapp.com/guides/managing-trades', 'A dedicated copy action lets users reproduce another trader\'s position parameters after manual confirmation. Ongoing automatic mirroring and subsequent updates are not established; manually reviewed on 2 Nov 2026.', 'Medium'),
        ('Alpha discovery', 'https://www.invoapp.com/', 'The official landing page provides ranked trader profiles, historical performance, and the Invo Score to find potential traders to follow.', 'High'),
    ],
    'TreadFi': [
        ('Bots', 'https://www.tread.fi/', 'Algorithmic execution automates a configured trade execution strategy.', 'Medium'),
        ('Pro', 'https://www.tread.fi/', 'Official site explicitly promotes institutional-grade execution tools and direct REST API access to its execution engine.', 'High'),
    ],
    'Moonbot': [
        ('Bots', 'https://moonbot.eu/en', 'Configured automatic strategies execute trades on preset signals.', 'High'),
        ('Scalping', 'https://moon-bot.com/', 'Official terminal promotes fast manual scalping and tick chart trading.', 'High'),
    ],
    'Axiom': [
        ('Trenches (memecoins)', 'https://www.ycombinator.com/companies/axiom', 'The trading platform explicitly foregrounds memecoin trading.', 'High'),
        ('Rewards', 'https://docs.axiom.trade/getting-started/point-system', 'The official point system grants points for trades and referrals, with a leaderboard and stated additional benefits.', 'High'),
        ('Gamified', 'https://docs.axiom.trade/getting-started/point-system', 'Trading and referrals accrue scores and leaderboard ranking, giving users a competitive progression mechanic.', 'Medium'),
    ],
    'METASCALP': [('Pro', 'https://metascalp.io/en', 'Professional traders are the stated target users of the order-book execution terminal.', 'High')],
    'Legend': [
        ('Community', 'https://docs.legend.trade/clans', 'Clans provide a shared chat, member list and group trading statistics.', 'High'),
        ('Copy trading', 'https://docs.legend.trade/copy-trading/autocopy', 'Autocopy mirrors another trader’s position changes in a dedicated copy wallet.', 'High'),
        ('Rewards', 'https://docs.legend.trade/clans', 'Clan members earn builder-fee rebates based on their group’s rolling trading volume.', 'High'),
        ('Gamified', 'https://docs.legend.trade/ranks', 'Trader, clan and season leaderboards support competition over defined performance periods.', 'High'),
    ],
    'BITGETWALLET': [
        ('Rewards', 'https://web3.bitget.com/en/blog/articles/rewards-hub', 'First-party Rewards Hub offers onchain quest incentives and trading competitions with prize pools.', 'High'),
        ('Gamified', 'https://web3.bitget.com/en/blog/articles/rewards-hub', 'FOMO Thursdays features a gacha-style reward experience and Trading Arena competitions.', 'High'),
    ],
    'Based': [
        ('Rewards', 'https://based.one/blog/2025-07-11-affiliate-points-and-xp', 'Based awards trading/wallet XP and card-spending points, distinct from market trading returns.', 'High'),
    ],
    'Outcome': [
        ('Rewards', 'https://docs.outcome.xyz/outcome-liquidity-rewards', 'Official documentation lists an Outcome Liquidity Rewards program for activity in eligible outcome markets; rewards are program incentives rather than hypothetical token airdrops.', 'Medium'),
        ('Gamified', 'https://docs.outcome.xyz/badges-and-cards', 'Official documentation has a dedicated badges-and-cards feature alongside a leaderboard, representing a collectible/competitive interface.', 'Medium'),
    ],
    'TIGERCOM': [('Pro', 'https://hyperliquid.tiger.com/', 'DOM, hotkeys, footprints and cluster views are specialist trader execution tools.', 'Medium')],
    'Rainbow': [
        ('Rewards', 'https://rainbow.me/points', 'Rainbow Points explicitly rewards swaps, holding, referrals and other wallet activity, with incentives distinct from investment returns.', 'High'),
    ],
    'ONCHAINCC': [
        ('Trenches (memecoins)', 'https://onchain.cc/', 'The official Trenches screen offers filters for market cap, volume and holders to snipe newly launched tokens.', 'High'),
        ('Alpha discovery', 'https://onchain.cc/', 'Purpose-built Trenches filters discover newly minted tokens and identify high-activity launches before trading.', 'High'),
        ('Rewards', 'https://onchain.cc/', 'The Colosseum program returns 25–50% of trading fees as claimable USDC cashback, with a stated seasonal reward pool.', 'High'),
        ('Gamified', 'https://onchain.cc/', 'Colosseum has Recruit-to-Immortal ranks, weekly quests, loot boxes and an end-of-season leaderboard.', 'High'),
    ],
    'Tria': [
        ('Rewards', 'https://blogs.tria.so/en/tria-points-and-mystery-boxes', 'Season 3 awards points for card spending, Hyperliquid trading, referrals and participation, unlocking tangible Mystery Box benefits.', 'High'),
        ('Gamified', 'https://blogs.tria.so/en/tria-points-and-mystery-boxes', 'Points thresholds unlock staged Mystery Boxes with higher reward tiers and monthly openings.', 'High'),
    ],
    'Bullpen': [
        ('Alpha discovery', 'https://docs.bullpen.fi/', 'The official documentation describes tracking top wallets, convergence signals and trade alerts.', 'High'),
        ('Pro', 'https://docs.bullpen.fi/', 'Advanced orders including TWAP, alongside multi-market terminal execution.', 'Medium'),
    ],
    'Wallet V': [('Agents', 'https://walletv.io/', 'Autonomous AI agents execute trading strategies configured by users.', 'High')],
}

# AI-assisted review of all 10 allowed tags for every top-30 company, 2 Nov 2026.
# A negative search finding is deliberately scoped to the examined official material:
# it never asserts the feature does not exist. Limited material stays uncertain.
LIMITED_TAG_EVIDENCE = {
    'entropy.io', 'HyperLink', 'Mass', 'near.com', 'Trasia', 'Outcome',
    'TIGERCOM', 'Wallet V',
}
TAG_REVIEW_EXCEPTIONS = {
    ('Phantom', 'Copy trading'): 'The official Live Trades guide allows a one-off manually confirmed trade, explicitly not ongoing mirroring of the trader; it fails the systematic-copy rule.',
    ('near.com', 'Agents'): 'The official site marks AI-based finance assistance Coming soon; that does not establish a deployed autonomous trading agent.',
    ('Based', 'Agents'): 'Based AI is described as chat and research; the source does not establish autonomous trade execution by an agent.',
    ('OneKey', 'Rewards'): 'An official in-app referral incentive awards a share of eligible trade and service fees; participation and supported venues are restricted by the documented program rules.',
    ('Liquid', 'Rewards'): 'Reviewed the official affiliate program: fee sharing is offered to approved referral partners, but no qualifying in-product trader rewards feature was established. No Rewards tag assigned; this does not prove that no other incentives exist.',
}
TAG_REVIEW_SOURCE_OVERRIDES = {
    ('Liquid', 'Rewards'): 'https://www.liquid.trade/affiliates',
}
TAG_CRITERIA = {
    'Bots': 'automated rule-based trade execution',
    'Agents': 'autonomous AI agents that monitor, plan or execute trades',
    'Alpha discovery': 'dedicated signal, wallet, trader or opportunity discovery',
    'Community': 'in-product trader discussions, feeds or shared signals',
    'Copy trading': 'systematic replication of another trader\'s positions',
    'Trenches (memecoins)': 'prominent fast memecoin discovery or trading',
    'Scalping': 'explicit rapid short-horizon scalping support',
    'Pro': 'explicit professional or institutional execution tools',
    'Rewards': 'an incentive, points or benefits program beyond market returns',
    'Gamified': 'game-like achievements, competitions or progression',
}


def proposals(data_dir=ROOT / 'datasets'):
    """Return one sourced classification row for each of the top 30 companies."""
    data_dir = Path(data_dir)
    leaderboard = json.loads((data_dir / 'leaderboards/list_30d.json').read_text())['builders']
    builders = [b for b in leaderboard if isinstance(b.get('refCode'), str) and b['refCode'].strip() and (num(b.get('volume')) or 0) > 1e6]
    profiles = {b['address'].lower(): json.loads((data_dir / 'profiles' / f"{b['address'].lower()}.json").read_text()) for b in builders}
    groups = group(builders, profiles)
    top = sorted(groups.items(), key=lambda g: -sum(num(b['volume']) for b in g[1]))[:30]
    names = {max(items, key=lambda b: num(b['volume']))['refCode'] for _, items in top}
    if len(top) != 30 or names != set(EVIDENCE):
        raise ValueError(f'Research evidence does not match top 30: missing={names-set(EVIDENCE)} extra={set(EVIDENCE)-names}')
    if set(FACTOR_EVIDENCE) - names or set(TAG_EVIDENCE) - names:
        raise ValueError('Non-top-30 company has factor or tag evidence')
    rows = []
    for rank, (cid, members) in enumerate(top, 1):
        lead = max(members, key=lambda b: num(b['volume']))['refCode']
        codes = ' | '.join(b['refCode'] for b in members)
        typ, source, reason, conf = EVIDENCE[lead]
        if typ not in TYPES and typ != 'Unclassified':
            raise ValueError('Unsupported type: ' + typ)
        if lead in FACTOR_EVIDENCE:
            factor, fact_source, fact_reason, fact_conf = FACTOR_EVIDENCE[lead]
        else:
            factor, fact_source, fact_reason, fact_conf = ('unknown', source, 'Insufficient evidence of the primary delivery platform or equivalent mobile and desktop workflows; requires human research.', 'Low')
        if factor not in FORM_FACTORS:
            raise ValueError('Unsupported form factor: ' + factor)
        tags = []
        tag_evidence = []
        for tag, tag_url, tag_reason, tag_conf in TAG_EVIDENCE.get(lead, ()):
            if tag not in PRODUCT_TAGS:
                raise ValueError('Unsupported product tag: ' + tag)
            tags.append(tag)
            tag_evidence.append(dict(label=tag, source=tag_url, confidence=tag_conf, evidence=tag_reason))
        if len(tags)!=len(set(tags)):
            raise ValueError('Duplicate product tag: '+lead)
        verified = {entry['label']: entry for entry in tag_evidence}
        review = []
        for tag in PRODUCT_TAGS:
            if tag in verified:
                entry = verified[tag]
                status = 'Verified'
                url = entry['source']
                note = entry['evidence']
            elif lead in LIMITED_TAG_EVIDENCE:
                status = 'Insufficient evidence'
                url = source
                note = ('Accessible first-party material does not establish whether the product supports '
                        + TAG_CRITERIA[tag] + '; further product-level verification is needed.')
            else:
                status = 'No qualifying feature found'
                url = source
                note = ('The reviewed first-party product descriptions did not establish '
                        + TAG_CRITERIA[tag] + '; this limited search finding does not prove absence.')
            if (lead,tag) in TAG_REVIEW_EXCEPTIONS:
                note = TAG_REVIEW_EXCEPTIONS[(lead,tag)]
            url = TAG_REVIEW_SOURCE_OVERRIDES.get((lead,tag),url)
            review.append(dict(label=tag,status=status,source_url=url,note=note))
        rows.append(dict(rank=str(rank), company=lead, type=typ, form_factor=factor,
                         product_tags=' | '.join(tags), company_id=cid, builder_codes=codes,
                         type_confidence=conf, type_source_url=source, type_evidence=reason,
                         form_factor_confidence=fact_conf, form_factor_source_url=fact_source,
                         form_factor_evidence=fact_reason,
                         tag_evidence=json.dumps(tag_evidence, ensure_ascii=False),
                         tag_review=json.dumps(review, ensure_ascii=False)))
    return rows


if __name__ == '__main__':
    rows = proposals()
    with (ROOT / 'labels.csv').open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Companies labeled: {len(rows)}; tag decisions: {sum(len(json.loads(row["tag_review"])) for row in rows)}; verified tags: {sum(len(json.loads(row["tag_evidence"])) for row in rows)}')
