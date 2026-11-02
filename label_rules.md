# Top-30 builder classification rules

These definitions were recorded before classification and applied again during the final review. Rank the 30 largest **companies** by combined 30-day volume of their builder codes; company identity uses the same normalized X account grouping as the main analysis. Each receives exactly one primary type (or an explicitly documented `Unclassified` exception), exactly one form factor, and zero or more tags. These are product descriptors, not wallet-behavior labels.

## One primary type

| Type | One-line definition and inclusion rule |
|---|---|
| Wallet | Self-custody and asset management are the core workflow; include even when swaps or trades are integrated. |
| Trading app | Placing trades through an accessible market interface is the core workflow; include apps without specialist terminal emphasis. |
| Terminal & analytics | Professional execution surfaces, market/trader data, charting or order-book analysis define the core workflow. |
| Automation & AI | Configured bots, algorithms, or autonomous agents drive the core trading/monitoring workflow. |
| Social trading | Discovering, following, sharing, or copying other traders is the defining workflow. |

`Unclassified` is a recorded **status**, not a sixth type: use it when available evidence cannot distinguish a core workflow or the product is outside these five. Do not infer product functions from a builder code alone.

## Exactly one form factor

| Form factor | One-line definition and inclusion rule |
|---|---|
| mobile-first | The documented primary user experience is a phone application; include when mobile is the main interface, even if minor web support exists. |
| desktop/web | The documented main workflow runs in a browser, desktop extension or desktop application, without evidence of equivalent mobile support. |
| both | Officially documented or explicitly user-confirmed usable mobile **and** desktop/browser versions support the product's core workflow. |
| Telegram | A Telegram bot or Mini App is the primary place users perform the workflow; Telegram alerts alone do not qualify. |
| unknown | Evidence reviewed does not establish a primary platform or comparable cross-platform workflows; record uncertainty explicitly. |

These labels represent **supported/primary workflow**, not a list of operating systems. Evidence of a website alone is not proof of an actual web app; a marketing page alone does not qualify. If product parity or platform primacy is unclear, choose `unknown` until documented.

## Zero or more product tags

| Product tag | One-line definition and inclusion rule |
|---|---|
| Bots | Explicit rule-based or automated bots execute or manage trades without manual execution each time. |
| Agents | Explicit autonomous AI agents plan, monitor, or execute trading actions; an ordinary AI chatbot is insufficient. |
| Alpha discovery | Finding high-signal traders, opportunities, flows or assets through purpose-built discovery, screens or alerts is a documented feature. |
| Community | Trader feeds, shared signals, interactive discussions, or social groups are part of the product workflow. |
| Copy trading | Users can systematically mirror another trader's positions or trades, rather than merely view them. |
| Trenches (memecoins) | The product prominently supports rapid discovery or trading of memecoins and newly launched tokens. |
| Scalping | The product explicitly supports fast, short-horizon scalping workflows or presents itself as a scalping terminal. |
| Pro | The product explicitly targets professional traders with specialist execution, institutional-grade tooling or professional features. |
| Rewards | Earnable points, incentives, or a rewards program are built into the product experience, beyond ordinary market returns. |
| Gamified | Game-like progression, competitions, quests, or interactive achievement mechanics are documented product features. |

Do not replace unrelated legacy tags mechanically: derivatives, spot, prediction markets, advanced orders, basic wallet management and generic analytics are **not** tags in this rubric. Assign every tag from a specific linked feature claim; no tag means *unverified*, not known absent.

## Boundary and research protocol

**Boundary builder — MetaMask:** classify as `Wallet`, even though it offers swaps and derivatives: self-custody and key management remain its primary purpose. This makes `Wallet` versus `Trading app` a genuine boundary decision. Moonbot also straddles `Terminal & analytics` and `Automation & AI`; the recorded primary classification prioritizes its configured automatic strategies and should be reviewed if its product emphasis changes.

Each top-30 company has one row in `labels.csv`, containing one primary type, one form factor and optional tags in separate columns. Each type and form-factor claim has its own source URL, specific evidence and confidence; each product tag has the same information in the `tag_evidence` JSON list. High means explicit first-party documentation or directly observed core controls; Medium means partial evidence or a reasoned boundary classification; Low means substantial uncertainty. A reachable URL alone is not feature verification. Product tags describe supported features; no tag means unverified, not absent.

For product tags, AI-assisted research produced candidate evidence and the recorded decisions were reviewed against the sources and inclusion rules, applying manual judgment to ambiguous cases. The review checks **each of the 10 permitted tags against each of the 30 builders**. The `tag_review` JSON list on each company row contains exactly ten evaluations: `Verified` (a feature-specific source supports the assigned tag), `No qualifying feature found` (the reviewed first-party descriptions did not establish the rule, although absence is not proved), or `Insufficient evidence` (available descriptions are too limited to decide). The assignment's word **“any”** means zero or more tags, so the six companies without supported tags intentionally keep empty cells; inventing a tag to fill them would break the evidence rule. The sources and decisions are an auditable research snapshot as of 2 November 2026, not a live LLM classifier, an independent human audit, or proof that every possible feature page has been searched. The script `make_labels.py` regenerates the recorded decisions. Historical promotions are identified as such; paid yields alone do not qualify as `Rewards`. A generic one-off manual imitation is insufficient for `Copy trading`; Invo's explicit copy-position workflow is retained as a Medium-confidence boundary case without claiming automatic ongoing mirroring.

The user previously resolved four ambiguous types: entropy.io and HyperLink as Trading app; near.com and Tria as Wallet. These were classification decisions informed by AI-assisted research, not independent source verification. Axiom and Outcome mobile support retain recorded user confirmations with Medium confidence. Phone-sized automated browser checks do not prove funded trading works on a physical device.

**Targeted manual judgment review (2 November 2026):** After AI-assisted evidence review, the user explicitly checked and agreed with four decisions: (1) **Liquid** receives no `Rewards` tag because the cited affiliate program covers approved partners, not a demonstrated in-product trader rewards feature; (2) **Invo** retains `Copy trading` at **Medium** confidence because its dedicated, user-confirmed copy-position action is documented but continuing automatic mirroring is not; (3) **entropy.io** and (4) **near.com** remain `desktop/web` at **Medium** confidence because an equivalent mobile core workflow is not established. These are targeted user-approved judgments, not hands-on execution tests or a full independent audit of every company.

On 2 November 2026, fomo was reclassified as Social trading: its official page describes the product as social-first and emphasizes trader discovery, following and feeds. Trading-app accessibility alone does not override a documented defining social workflow. HyperDash’s Pro confidence was reduced because specialist features are documented but professional users are not explicitly named. Bullpen’s unsupported memecoin tag was removed. Legend tags now link to the specific feature pages. Update the evidence seed in `make_labels.py` before regenerating labels.

The intermediate form-factor research notes and screenshots are preserved locally at `research_evidence/form_factor/README.md`, outside the submission archive. Some older intermediate tables differ from final decisions; `labels.csv` is authoritative.
