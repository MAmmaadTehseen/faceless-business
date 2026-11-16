# Growth log

Standing loop: measure, diagnose, change, wait 1-3 days, measure again. Snapshot command (read-only):

```
PYTHONPATH=. .venv/bin/python scripts/growth_snapshot.py --days 30
```

Owner target (stated 2026-11-16): 10,000 views per day per video. Milestones on the way, in order:
1. Shorts retention above 70 percent (median today 36-58) so the platforms push past the first test pool.
2. A Short that keeps gaining views after day 2 (today every Short flattens within 48 hours).
3. Median Short above 1,000 views, then one Short past 10,000 total.
4. Daily views per video in the thousands, which on every comparable channel took months of 70 percent-plus retention, not weeks.

## Round 1: 2026-11-16

### Snapshot (last 30 days, public only)

| platform | channel | kind | n | median views | views/day median | median retention % | median AVD s | zero-view | comments |
|---|---|---|---|---|---|---|---|---|---|
| youtube | escapevelocity | long | 8 | 7.5 | 0.9 | 11 | 104 | 0 | 0 |
| youtube | escapevelocity | short | 25 | 24 | 5.0 | 36 | 27 | 0 | 0 |
| youtube | futurework | long | 11 | 7 | 0.7 | 16 | 80 | 1 | 4 |
| youtube | futurework | short | 24 | 14.5 | 1.8 | 40 | 20 | 1 | 0 |
| youtube | tradewinds | long | 8 | 2.5 | 0.2 | 27 | 112 | 3 | 0 |
| youtube | tradewinds | short | 26 | 47 | 8.2 | 58 | 35 | 0 | 0 |
| youtube | tentongues | all | 10 | 0 | 0 | n/a | n/a | 10 | 0 (day one) |
| instagram | escapevelocity | reel | 33 | 126 | | | | 0 | 0 |
| instagram | futurework | reel | 22 | 19.5 | | | | 0 | 0 |
| instagram | tradewinds | reel | 31 | 5 | | | | 2 | 0 |
| facebook | all | reel | 87 | 0 | | | | 85 | 0 |
| hub | all | pageviews | 48 views, 13 uniques, 40 from Pakistan (owner) | | | | | | |

Best Short: 620 views (escapevelocity, "The rescue didn't doom Swift"), retention 29 percent. Its view curve: 5 on day 0, 163 on day 1, 168 from day 2 onward for two weeks. Every Short follows that shape.
Shorts run 42-61 s (median 55); average view duration 20-35 s. Long videos run about 9 minutes with 80-110 s watched.
Posting times: Shorts go out at 13/15/18 UTC by channel; Reels went out in bursts of four within two minutes whenever a long video finished.

Comparison: a new faceless explainer channel typically sees 100-1,000 views per Short in the first test pool and single-digit views on long videos until Shorts bring subscribers. Our test pools are 100-600 impressions (visible as the day-1 jump), which is normal. What is not normal is that none of them get a second wave.

### Diagnosis (where the lag is)

- YouTube Shorts: impressions exist (the day-1 jump), so this is not zero distribution. Retention of 36-58 percent on 55-second Shorts is below the roughly 70 percent that earns a second wave, so each Short dies after its first pool. Zero comments on every upload confirms no engagement signal either.
- YouTube long: effectively no impressions (2-8 views). Expected at this age; longs grow from subscribers that Shorts bring. Retention 11-27 percent is weak but not the bottleneck yet.
- Instagram: escapevelocity reaches the normal non-follower test pool (median 126). futurework (19) and tradewinds (5) do not. Two likely causes: four Reels posted in two minutes (the second to fourth in each burst get 1-6 views on tradewinds) and captions that were the YouTube title plus a non-clickable YouTube link and `#shorts`, with no niche hashtags and no question.
- Facebook: unmeasured, not necessarily zero. The Page token lacks `read_insights`, the Reels `views` field returns 0, and the API refuses `video_insights`. Fix is owner-side (permission) plus the code change below.
- Hub: no organic traffic; the YouTube description links to articles are switched off (`yt_description_links_enabled` is unset).
- Ten Tongues: day one, nothing to judge.

### Hypotheses ranked (impact x cheapness)

1. Shorter Shorts with the payoff before 30 s lift retention to 70 percent and earn a second distribution wave. High impact, cheap (prompt change).
2. Spacing Reels one per day in step with the YouTube slot stops the burst penalty on IG/FB. High impact on IG for futurework/tradewinds, cheap (publisher change, no new infrastructure).
3. Captions with a hook line, a one-comment question and 3-5 niche hashtags raise comments and tell Instagram the niche. Medium impact, cheap.
4. YouTube Short descriptions with keywords, three hashtags and tags (child Shorts were uploaded with an empty description stub and no tags until publish time). Medium impact on search and suggested, cheap.
5. Facebook play counts via `video_insights` once the owner adds `read_insights`. Measurement only, cheap.
6. Hub article links in YouTube descriptions and playlists (settings already built, off). Owner toggle.
7. On-screen hook text card in the first second of each Short (render change). Medium impact, not done this round: touches render/QA and the running bank jobs.
8. Thumbnail and long-title work. Low impact until long videos get impressions; left for a later round.
9. Posting-time tuning. Not enough signal yet; IG by-hour numbers are noise at this volume.

### Shipped in round 1 (commit on main, 2026-11-16)

- Shorts scripts: 75-110 words (about 35-45 s) instead of 110-150; first sentence under twelve words naming an actor, object or number; payoff by sentence three; last line a one-comment question or a loop back to the hook. Applied to child Shorts (`pipeline/script.py`), daily Shorts (`pipeline/shorts_daily.py`, target 80-115, validation widened to 70-160 so saved responses still resume) and `persona/formulas.md`. Each channel's style.md keeps its own voice; only the length line changed.
- New `pipeline/publish/captions.py` (no model calls): Reels caption = spoken hook line, payoff sentence, closing question (script's own or `caption_question` from channel.json), "Full story on our YouTube channel" line, niche `hashtags` from channel.json. No links, no `#shorts`, no `@` (cross-mentions still added by the existing helper). YouTube Short description = hook, payoff, full-video link, channel footer, three niche hashtags plus `#Shorts`. Short tags = own tags, parent tags, then channel niche keywords, up to 15.
- `publish_short`: child Shorts no longer post Reels at production time when their YouTube copy is scheduled for the future. The existing `follow_youtube_to_reels` step in sync publishes them when YouTube makes the Short public, so Reels go out one per day per channel. Gated by shared setting `reels_follow_youtube` (default true). Standalone daily Shorts, Ten Tongues and Shorts without a scheduled YouTube row behave as before.
- `fb_insights`: tries `video_insights` Reel play metrics and keeps the larger of that and the object field; logs the missing-permission message once per video so the owner sees it.
- `scripts/growth_snapshot.py`: the measurement above, rerunnable.
- Tests: `tests/test_captions.py` (8 tests). Full suite: 388 passed.

Not touched: bank/stockpile workflow, render, common.py, workflows. Already banked bundles keep their 110-150-word Shorts; new bank runs produce the shorter format.

### What should move, and by when (judge in round 2, on or after 2026-11-19; better 2026-11-23)

| metric | now | expect by round 2 | means |
|---|---|---|---|
| Shorts median retention (YouTube `ctr` column) on Shorts produced after 2026-11-16 | 36-58 % | 65 %+ | hook/length change works |
| Shorts still gaining views on day 3+ | none | at least one per channel | second wave earned |
| Instagram median views, futurework and tradewinds | 19 / 5 | 60+ | spacing + captions work |
| Instagram comments | 0 | any | question line works |
| Facebook plays (now measured) | 2 total across 85 Reels | any movement | Page needs followers first; low priority |
| YouTube Short comments | 0 | a few | closing question works |

Only Shorts whose content id date is after 2026-11-16 count; older queued Shorts (57 scheduled) carry the old scripts and only get the new descriptions when uploaded by the drain.

### Done by the agent on 2026-11-16 (no owner login needed)

- Facebook measured for real: `read_insights` added to the Meta app's Pages use case, new user token generated (owner clicked the consent popup), long-lived Page tokens exchanged and written to `.env` for all four Pages. Result: 85 Reels across the three Pages have 2 plays in total (1 futurework, 1 tradewinds, 0 escapevelocity). Facebook delivers nothing to Pages with no followers; the Reels there are free but worthless until the Pages have an audience. Keep posting (no cost) but judge growth on YouTube and Instagram only.

- `yt_description_links_enabled` and `cross_mentions_enabled` set to `true` in settings; hub links go into new YouTube descriptions and sister-account mentions switch on after three unmentioned Reels per account.
- `instagram_handle` filled for all three explainer channels from the API (`futurework.explained`, `tradewindsreport`, `escapevelocitydaily`).

- Community posts published 2026-11-16 on all four channels from the browser, each with the latest long video's closing question and link (Future Work: buyout list; Trade Winds: tariff ruling prices; Escape Velocity: asteroid suspects; Ten Tongues: bread). Repeat per long video.
- Comments: the only two in the database are the owner's own test comments, already answered. Nothing to reply to yet.
- Instagram Stories cannot be created from the desktop web app, so Reel-to-Story shares stay a phone task.

### Owner-only levers (one line each)

- Run the `gh secret set` block from the 2026-11-16 chat so GitHub Actions uses the new Facebook tokens (the agent's secret write was blocked by the permission classifier).
- Ten Tongues phone verified 2026-11-16 (custom thumbnails now allowed).
- Reply to every comment by hand for the first weeks and pin one: the engage job drafts replies but early comment velocity is a ranking signal the owner can supply faster than a 6-hourly cron.
- Instagram: post one Story per Reel (all three accounts are already creator accounts, verified via the API 2026-11-16): the app surfaces Reels to followers through Stories, which the API cannot do.
- YouTube Community posts: the agent can post them from the browser pane each round; ask for it with "community posts".
- Subscribe the three channels to each other and like each other's Shorts from the owner account once; a single early engagement helps the test pool on a brand-new channel.
- Consider hub articles as the Shorts "link in bio" on Instagram (one link per profile): set each profile's link to `https://hub.ammaad.online/c/<channel>`.

### Carry forward to round 2

- If retention moves but views do not, the next lever is the on-screen hook card (render) and a trimmed first 2 s of footage.
- If Instagram tradewinds stays under 20 median with spaced posting, inspect the account itself (shadow restrictions, missing professional category) rather than captions.
- Ten Tongues: judge after seven episodes; its Shorts are 10 per day on one channel, which is a different test from the explainer channels.
