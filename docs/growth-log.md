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
- Added later the same day: `tighten_shorts` in `pipeline/script.py`. The word budget was prompt-only and the model has overshot before (today's bank run, written on the old prompt, produced 119-126-word Shorts). Every child Short now logs its word count, and any over 110 words gets one small `short_tighten` call (glm-5.3-flash on LunaRoute, effort low, 1500 max tokens) that cuts it to 75-110 words while keeping the hook, the facts and the closing question. A rewrite outside 60-115 words or a failed call keeps the original; resumed saved scripts are never re-paid. Tests: `tests/test_tighten_shorts.py` (4). Suite: 398 passed.

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

### Facebook and hub push (2026-11-16, owner asked for a hard effort on both)

Facts first: the four Pages have 0 followers each and no website link; the hub has 25 published articles, Search Console shows 2 indexed and 24 "Discovered, currently not indexed" (sitemap submitted 2026-10-30, last read 2026-11-15, 31 URLs), 1 search click in 30 days.

- Shipped: `pipeline/publish/hub_share.py`. Every published hub article becomes a Facebook Page link post on its channel's Page: new articles right after saving (produce and banked release), older ones backfilled by sync one per Page per UTC day, newest first. Message = title, the article's quick answer (two sentences), the channel's comment question, the link, two niche hashtags. No model calls, idempotent via `fb_article_post_<id>` settings, gated by `fb_article_posts_enabled` (default true). First three posts went out by hand on 2026-11-16 (one per explainer Page). Tests: `tests/test_hub_share.py` (4).
- Done in the browser: requested Google indexing for 8 articles (layoffs, China Busan deal, October jobs report, NASA astronauts, asteroid 1998 KY26, Suez, Kenya rare earths, AI chips seized). Google stopped accepting after that, which matches its daily quota. 16 remain; repeat on later days ("index more").
- Tried and blocked: setting each Page's website to its hub channel page needs `pages_manage_metadata` (API) and the facebook.com About view in the pane has no edit control; Bing Webmaster Tools needs a Google sign-in and OAuth consent that I will not do on the owner's behalf.
- Expectation: Facebook Pages with zero followers will not grow from posts alone. The link posts give the Pages a feed that is not just Reels and give the hub its first inbound links, but follower count is the gate, and the only free lever for that is the owner inviting their own friends from each Page. Hub: indexing requests usually land within days; judge by indexed count and search clicks in round 2, not by views.

### Owner-only levers (one line each)

- Facebook: on each of the three explainer Pages, "Invite friends" from your personal profile (196 followers there). This is the one action that gives the Pages a starting audience; nothing in the pipeline can.
- Facebook: add `pages_manage_metadata` to the app's Pages use case and regenerate the token the same way as `read_insights`, or set Website = https://hub.ammaad.online/c/<channel> by hand in each Page's details.
- Bing Webmaster Tools: sign in with the Google account, "Import from Google Search Console", accept. One minute, and it also covers DuckDuckGo.

- Run the `gh secret set` block from the 2026-11-16 chat so GitHub Actions uses the new Facebook tokens (the agent's secret write was blocked by the permission classifier).
- Ten Tongues phone verified 2026-11-16 (custom thumbnails now allowed).
- Reply to every comment by hand for the first weeks and pin one: the engage job drafts replies but early comment velocity is a ranking signal the owner can supply faster than a 6-hourly cron.
- Instagram: post one Story per Reel (all three accounts are already creator accounts, verified via the API 2026-11-16): the app surfaces Reels to followers through Stories, which the API cannot do.
- YouTube Community posts: the agent can post them from the browser pane each round; ask for it with "community posts".
- Subscribe the three channels to each other and like each other's Shorts from the owner account once; a single early engagement helps the test pool on a brand-new channel.
- Consider hub articles as the Shorts "link in bio" on Instagram (one link per profile): set each profile's link to `https://hub.ammaad.online/c/<channel>`.

### Carry forward to round 2

- Round 2 check: grep bank/produce logs for `short ... words` and `tightened` lines to see how often the model overshoots and whether tightened Shorts hold retention as well as natively short ones.

- If retention moves but views do not, the next lever is the on-screen hook card (render) and a trimmed first 2 s of footage.
- If Instagram tradewinds stays under 20 median with spaced posting, inspect the account itself (shadow restrictions, missing professional category) rather than captions.
- Ten Tongues: judge after seven episodes; its Shorts are 10 per day on one channel, which is a different test from the explainer channels.


## Round 2: 2026-11-17

### Snapshot (last 30 days, public only; round 1 in brackets)

| platform | channel | kind | n | median views | views/day | retention % | zero-view |
|---|---|---|---|---|---|---|---|
| youtube | escapevelocity | short | 25 | 28 (26) | 3.4 | 36 | 0 |
| youtube | tradewinds | short | 27 | 45 (41) | 7.0 | 58 | 1 |
| youtube | futurework | short | 25 | 15 (15) | 1.5 | 39 | 2 |
| youtube | all | long | 28 | 2-7 | 0.2-1.0 | 11-27 | 4 |
| instagram | escapevelocity | short | 33 | 126 (126) | 9.9 | | 0 |
| instagram | tentongues | short | 9 | 107 | 107 | | 0 |
| instagram | futurework | short | 23 | 19 (19.5) | 1.5 | | 0 |
| instagram | tradewinds | short | 32 | 6 (5) | 0.8 | | 3 |
| facebook | all | short | 98 | 0 | 0 | | 96 |
| hub | | | | 71 views, 34 uniques (48 / ~20) | | | US 22 (was ~8) |

Nothing material moved in one day, as expected. Hub uniques and US visits roughly doubled after the Facebook link posts and indexing requests; six Facebook link posts (three by hand, three by sync's backfill) show 0 clicks so far.

### Diagnosis: why round-1 changes cannot show yet

- Every explainer channel had one YouTube upload per day scheduled through 2026-12-09, all produced before round 1. The scheduler placed four child Shorts on four consecutive days per long video while each channel makes three longs a week, so the backlog grew by five days every week. The shorter hook-first Shorts (now consistently 82-110 words in bank runs) would not have reached the public until December.
- Bank mode (until 2026-11-24) banks everything new; `banked_release_per_day` is unset, so releases only add to the end of that queue.
- A regression from round 1: child Reels now wait for the YouTube slot, and sync's follow-up then ran on a fresh runner without the mp4 (`No such file or directory` in sync 44033158218 for old Shorts with no `media_url`). It also tried to post Reels for Shorts that went public weeks ago.
- The YouTube quota ran out at 11:50 UTC today. Correction after the fact: the parent session's `scripts/remove_ai_label.py` made 107 `videos.update` calls (about 5,350 units) at that time to clear the synthetic-media label, and they are in the 7,380 logged. Playlists are not the cause. The remaining 80 videos (about 4,000 units) are cleared after the 08:00 UTC reset on 2026-11-18, so schedule compression is capped per sync run (`compress_schedule_max_per_run`, default 20 updates = 1,020 units) and both fit in one day. Normal days should settle around 2-3k units.

### Shipped in round 2

- Scheduler: the three explainer channels now use `shorts_same_day: true`, `shorts_spacing_hours: 4`, `max_youtube_per_day: 3` in channel.json. Child Shorts fill the parent's day (long plus two Shorts, then the next day at the Shorts hour), never spilling past midnight. Ten Tongues unchanged.
- `pipeline/publish/reschedule.py` + `scripts/compress_schedule.py`: re-slots every future, non-public YouTube publication of a channel under the new calendar in its original order and pushes the new `publishAt` to YouTube (51 units each) and the database. Dry run today: futurework 18 uploads, last slot 2026-12-02 -> 2026-11-22; tradewinds 21, 2026-12-03 -> 2026-11-23; escapevelocity 26, 2026-12-09 -> 2026-11-28. The apply hit Google's quota wall at the first update, so sync now runs `compress()` every six hours (setting `compress_schedule_enabled`, default true) and stops cleanly on quota errors; the backlog moves as quota allows, starting after the 08:00 UTC reset.
- Reels follow-up: restores media through the existing retry/queue paths, skips Shorts with no media on the runner instead of raising, and only follows Shorts whose YouTube copy went public in the last 7 days.
- Tests: `tests/test_reschedule.py` (2), same-day scheduler test, Reels follow-up regression test. Suite: 410 passed.

### What should move by round 3 (2026-11-21 or later)

| metric | now | expect |
|---|---|---|
| explainer uploads going public per channel per day | 1 | 2-3 within a week (watch `compressed schedule` lines in sync logs) |
| days until the hook-first Shorts are public | ~20 | 5-9 |
| Reels follow-up errors in sync | several per run | 0 |
| Facebook link-post clicks (6 posts) | 0 | still ~0 until Pages have followers |
| hub uniques / 30 days | 34 | 60+ once 24 articles are indexed |

### Carry forward / owner

- Sign in to Google in the browser pane again (it came back signed out) so I can request indexing for the remaining 16 articles, 8 a day.
- Decide whether to release banked bundles before 2026-11-24 (`banked_release_per_day` = 1 per channel) now that the calendar can absorb 2-3 uploads a day.


## Round 2b: hooks and SEO research, 2026-11-17 (owner: "are you even trying")

### What our own 72 public Shorts say

| retention bucket | n | median views |
|---|---|---|
| under 35% | 26 | 16.5 |
| 35-50% | 16 | 16.5 |
| 50-70% | 17 | 52 |
| over 70% | 13 | 69 |

Retention is the only trait that correlates with views (r = 0.18; words, title length, numbers and questions in titles are all near zero). Every top-ten Short names a concrete thing in its first sentence (Swift, Starship, Artemis, a $20 billion bill, a 342 percent freight rise). Every bottom-ten Short opens on an abstraction (a Dutch budget, "here's an unpopular take", "your old job might come back", a door latch). Long videos: titles are clever, not searchable ("The Catch Isn't the Real Test"), so they get 2-8 views with no search entry.

### What the research says (vendor blogs, no official YouTube numbers; treat thresholds as rough)

- Shorts: distribution is a staged test; the first filter is swipe-away in the first 2-3 seconds, the second is completion (65% for under-30 s, 50% for 30-60 s). Faceless Shorts autoplay muted, so the first frame must state the topic in text. Loops add replays. Sources: [ContentMatch](https://contentmatch.io/youtube-shorts-algorithm-viewed-vs-swiped-ratio-2026/), [virvid](https://virvid.ai/blog/first-3-seconds-hook-faceless-shorts-2026), [1of10](https://1of10.com/blog/youtube-shorts-analytics/), [socialync](https://www.socialync.io/blog/youtube-shorts-algorithm-2026), [vidIQ hooks](https://vidiq.com/blog/post/viral-video-hooks-youtube-shorts/).
- Long-form SEO: keyword in the first 40 characters of the title, keyword in the first sentence of the description, chapter labels as search phrases, tags nearly irrelevant. Sources: [vidIQ](https://vidiq.com/blog/post/youtube-seo/), [outlierkit](https://outlierkit.com/resources/youtube-seo/).
- Instagram: Trial Reels are the non-follower lever (needs a professional account with enough followers; not exposed in the Instagram Login API), keyword in the first 125 caption characters, said aloud and shown on screen; cover frame matters. Sources: [Hootsuite](https://blog.hootsuite.com/instagram-reels/), [brandID](https://brandid.app/blog/instagram-trial-reels/), [Toptal](https://www.toptal.com/creator/post/instagram-seo).
- Facebook: single-digit Reel views on a Page usually means a "not recommended" flag (check Meta Business Suite > Account status), links in captions, or a cold-start Page with no engagement history. Sources: [lilachbullock](https://www.lilachbullock.com/facebook-reels-not-getting-views/), [advertiserreview](https://advertiserreview.com/social-media/facebook/reels-not-showing/).

### Shipped

- Hook card: every explainer Short now opens with its hook title burned in as a bold boxed headline in the upper third for the first 2.5 s (`pipeline/render.py`, `hook_text`), clear of the action rail and the centred captions; one drawtext per line because ffmpeg 8 draws newlines as missing glyphs. The same frame is the Instagram cover (thumb offset 2 s) and the Facebook Reel cover. Verified on real frames.
- Prompts: `hook_title` under 45 characters naming the subject (proper noun or number) in its first three words; long-video title starts with the searchable subject inside 40 characters, then the angle; description's first sentence states the subject plainly; chapter labels are search phrases. Ideation now prefers topics with a nameable actor plus a hard number, because that is what the top ten have and the bottom ten lack.
- Reels captions already lead with the spoken hook line, carry no links and use niche hashtags (round 1); Facebook Reels get the same caption.

### Not possible from here (owner)

- Instagram Trial Reels: toggle "Trial" when posting from the app; the API we use has no such flag. Run two or three a week per account.
- Facebook: open Meta Business Suite > Account status for each Page and tell me if any says "not recommended"; and invite friends to the Pages. Zero followers plus no engagement history is a cold start nothing automated can fix.
- YouTube Studio: for the next Shorts, read "Viewed vs swiped away" and "Stayed to watch"; I cannot read those through the API.

### Expect

Hook card plus named-subject rules target the 2-second swipe and the 50% retention line. If the next 20 Shorts median above 50% retention, median views should move from the teens to 50+ per the table above, before any algorithmic expansion. 10k a day per video needs the expansion stage; that is a retention problem first, and this is the first round that attacks the muted first frame directly.


## Round 3 check-in: 2026-11-18

Owner: no difference in analytics. Correct, and expected: nothing shipped on 2026-11-16/17 had reached a public video yet. Nine videos went public since 2026-11-17, all rendered and uploaded before round 1 (views 0-95; the 95 is Escape Velocity's "Starlink Dies in Five Years, On Purpose", the one title with a hard named subject). Already-uploaded videos cannot have their file replaced, so the backlog going public this week performs like the old format regardless.

- Schedule compression ran from sync: Future Work's last slot moved 2026-12-02 -> 2026-11-25, Escape Velocity 2026-12-09 -> 2026-11-28, Trade Winds mostly moved (one straggler on 2026-12-03 waits for the per-run cap). All three channels now have 2-3 uploads a day through 2026-11-24.
- Banked bundles were rendered before the hook card existed. Commit 21bcc05: release now burns the card onto each banked Short (one ffmpeg re-encode, audio copied) before upload, so bundles released from the next sync carry it.
- Dispatched one public produce run per explainer channel (new scripts, subject-first titles, hook card, same-day Shorts) so the first fully new-format bundles go public at the next cron slots (2026-11-19/20) rather than after the bank.
- First readable signal: 2026-11-21 (48 h of public life on card-bearing Shorts). Compare "Viewed vs swiped away" in Studio and retention via `scripts/growth_snapshot.py` for Shorts published on/after 2026-11-19 against the round-2b table.


## Thumbnail audit, 2026-11-19 (owner: "why are thumbnails not working, where is CTR")

### Findings

- Escape Velocity's channel returns `longUploadsStatus: eligible` (Future Work, Trade Winds, Ten Tongues: `allowed`). "eligible" means the channel has not completed phone verification, and YouTube rejects `thumbnails.set` on unverified channels. Every Escape Velocity long video has therefore carried an auto-picked frame, including one with a burned caption, and the code only logged a warning. This should have been caught at channel setup; it was not.
- Future Work and Trade Winds do get our custom thumbnails, and they are weak: a random stock frame plus three vague words ("NOT SO SAFE", "WHO KEEPS IT") that name nothing. Research consensus (vidIQ's 2026 study of 500 breakout videos, several design guides): 1-5 words that say what the video is about, one dominant element, high contrast. Sources: [vidIQ thumbnail tips](https://vidiq.com/blog/post/youtube-thumbnail-tips/), [vidIQ CTR designs](https://vidiq.com/blog/post/youtube-custom-thumbnails-ctr/), [awisee stats](https://awisee.com/blog/youtube-thumbnail-best-practices).
- Ten Tongues uses a typographic card: fine as is.
- Click-through rate: not available in the YouTube Data or Analytics API (only averageViewPercentage is; that is what the `ctr` column holds). Impressions and CTR exist only in YouTube Studio's Reach report. Reading them per channel is a browser job and needs the owner signed in to Google in the browser pane.

### Shipped

- Thumbnail failures are now errors with the API reason, and the rejected image is kept in Storage (`thumbs/<video id>.jpg`) with a `yt_thumbnail_pending_<video id>` setting. Sync retries `thumbnails.set` for each channel (50 units each, reserved) and clears the row on success, so the moment Escape Velocity is verified its scheduled uploads get their thumbnails without re-rendering. Already-public Escape Velocity longs keep their auto frames (their thumbnails were not retained).
- New thumbnail design (`pipeline/thumbnail.py`): text is 2-5 words that name the subject and/or the number (prompt rule; "never a vague teaser"), set large in up to three lines with the last line in the channel accent, over the sharpest clean frame (edge/contrast score with a penalty for single-hue placeholder cards), with the left 60% darkened and an accent bar. Verified on real frames.
- Tests: `tests/test_thumbnail_design.py` (3). Suite: 423 passed.

### Owner

- Verify Escape Velocity's phone in YouTube Studio (same steps as Ten Tongues on 2026-11-16). Until then no custom thumbnail can be set on that channel.
- Sign in to Google in the browser pane so I can read Reach (impressions, CTR) per channel and log it in round 3.


### Studio Reach, read 2026-11-19, all five channels (last 28 days unless noted)

| channel | long impressions | long CTR | long views / AVD | long traffic | Shorts stayed / swiped | Shorts views (engaged) |
|---|---|---|---|---|---|---|
| Future Work Explained | 600 | 4.7% | 105 / 1:51 | search 35%, direct 18%, browse 18% | 47.7% / 52.3% | 464 (214) |
| Trade Winds Report | 680 | 2.1% | 74 / 2:21 | browse 58%, search 34% | 58.4% / 41.6% | 1.6K (903) |
| Escape Velocity | 1.4K | 1.3% | 74 / 2:01 | search 66%, suggested 20% | 40.4% / 59.6% | 2.8K (1.1K) |
| Ten Tongues | 357 | 0.8% | 4 / 1:39 | suggested 75% | 35.1% / 64.9% | 917 (340) |
| Frame and Argument | first video, 1 day | 0.6% | 19 / 0:42 | | | |

Reading:
- Click-through: Future Work's 4.7% is the only normal number; Trade Winds 2.1%, Escape Velocity 1.3% (never had a custom thumbnail: verified today 2026-11-19, `longUploadsStatus` now `allowed`, sync retrying pending thumbnails), Ten Tongues 0.8% and Frame and Argument 0.6% are failing. Ten Tongues' typographic card gets impressions from Suggested but nobody clicks a word on a dark gradient; it needs the same subject-first treatment with the word's translations visible, which is a separate change.
- Impressions are tiny everywhere (357 to 1.4K a month). Titles and thumbnails only matter once a video is shown; the long videos are barely shown at all, and what shows comes mostly from search and browse, so keyword-first titles are the right fix.
- Shorts: only Trade Winds clears 50% stayed-to-watch; Ten Tongues (35%) and Escape Velocity (40%) lose most viewers in the first seconds. Escape Velocity still has the most Shorts views because space topics are named things. The hook card and subject-first hook titles target exactly this column; judge again on 2026-11-21.
- Ten Tongues Shorts: four of the top five are Japanese, Russian, Italian and Urdu. Language-specific Shorts find a language-specific audience; the English long episode (4 views) does not.


### Thumbnail backfill, 2026-11-19

- Escape Velocity verified by the owner (API now reports `longUploadsStatus: allowed`).
- `scripts/backfill_thumbnails.py --channel <key> [--apply]`: for every scheduled private long video, one small model call writes 2-5 subject/number words plus a stock-image query, a frame is fetched through the normal footage providers (the rendered video is not on this machine), the new design is rendered and `thumbnails.set` is called (50 units each). Applied to Escape Velocity, Future Work and Trade Winds; Ten Tongues' three scheduled episodes got the new card (word large on the brand colour, three translations large in their own scripts on the dark panel; the old dark gradient with six tiny chips had 0.8% CTR).
- Judge: Studio CTR per channel on 2026-11-26 against today's table (FW 4.7%, TW 2.1%, EV 1.3%, TT 0.8%).


## Round 3: 2026-11-23 (owner target: 10,000 views per long video, 40,000 per Short)

### Scoreboard (YouTube API, all public uploads; `scripts/yt_scoreboard.py`)

| channel | kind | n | median views | best | best as % of target | median % viewed |
|---|---|---|---|---|---|---|
| futurework | long | 14 | 8 | 25 | 0.25% | 16 |
| futurework | short | 45 | 10 | 92 | 0.23% | 38 |
| tradewinds | long | 11 | 1 | 59 | 0.59% | 12.5 |
| tradewinds | short | 42 | 21 | 265 | 0.66% | 53 |
| escapevelocity | long | 11 | 4 | 27 | 0.27% | 10 |
| escapevelocity | short | 45 | 24 | 620 | 1.55% | 37.5 |
| tentongues | long | 6 | 3 | 30 | 0.3% | 42 |
| tentongues | short | 59 | 24 | 799 | 2.0% | 40 |

Honest distance: the best video on the network is at 2% of its target; no video is within 50x. Frame and Argument skipped (no channel.json key for the scoreboard yet).

### Diagnosis

- The network's top Shorts are Ten Tongues per-language words (Rice/Tea in Russian 799/576, Bread in Japanese 459, Tea in Portuguese 389): 27-35 s, titles that match what people type. Explainer Shorts run 48-54 s and median 10-24 views.
- Long videos get almost no impressions; what they get is mostly search. Titles that match real search phrasing are the only free lever there.
- Newest Trade Winds Shorts (first card-bearing ones) are at 27-40 views inside one day against a channel median of 21: too early to call, but the right direction.

### Shipped

- `pipeline/search_demand.py`: YouTube autocomplete (free, keyless) as a demand signal. Ideation sees a relevance-weighted demand score per headline (completions that extend a specific 2-3 word phrase from it; "starship flight 15" 70, "strait of hormuz" 50, abstract policy headlines 0) and prefers searched subjects when candidates are close. The script prompt gets up to eight real search phrases and must use one near the start of the main title and one Short hook_title where it fits honestly. Fails soft; tests never touch the network.
- Shorts length experiment: of each video's four Shorts, 1 and 3 are QUICK (50-70 words, about 20-28 s, loop ending) and 2 and 4 STANDARD (75-110 words). `tighten_shorts` enforces each budget. The scoreboard records duration, so the loop compares under-30 s against 35-45 s Shorts directly.
- `scripts/yt_scoreboard.py`: read-only scoreboard from the YouTube API (no Supabase), saved to `data/scoreboard/<date>.json` for trend lines.
- Tests: `tests/test_search_demand.py` (5). Suite: 429 passed.

### Loop

From today the growth loop runs every 6 hours as a scheduled task: scoreboard, compare with the previous snapshot, change one thing with evidence, test, commit, log here. Owner actions live in the growth to-do artifact.

- Owner to-do list: https://claude.ai/artifact/MYKD1Jzf9dJqPdSsHcEnbZ (source `docs/growth-todo.html`; tasks in its `todos` collection, scoreboard in `meta/scoreboard`). The owner ticks items; the loop reads them and adds new ones only for genuinely owner-only work.
- Scheduled task `growth-loop-6h` (Claude app, every 6 hours at :15 local) runs the loop. It runs while the app is open and catches up on next launch.
- Browser pane lost its Google sign-in again (2026-11-23), so today's indexing batch and Studio reads wait for the owner to sign in (to-do item 'Sign in to Google in Claude's browser pane').

- 2026-11-23 later: owner signed in to Google in the pane. Search Console: indexed pages 2 -> 11 since the first indexing requests (19 discovered-not-indexed, 1 crawled-not-indexed). Requested indexing for 8 more articles (nist-voluntary-ai-guidance, why-shipping-one-container, webb-3i-atlas, ai-spending-and-jobs, esa-hera, ai-layoff-rehire, us-canada-50-percent-tariff, how-to-spot-fake-job-postings). Two left for tomorrow: the long-slug starship-flight-15 and dutch-government articles.
- Thumbnail backfill applied to every scheduled long video: Escape Velocity 5, Future Work 7, Trade Winds 5 (17 thumbnails, 50 units each), all subject-first ("STARSHIP'S 3 GATES", "GOLDMAN: LAYOFFS DELAYED", "HORMUZ WAR RISK", "$463M NO SALE"). Judge CTR in Studio Reach from 2026-11-30 against FW 4.7%, TW 2.1%, EV 1.3%.
- 2026-11-23: owner confirmed all five Facebook Pages active after the 19 Nov lock. Invited friends from all five Pages in the browser (8 eligible friends each; Facebook offers only friends, not the profile's ~196 followers). Expect at most a handful of Page likes; Facebook reach still depends on Reels watch time.
- 2026-11-23: Bing Webmaster Tools set up at the owner's request: signed in with Google, granted view-only Search Console access, imported https://hub.ammaad.online/ with its sitemap (covers Bing, DuckDuckGo, Yahoo). New articles already ping IndexNow (pipeline/article.py), which Bing reads.
- 2026-11-23: pages_manage_metadata added to the Meta app's Pages use case (Ready for testing). Graph API Explorer prepared with 12 permissions. Owner still has to generate the user token (consent popup), run scripts/meta_page_env.py --all and update the five META_* secrets; then the loop can set each Page's website to https://hub.ammaad.online/c/<channel>.
- 2026-11-23: owner refreshed the five Page tokens (scripts/meta_page_env.py --all). pages_manage_metadata verified: Page websites set to the hub channel pages for Future Work, Trade Winds and Escape Velocity; Ten Tongues kept https://www.youtube.com/@tentongues (no hub channel page, /c/tentongues is 404).


## Loop run: 2026-11-23 12:08 UTC

### Scoreboard (`data/scoreboard/2026-11-23T12.json`)

| channel | long n / median / best | short n / median / best | median % viewed (long / short) |
|---|---|---|---|
| futurework | 14 / 8 / 25 | 45 / 11 / 92 | 16 / 38 |
| tradewinds | 11 / 1 / 59 | 42 / 21 / 265 | 12.5 / 53 |
| escapevelocity | 11 / 4 / 27 | 45 / 24 / 620 | 10 / 37.5 |
| tentongues | 6 / 3 / 30 | 63 / 23 / 846 | 42 / 40 |
| filmreview (Frame and Argument) | 1 / 73 / 73 | 4 / 97 / 407 | 12 / 26.5 |

Since this morning's round 3: "Rice in Russian" 799 -> 846 (best on the network, 2.1% of the Short target); four new Egg Shorts and the Egg long episode are under a day old (0-1 views). Trade Winds' newest Short ("The Queue Costs More Than the Tax") is at 60 views/day in its first 12 h, three times the channel median. Nothing is within 47x of target.

Frame and Argument is in the scoreboard from today (commit 797b7e3, `channel_for()` uses `FilmReviewChannel`). After four days it is, per video, the network's strongest channel: its single long recap (73 views) beats every other channel's best long video, and its Shorts median (97) is four times anyone else's; best "Heartland: The Confession That Broke Nashville" 407 at 31 s. Small samples (n=1 and n=4), but the direction is clear. Rows added to the owner's to-do scoreboard.

### Shipped

- 8b5f404 Ten Tongues on the hub. `pipeline/words_article.py` builds one article per published episode from `content.qa_notes.words_episode` with no model calls: "RICE in 10 languages" with a word table (native script, romanisation, IPA), an example-sentence table, one "How to say rice in <language>" section per language (memory hook, usage note), the YouTube embed and a search-shaped FAQ ("How do you say rice in Russian?", Japanese, Spanish, Hindi, French: the languages whose Shorts draw most). New episodes get theirs after a successful upload (`words.py`). Scheduled episodes are dated at the video's `publishAt`, so the hub shows the article when the video goes public; Facebook article shares now skip not-yet-live articles (the backfill sharer picked newest first and would have posted a 404 link). The hub lists Ten Tongues, the About page names four channels, and Instagram links use each channel's real `instagram_handle` (they used the YouTube handle, which is wrong for all four).
- Backfilled 8 articles: bread, milk, tea, coffee, rice, salt, egg (live) and fruit (live 2026-11-24 07:00 UTC). https://hub.ammaad.online/c/tentongues now returns 200; Ten Tongues' Facebook Page website set to it via the Graph API (verified).
- Tests: `tests/test_words_article.py` (7). Suite: 440 passed.

### Not done, and why

- Indexing requests for the Ten Tongues articles: today's 8 were used this morning. Next run (2026-11-24): starship-flight-15, dutch-government, then the rice, tea and bread articles (the words with the strongest Shorts).
- Quick vs standard Shorts: the experiment started today, so no side has public Shorts older than 48 h. Judge from 2026-11-26.
- `retry` workflow runs failed today on old Instagram/Facebook publications whose media is gone (`media_not_recoverable`); expected and harmless, dispatched by another session. The 11:34 bank failure is left to the stockpile session.

### Measuring

- Ten Tongues hub articles: impressions and clicks in Search Console from 2026-11-30 for "how to say <word> in <language>" queries.
- Frame and Argument: whether the Shorts median holds as n grows past 10.


## Loop run: 2026-11-23 13:23 UTC

### Scoreboard (`data/scoreboard/2026-11-23T13.json`)

| channel | long n / median / best | short n / median / best |
|---|---|---|
| futurework | 13 / 8 / 25 | 46 / 10 / 92 |
| tradewinds | 11 / 1 / 59 | 42 / 21 / 265 |
| escapevelocity | 11 / 4 / 27 | 47 / 24 / 620 |
| tentongues | 6 / 3 / 30 | 64 / 25 / 922 |
| filmreview | 1 / 73 / 73 | 4 / 97 / 407 |

Since 12:08: "Rice in Russian" 846 -> 922 (2.3% of the Short target, still the best on the network). "Egg in French" reached 61 views in its first ~5 h (244/day), the fastest start of any Ten Tongues Short. Best long is still Frame and Argument's 73 (0.7% of target). One-off items A and B from the owner's 2026-11-23 brief were both already committed (797b7e3, 8b5f404).

### Finding: Ten Tongues language order is confounded with posting hour

Median views per Ten Tongues Short by language (7 words, n=6-8 each): Russian 239, Japanese 127, Italian 118, then Urdu 29, French 28, Spanish 24, Hindi 21, Mandarin 14, Bengali 12, Portuguese 11. Children post hourly in a fixed order from 09:00 UTC (Mandarin 09, Hindi 10, Spanish 11, French 12, Bengali 13, Portuguese 14, Russian 15, Urdu 16, Japanese 17, Italian 18). The three winners are three of the last four slots, so "Russian learners" and "15-18 UTC is a better hour" cannot be told apart from this data.

### Shipped

- c742e04 `rotate_shorts_order` (channel.json, on for Ten Tongues): child Shorts' slot order shifts by one each day (keyed on the parent's publish date), so over ten days every language takes every hour once. Reschedule/compress keeps the order because it sorts by existing `publish_at`. Test in `tests/test_schedule.py`; suite 443 passed.
- Community posts (browser, owner-approved): Future Work "Pilot or funded?" (closing question + link) and Ten Tongues EGG. Escape Velocity's Starship video goes public at 16:00 UTC; post it next run.

### Not done, and why

- Indexing requests: today's 8 were used this morning. Next UTC day: starship-flight-15, dutch-government, then /c/tentongues and the rice, tea, bread, egg, salt articles.
- The scheduled task prompt still contains the 2026-11-23 one-off block (A, B); removing it needs an approval the unattended run cannot give. Both items are done, so later runs should skip it.
- Two `recap` regenerate runs failed at 13:16 ("Project not found in approve/ or review/"): a dispatch for a project that is not in Drive, started by another session; not a code fault.

### Measuring

- Rotation: from the next Ten Tongues episode (2026-11-24 onward), compare views at 48 h by posting hour vs by language. Judge on 2026-12-04 (10 rotated episodes). If hour dominates, move `shorts_hour_utc` to the winning window; if language dominates, give Russian/Japanese/Italian the best slots and test a second Short format for them.
- Quick vs standard Shorts: judge from 2026-11-26.


## Loop run: 2026-11-23 19:25 UTC

### Scoreboard (`data/scoreboard/2026-11-23T19.json`, deduplicated)

| channel | long n / median / best | short n / median / best |
|---|---|---|
| futurework | 13 / 8 / 25 | 42 / 10 / 92 |
| tradewinds | 11 / 1 / 59 | 43 / 21 / 265 |
| escapevelocity | 12 / 3.5 / 28 | 41 / 24 / 620 |
| tentongues | 6 / 3.5 / 30 | 69 / 27 / 921 |
| filmreview | 1 / 73 / 73 | 4 / 103 / 416 |

Since 13:23: flat. "Rice in Russian" 921 (2.3% of the Short target) is still the best; best long is Frame and Argument's 73 (0.7%). New today: Escape Velocity "When Will Humans Fly on Starship? 3 Gates Left" (public 16:00, 0 views at 3 h), Future Work "Pilot or funded?" (1 view at 14 h), Trade Winds "Trace Your Avocado Tonight" (11 views in ~5 h, 44/day, twice the channel median).

### Shipped

- Scoreboard fix: the uploads playlist returned 23 Future Work videos twice (265 rows, 242 unique), inflating n and skewing medians (the 13:23 snapshot's FW long n flipped 14 -> 13 for the same reason). `channel_videos()` now dedupes ids before `videos.list`; `tests/test_yt_scoreboard.py`. Suite 445 passed. Earlier snapshots may carry duplicates; compare by unique id.

### Finding: the quick vs standard Shorts experiment cannot be judged on 2026-11-26

The explainer calendars are full of Shorts made before the experiment (released stockpile bundles and older productions). Every explainer Short going public today is 46-52 s. YouTube publications scheduled from now: Future Work runs to 2026-12-31, Trade Winds and Escape Velocity to 2026-12-05/07. The first QUICK Shorts (LinkedIn CEO episode, 56 and 63 words) go public on 2026-12-30. Ten Tongues Shorts are all 27-35 s, so they don't test length either. New judge date: early January, unless the backlog drains faster.

Candidate for the next run (not done unattended, because it moves ~40 scheduled `publishAt`s and costs quota): raise explainer `max_youtube_per_day` from 3 to 4 so the backlog of five-week-old news Shorts drains sooner and the experiment starts earlier. Weigh it against the quota (compress costs 51 units per moved video; the general reserve must hold).

### Not done, and why

- The browser pane is signed out of Google again (YouTube shows "Sign in", Search Console shows the landing page). Blocked: the Escape Velocity Community post, today's indexing requests (starship-flight-15, dutch-government, Ten Tongues rice/tea/bread/egg/salt) and the Studio Reach read. Owner to-do added: "Sign in to Google in Claude's browser pane again". Community post text, ready to paste: "So tell me, which gate do you think breaks first: refuelling, the Moon, or certification? https://youtu.be/xAxaTViQdSs"
- No owner to-do items were newly ticked since 13:23.
- Workflows: the only failure in the last 30 runs is the 16:43 `recap` run (another session's dispatch).

### Measuring

- Ten Tongues hour vs language rotation: judge 2026-12-04.
- Quick vs standard Shorts: first quick explainer Shorts go public 2026-12-30; judge in January (see above).
- Thumbnail CTR in Studio Reach from 2026-11-30 (needs the Google sign-in).


## Loop run: 2026-11-24 06:50 UTC (LunaRoute, headless — blocked run, honest report)

**This run could not measure, test, or commit.** The headless session's permission system blocked
every execution and write command: all Python (scoreboard, pytest), `gh run list`, `curl` to the
autocomplete endpoint, WebSearch/WebFetch, `git pull --rebase`, and even `git add`/`git commit`
required an approval nothing in this run could give. Only read-only file and git commands worked.
No scoreboard was taken; no claim below relies on numbers newer than the 2026-11-23T19 snapshot.
The code fix below is written to disk but **uncommitted and untested** — the next permissioned
run must run `PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest tests -q` and commit
`pipeline/publish/__init__.py` + `tests/test_short_long_link.py` (plus this log) if it passes.

### Finding (from code reading, not new measurement): queued parents were breaking the Short-to-long funnel link

`publish_short` resolves the `{LONG_URL}` placeholder only when the long URL is known at call
time. When the long upload queues (quota bucket or expired OAuth), every child Short goes to
YouTube later through the drain path, which used the DB description verbatim: explainer legacy
stubs went up with the literal text `{LONG_URL}`, and words-format Shorts had the placeholder
stripped to an empty string at production time (the DB row itself was overwritten), leaving
`Full episode, all 10 languages:` dangling with nothing after it. Both lose the only link from
a Short to its long video — the pinned backlog item "pinned comment or description link from
each Short to its long video" was already half-broken in the queue case.

Fix (working tree, not committed): `short_description` now keeps the placeholder when the URL
is unknown so the DB row stays resolvable; `_youtube_publish` resolves it from the parent's
publication row at upload time (no API call, no quota) or drops the unresolvable line; words
Reel captions never leak the placeholder to Instagram/Facebook. Tests: `tests/test_short_long_link.py`
(8 cases: drain resolution for explainer + words, drop-when-unresolvable, untouched normal path,
`parent_long_url`, placeholder persistence, Reel caption guard). **Not run — no Python available.**

### Scoreboard (stale: 2026-11-23T19 snapshot, unchanged since)

Best long: Frame and Argument recap 73 (0.7% of 10,000 target). Best Short: "Rice in Russian" 921
(2.3% of 40,000). Ten Tongues per-language Shorts remain the network's strongest median (27 vs
10-24 elsewhere). No video on any channel is within 40x of target.

### What a browser-capable / permissioned run should do next (in order)

1. Run the test suite; if green, commit and push the fix above (files are already in the working tree).
2. Take the scoreboard (`scripts/yt_scoreboard.py`) — last snapshot is 11 h old; compare the 2026-11-23
   egg/salt/rice Shorts at ~1 day old (Egg in French was 124 views at 5 h, 401/day — the fastest
   Ten Tongues start yet; check whether it held).
3. Search Console: request indexing for starship-flight-15, dutch-government, then the Ten Tongues
   rice, tea, bread, egg, salt articles (8/day cap; none requested since 2026-11-23 morning).
4. YouTube Studio Reach (impressions, CTR, stayed-to-watch) for all five channels via the account
   switcher; log them here. Escape Velocity needs its phone verified first (owner to-do).
5. Community post for the Escape Velocity Starship video (text ready in the 2026-11-23 19:25 entry),
   plus a post for the 2026-11-24 episodes if any went public.
6. `gh run list --limit 30`: check produce/shorts/words overnight runs; the words run (03:30 UTC)
   should have produced the 2026-11-24 episode — confirm it published and its Shorts' descriptions
   now carry real links (this fix's first live test if the parent had queued).

### Measuring

- Ten Tongues hour vs language rotation: judge 2026-12-04 (unchanged).
- Quick vs standard Shorts: first quick explainer Shorts 2026-12-30; judge January (unchanged).
- After this fix ships: audit live Shorts' descriptions for `{LONG_URL}` or dangling `Full video:`/
  `Full episode` lines (a DB query for `description LIKE '%{LONG_URL}%'` on `status='published'`
  rows finds how many past uploads were affected; those can only be fixed by videos.update, which
  costs 50 units each — decide by count).
- Egg in French (fastest Ten Tongues start): whether the 401/day held past 24 h.


## Loop run: 2026-11-24 ~14:00 UTC (LunaRoute, headless — second blocked run; content-quality pass Q1/Q2/Q3 written, code prepared)

**This run could not execute or commit.** Same permission wall as the 06:50 run: every Python
invocation (scoreboard, pytest), `gh`, `curl`, `git add`/`git commit`/`push` required an approval
this unattended session could not give; only read-only file/git commands and the file tools worked.
No new scoreboard snapshot (last is `2026-11-23T19.json`; the analysis below uses it). The 06:50
fix (`pipeline/publish/__init__.py` + `tests/test_short_long_link.py`) is still uncommitted and
untested in the working tree; this run's changes are also on disk, uncommitted.
**Next permissioned run: run the suite once, then commit both batches** (file list at the end).

### Scoreboard (stale, from `2026-11-23T19.json`; unchanged snapshot)

| channel | long n / median / best | short n / median / best |
|---|---|---|
| futurework | 13 / 8 / 25 | 42 / 10 / 92 |
| tradewinds | 11 / 1 / 59 | 43 / 21 / 265 |
| escapevelocity | 12 / 3.5 / 28 | 41 / 24 / 620 |
| tentongues | 6 / 3.5 / 30 | 69 / 27 / 921 |
| filmreview | 1 / 73 / 73 | 4 / 103 / 416 |

Best long: Frame and Argument 73 (0.7% of 10,000). Best Short: Ten Tongues "Rice in Russian: ris"
921 (2.3% of 40,000). No video is within 40x of target.

### Content-quality pass — Q1: rank channels/formats (from the 2026-11-23T19 snapshot)

Per-video strength (median views): filmreview 103 > tentongues 27 > escapevelocity 24 >
tradewinds 21 > futurework 10 (Shorts). Average % viewed: tradewinds Shorts 53.5% is the best of
the explainers (bm_george, +0%), escapevelocity and futurework 38%, filmreview 26.5%, tentongues
40%. Longs: tentongues 42% > futurework 16% > tradewinds 12.5% > filmreview 13% > escapevelocity 10%.

Top 5 Shorts on the network (views; views/day where young): "Rice in Russian: ris" 921 (406/day),
"Tea in Russian: chay" 576 (138/day), "Bread in Japanese: pan" 459 (63/day), "The rescue didn't
doom Swift" 620 (51/day), "Salt in Japanese: shio" 406 (369/day, fastest start anywhere; "Egg in
French: oeuf" 124 in ~5 h, 401/day, same pattern). Best explainer Shorts after those: "Freight up
342 percent. Demand isn't." 265 (75% retention), "Only 5 Starship Launches This Year?" 384 (64%),
"Starlink Dies in Five Years, On Purpose" 120 (60%), filmreview "Heartland: The Confession That
Broke Nashville" 416 (206/day).

Bottom Shorts (views): "Where can a falling telescope land?" 3, "Voyager's silences aren't
mysterious" 8, "The Small Rocks Are the Dangerous Ones" 10, "Nobody Lost the Pipe" 7, "The
savings target came before the AI plan" 2, plus futurework's concept batch ("Being Right Is No
Longer Enough" 4, "The Two Column Job Check" 1, "Connecticut Is Counting. So Should You" 1).
Scripts live in the DB; the titles carry the pattern, which is the actionable part.

### Q2: what winners do differently (now written into persona/formulas.md and every style.md)

1. The exact search phrase in the first three title words, with the answer in the title.
   "Rice in Russian: ris": phrase + colon + answer. The answer being "spoiled" costs nothing;
   searchers type "how to say rice in Russian" and click the title that already confirms.
2. Winners open on a checkable fact, number, or named actor; losers open on a concept.
   "Four hundred thousand dollars per box" vs "Ignore the ban. Find the exemption."
3. Contradiction shape: fact, then flipped assumption. "Freight up 342 percent. Demand isn't."
   "Teams wasn't hacked. That's the problem." "Starlink Dies in Five Years, On Purpose."
4. Gerund/adjective-led titles underperform everywhere ("Being Right...", "Ignore...", "Find...").
   Banned in prompts now.
5. Duration: winning Shorts are 26-35 s (words) and 31-50 s (explainers); every 60 s+ Short
   underperforms. (The quick/standard experiment still starts 2026-12-30; the backlog is full
   of pre-experiment Shorts.)
6. Voice/pace: channels whose winners hold 40-75% (tradewinds bm_george +0%, tentongues af_bella
   -4%) speak at or below 1.0x; the two +rate channels (futurework +4%, escapevelocity +2%) hold
   38%. Correlation, not proof; the A/B below tests it.

### Q3: voice decisions (playbook item 34, one channel first)

- A/B started: escapevelocity. Worst long retention (10%) and low Shorts retention (38%). Its
  style.md now requires the first sentence of every video/Short to be slower and punchier (under
  ten words, number or mission name last); the body keeps its quick bursts. Judge at 48 h per
  video against the 2026-11-23 baseline from 2026-12-01. If Shorts move 38% to 45%+ and longs
  10% to 14%+, extend to futurework; if flat, revert and try Kokoro rate +2% to -0% instead
  (needs the permissioned run; render tests exist).
- tradewinds (+0%, 53.5%, best explainer retention) and tentongues (-4%, 40%) unchanged: no
  evidence supports touching the network's two best-retaining voices.
- futurework am_michael +4% (38%): hold until the escapevelocity A/B reads.

### Shipped this run (written to disk; commit pending a permissioned run)

- persona/formulas.md: six-block spine (playbook items 1, 6, 11, 12) replacing the five-part
  sequence, with strongest-evidence-before-40% and framework-by-0:40; new "Title rules that
  separate winners from losers" and voice-delivery sections from the Q2 findings.
- channels/{futurework,tradewinds,escapevelocity,tentongues,filmreview}/style.md: per-channel
  "Network findings 2026-11-24" sections, kept distinct per the inauthentic-content rule;
  escapevelocity carries the voice-pacing A/B (item 34).
- pipeline/script.py: prompt enforces the six-block spine, named-actor-or-number in the first
  40 words, "title/hook/thumbnail state the same claim" (items 2, 4), two attributed quotes in
  the evidence block (item 5), gerund/adjective title ban; new `opening_names_actor_or_number()`
  warning (item 1's measurable half; a warning, not a reject, so a paid script is never stranded);
  the hook-rewrite prompt now demands the same claim and the 40-word rule.
- pipeline/shorts_daily.py: the same claim-first, searchable-subject, no-gerund rules in the
  daily prompt and the DAILY_SCHEMA hook_title description.
- pipeline/ideate.py: topic rubric (viral potential, brand fit, series potential, production
  feasibility; item 9), rising-not-saturated (item 7), and the required "what everyone else
  missed" own-angle clause (item 8).
- tests/test_content_quality.py: 9 tests (validator behavior including spoken-number and
  sentence-start handling; prompt content pinned so a refactor cannot silently drop the rules).

Note: `tests/test_reels_follow_speed.py` was modified by another session during this run (a
follow_youtube_to_reels skip-quietly test); left untouched and out of both commit batches.
`scripts/tmp_failed_inventory.py` (untracked, owner-approved inventory script from the 06:50
session) also left as-is.

### Files for the next permissioned run to commit (after the suite passes)

Batch A (06:50 run): `pipeline/publish/__init__.py`, `tests/test_short_long_link.py`.
Batch B (this run): `pipeline/script.py`, `pipeline/shorts_daily.py`, `pipeline/ideate.py`,
`persona/formulas.md`, `channels/{futurework,tradewinds,escapevelocity,tentongues,filmreview}/style.md`,
`tests/test_content_quality.py`, `docs/growth-log.md`.
Pre-existing working-tree changes (`.gitignore` .env.* line, `AGENTS.md` tradewinds-locked note,
`docs/growth-log.md` up to the 06:50 section) belong to the earlier run; include them in the
same push since they are the same workstream.

### Playbook items (all 35; running table)

| # | Item | Status |
|---|---|---|
| 1 | Six-block spine; first-40-words named actor/number | applied (f93a328): six-block spine in the script prompt; warning-only first-40-words check |
| 2 | Hook = "[Actor] just [verb] [number]"; hook card = first spoken sentence | applied (f93a328): hook prompt + hook card = first spoken claim |
| 3 | Thumbnail: subject+object, <=3 words, strong verb, tone colour | applied (this commit): thumbnail_text 2-3 words with a strong verb or key number; design from 2026-11-19 |
| 4 | Title "[claim], [authority] just confirmed it"; same claim in title/hook/thumbnail | applied (f93a328): claim-first title pattern; title, first sentence and thumbnail state one claim |
| 5 | Two attributed quotes/excerpts in the evidence block | applied (f93a328): two attributed quotes in the evidence block |
| 6 | Context beat right after the hook | applied (f93a328): context beat after the hook |
| 7 | Recency scan; rising-not-saturated preference | applied (f93a328): rising-not-saturated rule in ideation; news fetched every run |
| 8 | "What nobody covered" own-angle; rival-transcript mining | applied (f93a328): 'what everyone else missed' angle clause; rival-transcript mining skipped (no rival ingestion, and copying rivals is item 35's caveat) |
| 9 | Topic rubric: rising, brand fit, series potential, feasibility | applied (f93a328): 1-5 rubric (viral, fit, series, feasibility) in ideation |
| 10 | Answer-first hub articles: question H2s, 40-60 word answers, FAQ | applied (this commit): article section headings are search questions, each opening with a 40-60 word direct answer |
| 11 | Application block before CTA | applied (f93a328): application block before the CTA |
| 12 | Simple CTA; no business pitch | in place: simple CTA, no business pitch (re-affirmed in the spine) |
| 13 | Never overstate; verify digits in art text | applied (f93a328): review_script.art_text_mismatch flags art digits/currency the narration never states (K/M/B aware) |
| 14 | Thumbnail refine loop; winners as style reference | owner: no image model to iterate on; use YouTube Studio Test & Compare (3 thumbnails per new long video), see owner actions |
| 15 | Per-script review checklist as a QA step | applied (f93a328): per-script review checklist (strategy, voice, accuracy, CTA) logged before QA |
| 16 | Home tab: featured video, playlist sections, trailer | owner: Home tab layout (see owner actions) |
| 17 | Channel description: unique first sentence, cadence, links | owner: channel descriptions (see owner actions) |
| 18 | Watermark, avatar, banner 2048x1152 | owner: watermark, avatar, banner upload (see owner actions) |
| 19 | Opinionated myth-busting post per long video; link in first comment | owner/browser: posting is manual or the loop's browser run; the text comes from the video's closing question and contrarian Short |
| 20 | 8-12 repurposed pieces per long video | in place: each long video already yields 4 Shorts, 4 Instagram Reels, 4 Facebook Reels, a hub article, a Facebook link post and a Community post (about 15 pieces) |
| 21 | Monthly explicit ask; proof-screenshot images | owner: monthly explicit ask and proof screenshots (content decision) |
| 22 | Pin and refresh a Community post per long video | owner/browser: pin and refresh a Community post per long video |
| 23 | Organization schema with sameAs; validate rich results | applied (f93a328): Organization schema with sameAs in hub/src/lib/seo.ts; owner validates in Rich Results Test |
| 24 | robots.txt allows AI crawlers; llms.txt; fast SSR | applied (f93a328): hub/public/llms.txt; robots.ts already allows all crawlers; pages are SSR/ISR |
| 25 | Definition pattern; 100-300 token self-contained sections | applied (this commit): definition pattern and 100-300 word self-contained sections in the article prompt |
| 26 | Topical-authority publishing on a defined topic set | in place: topics come from each channel's fixed niche_keywords and four topic_playlists (a defined topic set) |
| 27 | Off-site mentions; AI-citation testing | owner: off-site mentions (Reddit, publications) and AI-citation testing |
| 28 | Query fan-out: sub-question articles | applied (this commit): FAQs are the follow-up sub-questions (query fan-out) |
| 29 | EEAT: author schema, visible sources | in place: Article JSON-LD author (channel organisation), visible linked sources in evidence boxes |
| 30 | Weekly metrics loop feeding prompt updates | in place: this growth loop plus the weekly persona review |
| 31 | Series potential in topic planning | applied (f93a328): series potential scored in the ideation rubric |
| 32 | Commit to one repurposing style for 3 months | owner: commit to one repurposing style for three months (strategy decision) |
| 33 | Keep testing topics continuously | in place: the loop keeps testing topics continuously |
| 34 | Slower, punchier hook line; A/B on one channel | applied (this commit): voice.hook_rate slows only the first paragraph; A/B on Escape Velocity (-6% hook, +2% body), judged from 2026-12-01 |
| 35 | Do not copy huge-channel tactics blindly | standing rule: own data before huge-channel tactics |

### Owner actions from the playbook (for the to-do artifact; this run cannot write to it)

- Item 16: set each channel's Home tab: featured video = the channel's best performer, playlist
  sections from the topic playlists, trailer optional. Studio > Customization > Layout.
- Item 17: rewrite each channel description: unique first sentence, signature phrase, why trust
  us, upload cadence, one free link to the hub.
- Item 18: upload the 2048x1152 banner from assets/brand/<key>/, confirm avatar and handle match
  across YouTube/IG/FB, enable the video watermark.
- Item 22: pin each long video's Community post (two posted 2026-11-23; the Escape Velocity
  Starship post text is ready in the 2026-11-23 19:25 entry).
- Item 27: Reddit mentions of the hub in relevant communities; log them for the AEO citation test.
- Standing: sign in to Google in the browser pane (blocks Search Console indexing, Studio Reach,
  Community posts); verify Escape Velocity's phone at youtube.com/verify (thumbnails still failing).

### What a browser-capable / permissioned run should do next (in order)

1. Run `PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest tests -q`. If green, commit and push
   BOTH batches: (a) 06:50's `pipeline/publish/__init__.py` + `tests/test_short_long_link.py`;
   (b) this run's `pipeline/script.py`, `pipeline/shorts_daily.py`, `pipeline/ideate.py`,
   `persona/formulas.md`, the five `channels/*/style.md`, `tests/test_content_quality.py`, and
   this log. If any test fails, fix it first; do not commit red.
2. Take a scoreboard snapshot (last is 21+ h old): did "Egg in French: oeuf" hold past 401/day,
   and the 2026-11-24 words episode (03:30 UTC run) gives the first rotated hour/language datapoint.
3. `gh run list --limit 30`: confirm the 03:30 words run published; check for failed produce/shorts runs.
4. Search Console (8/day): starship-flight-15, dutch-government, then tentongues rice/tea/bread/egg/salt.
5. Studio Reach for all channels via the account switcher; log impressions, CTR, stayed-to-watch.
6. Community post for the Escape Velocity Starship long (text ready in the 2026-11-23 19:25 entry).
7. Hub quick wins: `sameAs` with the five channel URLs in `organizationJsonLd()`
   (hub/src/lib/seo.ts); add `hub/public/llms.txt`; then items 10/25/29 in the article prompt.
8. Add the six owner playbook actions above to the to-do artifact (collection "todos").

### Measuring (this run's hypotheses)

- Six-block spine + first-40-words rule: longs published after ~2026-11-26 should show avg %
  viewed above the 16/12.5/10% baselines by ~2026-12-08; the `opening_names_actor_or_number`
  warning should stop appearing in produce logs.
- Search-phrase-first titles + claim-first hooks: Shorts published after ~2026-11-26, judged on
  views at 48 h against the channel medians (10/21/24/27) on 2026-12-08.
- Escapevelocity voice-pacing A/B: 48 h avg % viewed per video from 2026-12-01 (baselines:
  Shorts 38%, longs 10%).
- Ten Tongues hour-vs-language rotation: judge 2026-12-04 (unchanged).
- Quick vs standard Shorts: first quick explainer Shorts 2026-12-30 (unchanged).

### Before/after for the owner (plain words)

Before: titles and hooks often led with a clever phrase or a mood; long videos took a while to
reach the point; every channel's opening did its own thing. After: every video must name the
actor or the number in its first sentence and pay off the title inside fifteen seconds; titles
must start with the exact words people search; the same claim must appear in the title, the hook
card and the thumbnail; topics are picked for being new and unsaturated, with a stated "what
everyone else missed"; Escape Velocity reads its first line slower as an experiment. The rules
came from our own winners (the rice/tea/salt Shorts, the 342% freight Short), not from a course.
Nothing is measured yet: the first videos made under these rules go out around 2026-11-26 and
get judged on 2026-12-08.


## Task run: 2026-11-24 (failed-publication cleanup — blocked execution, honest report)

**Owner task:** count failed publications by platform/reason, quick-recover restorable instagram/facebook
rows, delete the rest, and stop `follow_youtube_to_reels` from leaving failed rows for unrestorable media.
**This session could not execute anything**: the permission system again blocked every Python
interpreter invocation (inventory, `pytest`), `sqlite3`, `git add`/`git commit`. Only read-only file
and git commands worked. No DB counts were taken, nothing was recovered, nothing was deleted,
nothing was committed. `scripts/tmp_failed_inventory.py` (leftover from an earlier attempt) was
deleted and replaced by a safer, complete script.

### Shipped to the working tree (uncommitted, untested)

- `scripts/clear_failed_publications.py`: report-only by default; `--recover` re-publishes once,
  via the existing retry path, only instagram/facebook rows whose YouTube copy is live and whose
  media `restore(..., deep=False)` can fetch (no slow artifact scan, one attempt each); then
  deletes every still-failed row. It deletes only `status='failed'` publication rows and detaches
  (never deletes) historical metrics/comments references, which would otherwise block the plain FK.
  **Next permissioned run: run it without flags first (report), then with `--recover`, and log
  the counts here.**
- `pipeline/publish/__init__.py` (`follow_youtube_to_reels`): a Short with no local file now always
  proves its media through `restore(deep=False)` before `publish_short` runs — previously a set
  `media_url` bypassed the check, `publish_short`'s Meta publishes failed on dead media, and each
  miss recorded failed instagram/facebook publication rows (the exact rows today's task is deleting).
  Misses skip quietly and are remembered once in `reels_follow_missing_<channel>`, as before.
- `tests/test_reels_follow_speed.py`: new regression test proving a dead-`media_url` Short leaves
  no failed publication row and is remembered in the missing setting.

### Next permissioned run must, in order

1. `PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest tests -q`; if green, commit
   `pipeline/publish/__init__.py`, `tests/test_reels_follow_speed.py`, `tests/test_short_long_link.py`,
   `scripts/clear_failed_publications.py` and this log (the working tree also carries a concurrent
   session's edits to ideate/script/shorts_daily/persona files — coordinate or leave them out).
2. Run the cleanup script (report first, then `--recover`), and record here: counts before,
   recovered per platform, deleted, failed remaining (target 0).


### Owner actions from the playbook (2026-11-24)

1. Thumbnail Test & Compare (item 14): in YouTube Studio, open each new long video, Thumbnail, Test & compare, upload two alternatives (Claude can render them on request). Studio picks the winner by watch time.
2. Home tab (item 16): Studio, Customisation, Layout: set a channel trailer for non-subscribers, a featured video for returning viewers, and sections for each topic playlist.
3. Channel descriptions (item 17): Studio, Customisation, Basic info: first sentence says what the channel is about in search words, then the upload cadence, then the hub and Instagram links.
4. Branding (item 18): upload the watermark, avatar and 2048x1152 banner from assets/brand/<key>/ in Studio, Customisation, Branding.
5. Community posts (items 19, 22): one opinionated post per long video (the myth it busts plus the link), pinned and refreshed; the browser loop can draft and post these when asked.
6. Monthly ask (item 21): one post a month asking viewers what to cover next, with a screenshot of a real result.
7. Off-site mentions (item 27): answer relevant Reddit or forum questions with the hub article when it genuinely helps; never spam.
8. Repurposing style (item 32): keep the current Shorts plus hub-article format unchanged for three months before judging it.
9. Rich results (item 23): run https://search.google.com/test/rich-results on one hub article and the home page.

PLAYBOOK COMPLETE (2026-11-24): all 35 items have a final status (applied, in place, owner or standing rule).
- 2026-11-24: playbook items 16-18 via the API (scripts/channel_profile.py): new About descriptions on all four channels (search words first, then schedule, then hub and Instagram links; Future Work had none), new-visitor trailers set (FW mX8MSCkWrbE, TW mTzhMe5JJPk, EV JhjYStQ7LOI, TT R4LnSOzp_iw, each the channel's best long video), watermarks set (HTTP 204). Remaining Studio-only: avatar upload, Home tab featured video for subscribers and playlist sections.
- 2026-11-24 (owner request): made the 6 private topic playlists public (FW 2, EV 3, TT Italian) and added Home tab playlist sections through the API: Future Work 2, Escape Velocity 3, Ten Tongues 6 (full episodes, Russian, Japanese, Urdu, Bengali, French). Trade Winds has no playlists yet (they are created when a matching long video uploads). New topic playlists are now created public. Hub structured data verified by a direct check (Organization sameAs 8; Article, Breadcrumb, Video, FAQ complete).
- 2026-11-24 (browser, owner request): the Home tab was switched OFF on all four channels, so trailers and sections were invisible. Turned it on, added a featured video for returning subscribers (FW 'Pilot or funded?', TW 'Rare Earths For Chips', EV 'When Will Humans Fly on Starship?', TT FRUIT episode), a Short videos row (FW, EV) or Popular videos row (TT), and published. Posted the monthly 'what should we cover next' Community post on all four channels. Still owner/Chrome: avatar upload and thumbnail Test & Compare need file upload (Claude in Chrome was not connected).
- 2026-11-24: 9 of the 17 backfilled thumbnails had unrelated stock backgrounds (Ferris wheel for Starship, pug for Google ads, candle, swing, amethyst). Replaced them with a branded card (pipeline.thumbnail.make_card_thumbnail: channel accent on dark, same text) and the backfill script now uses cards only. Production renders still use the video's own frames.
- 2026-11-24 (Chrome, owner request "do the next five"): thumbnail A/B tests (Studio, Thumbnail, menu, A/B Testing, "Thumbnail only") saved on the next five long videos, A = current thumbnail, B = a 2-3 word claim card from out/thumbs/ab/: E_c9M-SD2TY "ONE NUMBER DECIDES CUTS" (FW, public 11-25 06:00), zVQVg5QK_SA "GOLDMAN: AI LAYOFFS 2026" (FW, 11-27), ey6S36JUzRA "6 DIGITS SET YOUR TARIFF" (TW, 11-24 11:00), zGOfJSXBdFw "HORMUZ: WATCH THE INSURERS" (TW, 11-26), ghU0yN44Ns4 "DARK MATTER: THE PROOF" (EV, 11-26 16:00). Studio shows them "Ineligible: video is not public" while scheduled; check after ey6S36JUzRA goes public at 11:00 UTC whether the test starts on its own, and if not re-set it on the public video. Results within two weeks (Studio picks by watch time share). Fixed make_card_thumbnail: text wider than the frame now shrinks to fit (the Hormuz B card clipped the H in WATCH; the live card thumbnails were checked and none clip).
- 2026-11-24 11:05: ey6S36JUzRA went public and its thumbnail test switched from "Ineligible" to "Running" on its own, so tests saved on scheduled videos start at publish; the other four need no action. First per-video Community post published on Trade Winds (HS-code myth plus link; setting community_post_ey6S36JUzRA). YouTube's post menu offers no pin option, so the loop step posts without pinning.

### Round 4 (2026-11-24): openings, Ten Tongues search titles, Short-to-long links

**Long-video openings.** `scripts/retention_curves.py` (new, read-only) pulls Analytics retention curves. Only four long videos have enough views for a curve, and all four show the same shape: the steepest drop is between second 10 and 21 (-25 to -32% of the audience), exactly where the narration finishes restating the title and turns to background (unit conversions, dates, "the headlines say"). The best curve (FTC data pricing: 76% at 30 s, 65% at 60 s against 26-42% for the rest) is the only one that opens on the viewer's own stake ("The price on your screen..."). Change: the script prompt and the hook rewrite pass now require, within the first 45 spoken words, a second-person stake and a promise of what the video reveals later, with background moved after it; `opening_has_viewer_stake` logs a warning when the first 45 words never say "you/your". Judge: rerun retention_curves.py on videos published after 2026-11-25 once they have 15+ views; success is 30 s retention above 0.6.

**Ten Tongues.** Short titles were already search-shaped ("Rice in Russian: ris"). The spread is by language, not wording: Russian and Japanese Shorts reach 200-900 views, French, Portuguese and Bengali mostly 0-5. YouTube autocomplete for "how to say <word> in" lists Korean, Chinese, Japanese, German and Spanish first, and "<word> in <language> pronunciation" is a common completion. Changes: Short tags now include "how to say X in Y", "X in Y pronunciation" and "Y word for X"; channel.json `short_title_ab: true` gives even-numbered days the title "How to Say Rice in Russian (ris)" and odd days the control, all ten languages sharing the day's variant. Judge on 2026-12-08 (14 days, 7 days each side): median views per Short by variant, per language. Not done (owner decision): replace the weakest languages with Korean or German. The second Short format ("3 ways to say X") needs a schema and render change; deferred until the title test reads out.

**Short-to-long links.** Shorts descriptions already carry the long URL but sit behind "more". New `pipeline/publish/short_links.py`, run by sync: once a child Short and its parent are both public, the channel comments "Full video: <title> <url>" on the Short (Ten Tongues: "Hear the word in all ten languages: ..."), once per Short (setting `yt_link_comment_<id>` written before the call), 50 units each, at most 10 per sync, off with `short_link_comments_enabled` = false. The API cannot pin comments. The Studio-only "Related video" field (a tappable link on the Short) is set by the 6-hour loop in Chrome; first one set on rXC_rpOyaM4 -> UsX-KRHzk2Y. Judge: long-video views with traffic source "Shorts" in Studio after two weeks.
- 2026-11-24 (owner decision): German replaces Bengali in Ten Tongues from the next episode (Piper de_DE-thorsten-medium, CC0; tested locally). Bengali Shorts drew 0-5 views; German is among the top languages in "how to say <word> in" autocomplete. Korean was the first choice but has no commercial-clean voice yet (Piper ko_KR-kss is CC BY-NC-SA; MeloTTS Korean depends on kykim/bert-kor-base, whose README asks commercial users for an MOU). The Bengali playlist and its Home section keep the old episodes; a "German word of the day" playlist is created on the first German Short.

## Loop run: 2026-11-24 13:24 UTC

### Scoreboard (`data/scoreboard/2026-11-24T13.json`)

| channel | long n / median / best | short n / median / best |
|---|---|---|
| futurework | 13 / 9 / 27 | 43 / 9 / 92 |
| tradewinds | 12 / 0.5 / 59 | 43 / 21 / 265 |
| escapevelocity | 12 / 4 / 29 | 42 / 25 / 620 |
| tentongues | 7 / 3 / 31 | 74 / 24 / 922 |
| filmreview | 1 / 73 / 73 | 4 / 112.5 / 424 |

Best long: Frame and Argument 73 (0.7% of 10,000). Best Short: "Rice in Russian: ris" 922 (2.3% of 40,000). Nothing is within 40x of target. Since 07:39 the whole network gained under 100 views; the biggest movers were +16 (Heartland Short) and +11 (Salt in Hindi, Fruit in Mandarin). "Egg in French" did not hold: 124 views at 5 h, 133 at 26 h. Ten Tongues Shorts get one first-day push and then stall. Today's FRUIT episode and Shorts are up (Fruit in Mandarin 11 views in 5 h, the rest 0-2). Trade Winds "The Six-Digit Code That Decides Every Tariff" is public with 0 views at 0.2 days. Quick vs standard: still 0 quick explainer Shorts older than 48 h (7 standard, median 11), so no verdict yet. All workflow runs in the last 30 succeeded.

### Studio (browser pane, Escape Velocity, last 28 days)

- Long videos: 1.6K thumbnail impressions, **1.2% CTR**, average view 1:56, 97 views. Traffic: YouTube search 65%, suggested 19.6%, browse 9.3%. Its custom thumbnails are still rejected (unverified phone), so search results show auto-picked frames. Owner to-do added, priority 1: "Verify Escape Velocity's phone".
- Shorts: 3.3K views, 1.3K engaged, 39.9% stayed to watch (60.1% swiped away). Shorts feed 83.4%, search 14%.
- Other channels not read this run. The built-in pane only had Escape Velocity selected, and switching accounts there takes many clicks.

### Search terms (new `scripts/search_terms.py`, Analytics `insightTrafficSourceDetail`, 28 days)

Search brings in very few views (FW 15, TW 9, EV 65, TT 56), but the phrases are telling. Escape Velocity viewers searched for mission names: "artemis 14", "starship flight 15", "3i atlas", "asteroid 1998 ky26", "moon base". So the subject-first titles are matching real searches. The top Ten Tongues terms are native speakers asking **in their own language**: "hindi mein dudh kaise likhate hain" (10), "bangla cha" (7), "chai ko hindi mein kya bolate hain/kahate hain" (4), "dudh ko english mein kya bolate hain", "cómo se dice leche en inglés". Bengali drew 7 search views just as it was replaced by German; I left the owner's decision as it is, and the data is here if it gets revisited.

### Shipped (d206c6e)

- `pipeline/words.py` `short_tags`: Ten Tongues Short tags now include the native-language question shapes per language. Hindi gets "<word> ko hindi mein kya kehte hain", "hindi mein <roman> kaise likhte hain" and "<roman> ko english mein kya kehte hain". Urdu gets the same. Spanish, Portuguese, French, German and Italian get their "how do you say X in English" phrase plus "<word> in <language>". Every language also gets "<roman> in english", with accents stripped (dūdh -> dudh). Capped at YouTube's 15 tags. Test: `tests/test_words.py::test_short_tags_native_queries`. Suite 490 passed.
- `scripts/search_terms.py` (read-only), with its first output in `data/search_terms.json`.

### Browser

- Search Console (built-in pane, signed in): starship-flight-15 is **already indexed**. Requested indexing for dutch-government and the rice, tea, bread, salt, egg and fruit Ten Tongues articles. That is 8 requests: bread was sent twice because of a focus slip. The Search Console reports say indexed 11, discovered-not-indexed 19. Sitemap last read 2026-11-22. Next: /c/tentongues, milk, then the remaining discovered list.
- Claude in Chrome was not connected, so this run skipped the Community-post and "Related video" steps. No new FW/TW/EV long video went public since the last run apart from ey6S36JUzRA, which was already posted at 11:05.
- Owner to-do "Sign in to Google in Claude's browser pane again" is effectively resolved, since the pane is signed in, but I left it for the owner to tick.

### Measuring

- Native-language tags: Ten Tongues Shorts from the 2026-11-25 episode onward. Rerun `scripts/search_terms.py --channels tentongues --days 7` on 2026-12-02 and compare search views with this baseline (56 in 28 days, about 14 a week).
- Escape Velocity CTR: re-read the 1.2% in Studio once the owner verifies the phone and the thumbnails land.
- Unchanged: Ten Tongues title A/B and hour rotation (2026-12-04/08), quick vs standard Shorts (January), escapevelocity hook-pace A/B (from 2026-12-01).

### Round 5 (2026-11-24): the pictures did not match the story

Owner: content is not entertaining enough. Diagnosis from a frame grid (one frame every 3 s) of the Escape Velocity daily Short "Voyager 1 Went Silent, Then Saved Itself": not one frame showed Voyager, space or NASA. Viewers saw wildflowers, a bird, city skylines and a TV tower. Root causes in code: the daily-Short prompt asked for ONE "generic physical footage query" for the whole Short, child Shorts had one query each, the long-video shot list forbade names, countries and events, and when a query ran out the renderer retried with its first two words ("large radio" -> wildflowers). The hook title was 68 px white on translucent grey (barely readable), and each clip held for up to 9 s.

Changes:
- Shorts (child and daily) now carry an ordered `shots` list, one visual per 3-4 s of narration: a stock search for exactly what is being said, or `CARD: <words>` for a full-screen branded stat card (key numbers and names stock cannot show). `render.apply_shots` maps them to segments of 2.5-4 s (was 3-5 s of one repeated query). Older saved scripts without shots render as before.
- No more truncated two-word fallback queries; an exhausted slot gets the branded caption card instead of an off-topic clip.
- Escape Velocity: shot queries may name real spacecraft and missions (`nasa_hint`), and the NASA provider now also uses public-domain NASA photos with Ken Burns motion when no NASA video matches. Demo rebuild of the same Voyager Short: 9 of 10 slots came from NASA (Voyager team, mission control, launch, the spacecraft).
- Hook title: 92 px black on the channel accent (was 68 px white on grey). Stat cards: one drawtext per line, upper third (clear of the captions), accent colour.
- Long videos: shots 4-6.5 s (were 5-9 s).
- Prompts: entertainment rules. Shorts: a concrete image in every sentence, a twist at the midpoint, nothing skippable. Long videos: re-hook every chapter with an open question, alternate fact and scene, one moment of contrast per chapter, never two abstract sentences in a row.
Judge: Shorts average % viewed and swipe-away (Studio "stayed to watch") for Shorts published from 2026-11-25 against the previous 14 days, read on 2026-12-08.

### Round 5b (2026-11-24): charts, maps, sound, weekly retention review

- CHART and MAP shots (`pipeline/graphics.py`): scripts can ask for a bar chart of 2-6 numbers they state (`CHART: title | a=25%, b=100%`) or a map highlighting named countries (`MAP: Iran, Oman | Strait of Hormuz`, Natural Earth 1:110m, public domain, in assets/geo). Drawn in the channel accent with a slow push-in; portrait layouts keep bars and highlighted countries below the burned-caption zone. Undrawable specs fall back to a stat card. Long-video shot lists may use CARD/CHART/MAP for about one paragraph in four; Shorts up to four per Short. Gives Future Work and Trade Winds on-topic visuals where stock footage has nothing specific.
- Sound design (`pipeline/sfx.py`): synthesised whoosh into every cut on Shorts and into graphics on long videos, plus a low hit under every card, chart and map, mixed at -17 dB with a limiter. No sample library, so no licence question. The narration is no longer halved by amix normalisation (normalize=0).
- Weekly retention review (`pipeline/retention_review.py`, run from sync at most once a week per channel): for recent public videos with 15+ views it finds the steepest drop on the Analytics retention curve, stores the narration spoken there (estimated by word position) and the best-holding opening in `retention_lessons_<channel>`, and every new long-video, child-Short and daily-Short prompt includes them as measured examples to avoid and copy. No model calls.
Judge with round 5 on 2026-12-08.

## Loop run: 2026-11-25 05:41 UTC

### Scoreboard (`data/scoreboard/2026-11-25T05.json`)

| channel | long n / median / best | short n / median / best |
|---|---|---|
| futurework | 13 / 9 / 27 | 45 / 9 / 92 |
| tradewinds | 12 / 1 / 59 | 45 / 20 / 265 |
| escapevelocity | 12 / 5 / 29 | 45 / 27 / 620 |
| tentongues | 7 / 3 / 32 | 77 / 24 / 920 |
| filmreview | 2 / 38 / 76 | 5 / 91 / 421 |

Best long: Frame and Argument 76 (0.8% of 10,000). Best Short: "Rice in Russian: ris" 920 (2.3% of 40,000). The network barely moved in 16 h. Trade Winds "The Six-Digit Code That Decides Every Tariff" still has 0 views at 0.8 days. Best new Shorts in their first hours: EV "Cat's Head Nebula" 29 views at 0.4 d (72/day), "Maybe Don't Bring the Mars Rocks Home" 18 views. Quick vs standard: still no explainer Short under 30 s is public. Owner to-do: nothing newly ticked; Escape Velocity phone verification is still open.

Workflows: every run in the last 30 succeeded apart from the two `retry` runs and one `recap` run on 11-24 16:00, which other sessions dispatched. GitHub cron is running hours late: `words` (03:30 cron) fired at 14:10 on 11-24 and had not fired today by 05:41, and the 04:15 `sync` had not run either. Another session's uncommitted homelab slot-guard work in `.github/workflows/*` and `ops/` targets this, so I left it alone.

### Finding: Future Work's queue runs to 2027-01-02

The `compress_schedule.py` dry run (read-only) shows 81 scheduled YouTube uploads for Future Work, including **16 long videos**, with the last slot on 2027-01-02. Trade Winds has 42 (last slot 2026-12-11) and Escape Velocity 48 (2026-12-13). Long videos are the binding constraint because there are only three cron slots a week and each long brings four child Shorts. The banked stockpile added the surplus. Produce keeps adding three longs a week, so the Future Work queue never shrinks. As a result, every content change (rounds 4 and 5: viewer-stake openings, shot lists, stat cards, sound) reaches Future Work viewers about 5.5 weeks later, and topical news is weeks stale when it airs.

### Shipped

- **Backlog brake** (`pipeline/run_all.py` `backlog_full`, `pipeline/publish/__init__.py` `long_backlog_days`): a fresh `--publish` produce run is skipped (run status `skipped`, log "long-video backlog full") while the channel's last scheduled non-public long video is more than `max_long_backlog_days` days away (channel.json, default 14). Resume, rebuild, dry-run, bank and words runs are never braked. Setting `production_backlog_brake_enabled` = false turns it off. Current values: futurework 37.0 days (braked until about 2026-12-18), tradewinds 15.2 (about one day), escapevelocity 18.4 (about four days), tentongues 1.1 (words.yml is not affected). The brake spends no model calls on videos that would air in January, and when production resumes it picks topics about two weeks before they air instead of six. Tests: `tests/test_backlog_brake.py` (3). Suite 499 passed.
- Not done (needs a decision): drain Future Work faster by adding long-video days or raising `max_youtube_per_day`. Moving the queue costs 51 units per scheduled video (about 4,100 units for Future Work) and changes the channel's fixed calendar, which is part of keeping the channels distinct.

### Browser (Claude in Chrome)

- Community post on Future Work for E_c9M-SD2TY "One Number Decides Every Restructure", public at 06:00. The text covers the performance-review myth, then the span-of-control arithmetic from the script (10,000 workers: 4 reports per manager gives about 3,300 managers over seven layers; 10 reports gives about 1,100 over four), plus the link. Setting `community_post_E_c9M-SD2TY` written.
- "Related video" set on 15 child Shorts, chosen by views: Ten Tongues D-gBD5v9Qkg, SbnZAf0bvYY, NinMrHA1YjE, mVS8S_ct9a0, Zc6Z84C0bP8, qrDzSXo-n18, Dx-75j6QTFw, wV4fIk1FQj8, y4OW8a2YEE8, g91fB_jCOmU, J8qGA8FaJYU, Zz4QtFl6-GA, a2MH0q2Nz7w, and Future Work kqrLYTkqvsE, S9UL8Fq2h7g. Each Short links to its parent episode or long video, and `yt_related_set_<id>` is written for each. 106 eligible pairs remain. Method note: in Chrome, `computer type` fails inside the Studio picker ("Cannot access a chrome-extension:// URL of different extension"). Setting the search input's value plus input/Enter events in JS works, as does clicking the `[role=option]` whose aria-label starts with the parent title and then `#save`. The picker list only loads about 40 recent videos, so search is needed for older parents.
- Search Console indexing and the Studio Reach read were skipped this run (time). Next run: /c/tentongues, milk, and the discovered-not-indexed list.

### Measuring

- Backlog brake: re-run `compress_schedule.py` dry runs on each loop. Future Work's last long slot should stop moving later. Success means the first post-brake Future Work long publishes within 14 days of being produced.
- Related video: Studio "Shorts" traffic source into the linked long videos (TEA, MILK, SALT, RICE, EGG, COFFEE episodes) after 14 days, read on 2026-12-09.
- Unchanged: Ten Tongues title A/B and hour rotation (2026-12-04/08), native-language tags (2026-12-02), round 5 visuals (2026-12-08), quick vs standard Shorts (January).

## Loop run: 2026-11-25 07:23 UTC

### Scoreboard (`data/scoreboard/2026-11-25T07.json`)

| channel | long n / median / best | short n / median / best |
|---|---|---|
| futurework | 14 / 8.5 / 27 | 45 / 9 / 92 |
| tradewinds | 12 / 1 / 59 | 45 / 20 / 265 |
| escapevelocity | 12 / 5 / 29 | 45 / 27 / 620 |
| tentongues | 8 / 2.5 / 32 | 77 / 24 / 920 |
| filmreview | 2 / 38 / 76 | 5 / 91 / 421 |

Best long: Frame and Argument 76 (0.8% of 10,000). Best Short: "Rice in Russian: ris" 920 (2.3% of 40,000). Nothing moved in the 1.7 h since the last run. New uploads: FW "One Number Decides Every Restructure" (1 view at 0.2 d) and TT "APPLE in 10 languages" (0 views). Trade Winds "The Six-Digit Code" is still at 0 views after 0.8 days. Quick vs standard: no explainer Short under 30 s is older than 48 h yet (FW 5 standard, median 5; EV 2, median 10.5; TW 0), so no verdict. Owner to-do: nothing newly ticked.

Ten Tongues Shorts older than 48 h, median views by language: Russian 282 (n=6), Italian 118, Japanese 93, Bengali 45, Urdu 40, Hindi 36, Spanish 33, French 28, Mandarin 17, Portuguese 12. Russian leads clearly. Analytics country data for the Russian Shorts: RU 166, US 150, UZ 56, PH 51, TR 41. The views come from the Shorts feed, not search, so this is learner and Russian-speaker interest. That is not enough evidence to change the language list, which is an owner decision. Logged so it can be revisited.

Workflows: one `words` bank run failed at 06:36 with `DriveFull` ("Drive reserve reached; banking stopped (keep 5 GiB free)"). The 06:46 retry succeeded. This is bank territory, owned by another session, and I left it alone. Everything else in the last 30 runs succeeded.

### Finding: embedding off and view counts hidden on three channels

`videos.list` status, sampled across the 50 newest uploads per channel: Future Work 40 of 50, Trade Winds 50 of 50 and Escape Velocity 46 of 50 are `embeddable: false` and `publicStatsViewable: false`. Ten Tongues is 50 of 50 true. The upload body never set these fields, so each channel's Studio upload defaults applied. The impact: every hub article embeds its video (lite YouTube facade), and on these three channels those players cannot play. External embeds are blocked too, and the hidden view count removes social proof.

### Shipped (c0c0c2b)

- `pipeline/publish/youtube.py` `upload`: `status.embeddable` and `status.publicStatsViewable` are now always true. Test: `tests/test_youtube_upload_status.py`.
- `pipeline/publish/reschedule.py`: the publishAt update it already sends (51 units, part=status) now also sets both fields to true. Every scheduled video that `compress()` re-slots gets fixed at no extra quota cost. `tests/test_reschedule.py` asserts it. Suite 528 passed.
- Already-public videos stay as they are: about 136 videos at 51 units each would cost roughly 7,000 units through the API. Owner to-do added (priority 1, `yt-allow-embedding`): set the upload defaults and bulk-edit "Allow embedding" in Studio, free.

### Browser

- Claude in Chrome: "Related video" set on 15 child Shorts. Ten Tongues: yY1lIwFT5qA, UsaCkbq7t-k, AY9qHMT881w, YlurStgZ4o0, IWEJLF2rH0Q, 9C6Yfxl1lOQ, AYHv856nMS8, z-XYPlCH7qQ, PEkElzhlIwQ (all linked to FRUIT 1bwP3Fkk2-Y). Trade Winds: Lebb6CzRQ4o and 8WlRxnxU350 (linked to ey6S36JUzRA), tHNrVOxEURA (linked to UsX-KRHzk2Y). Escape Velocity: 1noTsFZ4Q-M and hm5scJ-jMqY (linked to YaFfHSER-Ss). Future Work: Ufu_OpUwisQ (linked to 0cHNl-pTq0Y). `yt_related_set_<id>` was written for all 15, and 91 eligible pairs remain. Method note: the picker lists only the **active Studio identity's** videos. Opening a Short's edit URL on another channel loads the page but leaves the picker empty, so switch first (avatar, Switch account) and check `ytcfg.get('CHANNEL_ID')`. Wait for `#save` to become disabled before navigating away, or a "Leave site?" dialog blocks the next page.
- Community post: no new FW/TW/EV long went public since 05:41, apart from E_c9M-SD2TY, which already has its post.
- Search Console: the built-in pane is signed out of Google again, so no indexing this run. The existing to-do `browser-google-signin-2` covers it. Queue: milk, coffee, apple, starship-ship-42, /c/tentongues, layoffs-fell, china-busan, october-jobs.

### Measuring

- Embedding: re-run the status sample on the next run. New uploads and re-slotted videos should show true. Hub embed plays (`hub_events`) on FW/TW/EV articles from 2026-11-26.
- Unchanged: native-language tags (2026-12-02), Ten Tongues title A/B and hour rotation (2026-12-04/08), round 5 visuals (2026-12-08), Related video (2026-12-09), backlog brake (each run), quick vs standard Shorts (January).
