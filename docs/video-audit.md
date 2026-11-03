# Video audit

Baseline generated 2026-11-03T06:51:17.207224+00:00. The remediation follow-up below supersedes the Webb status and spend classifications in this snapshot. Read-only DB, YouTube videos.list, media HEAD and GitHub reads. No platform writes, DB repairs, workflow dispatches or Claude calls.

## Coverage and limitations

- DB inventory: 90 content, 190 publications, 7 articles, 222 cost rows.
- Retained result.json history: 8 mapped longs, 0 older/different upload ID records; 0 archives unavailable.
- YouTube: 3 batched videos.list calls; 84 checked IDs; 84 accessible videos. Unrecorded uploads cannot be enumerated under videos.list-only constraint.
- Quota settings: youtube_uploads_per_day=100; youtube_quota_units_per_day=10000.
- Disclosure raw: {"sample": "oldest", "id": "9zCKLky80Qo", "publishedAt": "2026-10-27T17:33:41Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
- Disclosure raw: {"sample": "oldest", "id": "XdErNn67XUc", "publishedAt": "2026-10-27T19:33:47Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
- Disclosure raw: {"sample": "oldest", "id": "dxtzAHDpPco", "publishedAt": "2026-10-27T21:33:43Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
- Disclosure raw: {"sample": "oldest", "id": "7cn4f6p6g3M", "publishedAt": "2026-10-28T13:11:42Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
- Disclosure raw: {"sample": "oldest", "id": "mX8MSCkWrbE", "publishedAt": "2026-10-28T23:35:02Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
- Disclosure raw: {"sample": "newest", "id": "ZTeI--MY7V0", "publishedAt": "2026-11-02T19:49:03Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
- Disclosure raw: {"sample": "newest", "id": "jL7N6eF1ksQ", "publishedAt": "2026-11-03T00:09:25Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
- Disclosure raw: {"sample": "newest", "id": "laizPh42MmI", "publishedAt": "2026-11-03T00:09:36Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
- Disclosure raw: {"sample": "newest", "id": "cqxljm0G-Lc", "publishedAt": "2026-11-03T00:10:40Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
- Disclosure raw: {"sample": "newest", "id": "nlxPYGzIQlM", "publishedAt": "2026-11-03T00:11:44Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
- Wrong-channel verification uses configured YT_CHANNEL_ID when available; otherwise channelId consistency only. Vertical verification requires owner-visible fileDetails; absent fields are unverified. API thumbnails do not prove a custom thumbnail was set.
- Private queue: 7 objects; 1 unreferenced objects (never deleted).
- GitHub recent runs: 100; failed: 41512476980 shorts, 41327528251 weekly-review, 41325395886 shorts, 41215037686 shorts, 41087483122 shorts, 41059901010 produce, 41059891628 produce, 41056709580 produce, 41052009823 produce, 41052004984 produce, 41051845660 retry, 41051842756 retry, 41048387073 retry, 41048385023 retry, 41043704476 retry, 41043593657 retry, 41043589973 retry, 41043368723 retry, 41043361405 retry, 41043358219 retry, 41042799307 retry, 41042745404 retry
- Media artifact sampling skipped (use --sample-media).
- Quota settings verified read-only: youtube_uploads_per_day=100; youtube_quota_units_per_day=10000. No settings changed.
- Additional owner-authenticated channels.list + paginated playlistItems.list + videos.list enumerated all uploads: escapevelocity=30, futurework=29, tradewinds=25; no same-title duplicates on any channel; all 84 IDs match the audit inventory.

Finding counts (one item can have multiple findings): critical=0, high=37, medium=138, low=20.

## Findings

| Severity | Content id | Problem | Evidence | Recommended action | Classification |
|---|---|---|---|---|---|
| high | 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt-short-1, 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt-short-2, futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite, futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite-short-1, futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite-short-2, futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c, futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c-short-2 | Over three YouTube slots per UTC day | ('futurework', datetime.date(2026, 10, 29)) | Review before retry | owner-only |
| high | 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt-short-1, 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt-short-2, futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite, futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite-short-1, futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite-short-2, futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c, futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c-short-2 | Over three actual public videos per UTC day | ('futurework', datetime.date(2026, 10, 29)) | Owner review burst; new uploads use private schedules | owner-only |
| high | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-1 | Public before DB schedule | 2026-11-05T18:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-2 | Public before DB schedule | 2026-11-06T18:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-3 | Public before DB schedule | 2026-11-07T18:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-4 | Public before DB schedule | 2026-11-08T18:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double, escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-1, escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-2, escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-3 | Over three YouTube slots per UTC day | ('escapevelocity', datetime.date(2026, 10, 29)) | Review before retry | owner-only |
| high | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double, escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-1, escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-2, escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-3 | Over three actual public videos per UTC day | ('escapevelocity', datetime.date(2026, 10, 29)) | Owner review burst; new uploads use private schedules | owner-only |
| high | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-4, escapevelocity-2026-10-30-short-nasa-unveils-ambitious-20-billion-moon-b, escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph, escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-1, escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-2, escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-3 | Over three YouTube slots per UTC day | ('escapevelocity', datetime.date(2026, 10, 30)) | Review before retry | owner-only |
| high | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-4, escapevelocity-2026-10-30-short-nasa-unveils-ambitious-20-billion-moon-b, escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph, escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-1, escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-2, escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-3 | Over three actual public videos per UTC day | ('escapevelocity', datetime.date(2026, 10, 30)) | Owner review burst; new uploads use private schedules | owner-only |
| high | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet, escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-1, escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-2, escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-4, escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha, escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-1, escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-2, escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-3, escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-4, escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af | Over three actual public videos per UTC day | ('escapevelocity', datetime.date(2026, 11, 1)) | Owner review burst; new uploads use private schedules | owner-only |
| high | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-2 | Public before DB schedule | 2026-11-03T18:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-3 | Content qa_failed | QA=failed | Resume retained artifact after reviewing QA | re-runnable |
| high | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-4 | Public before DB schedule | 2026-11-04T18:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af | Public before DB schedule | 2026-11-05T16:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the-short-1 | Content qa_failed | QA=failed | Resume retained artifact after reviewing QA | re-runnable |
| high | futurework-2026-10-30-attackers-use-microsoft-teams-it-support | Public before DB schedule | 2026-11-04T06:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | futurework-2026-10-30-attackers-use-microsoft-teams-it-support, futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-1, futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-2, futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-3, futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-4 | Over three actual public videos per UTC day | ('futurework', datetime.date(2026, 11, 1)) | Owner review burst; new uploads use private schedules | owner-only |
| high | futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-1 | Public before DB schedule | 2026-11-07T13:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-2 | Public before DB schedule | 2026-11-08T13:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-3 | Public before DB schedule | 2026-11-09T13:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-4 | Public before DB schedule | 2026-11-10T13:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe, tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-2, tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-3, tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-4 | Over three YouTube slots per UTC day | ('tradewinds', datetime.date(2026, 10, 30)) | Review before retry | owner-only |
| high | tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe, tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-2, tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-3, tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-4, tradewinds-2026-10-30-short-trump-delays-robotics-machinery-tariffs | Over three actual public videos per UTC day | ('tradewinds', datetime.date(2026, 10, 30)) | Owner review burst; new uploads use private schedules | owner-only |
| high | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o, tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-1, tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart, tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-1, tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-2, tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-3, tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-4 | Over three actual public videos per UTC day | ('tradewinds', datetime.date(2026, 10, 31)) | Owner review burst; new uploads use private schedules | owner-only |
| high | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-1 | Public Short missing Reels | facebook, instagram | Recover media then normal sync follow-up | re-runnable |
| high | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-1 | Short missing media_url | Fresh runner cannot restore local file | Recover artifact and persist media URL; no fabricated URL | code-fixable |
| high | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-1 | facebook failed | publication=236; unstructured error retained in DB | Drain quota queue; inspect failures before retry | re-runnable |
| high | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-1 | instagram failed | publication=235; unstructured error retained in DB | Drain quota queue; inspect failures before retry | re-runnable |
| high | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-1, tradewinds-2026-10-30-container-freight-rates-are-climbing-eve, tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-2, tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-3, tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-4 | Over three actual public videos per UTC day | ('tradewinds', datetime.date(2026, 11, 1)) | Owner review burst; new uploads use private schedules | owner-only |
| high | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-1, tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-2, tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-3, tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-4 | Over three YouTube slots per UTC day | ('tradewinds', datetime.date(2026, 11, 1)) | Review before retry | owner-only |
| high | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve | Public before DB schedule | 2026-11-07T11:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart | Public before DB schedule | 2026-11-05T11:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-1 | Public before DB schedule | 2026-11-09T15:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-2 | Public before DB schedule | 2026-11-10T15:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-3 | Public before DB schedule | 2026-11-11T15:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| high | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-4 | Public before DB schedule | 2026-11-12T15:00:00+00:00 | Owner decide publication policy; public uploads ignore publishAt | owner-only |
| medium | 2026-10-27-microsoft-offers-voluntary-buyouts-to-about-a-qu | Spend without rendered output | $0.9449 | Inspect failure before regeneration | re-runnable |
| medium | 2026-10-27-paypal-cuts-thousands-of-jobs-and-raises-its-pro | Spend without rendered output | $0.9710 | Inspect failure before regeneration | re-runnable |
| medium | 2026-10-27-proton-is-re-interviewing-staff-about-how-they-u | Spend without rendered output | $0.7642 | Inspect failure before regeneration | re-runnable |
| medium | 2026-10-27-the-netherlands-plans-to-replace-about-25-000-go | Long without four active Shorts | 0 active children | Review historical two-Short scripts; rebuild needs four saved angles | owner-only |
| medium | 2026-10-27-the-netherlands-plans-to-replace-about-25-000-go | Repeated Claude spend (review) | $3.0072; {'qa': 4, 'article': 5} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | 2026-10-27-the-netherlands-plans-to-replace-about-25-000-go | Synthetic disclosure unverified | 9zCKLky80Qo; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | 2026-10-28-breach-victims-are-finding-their-data-was-held-b | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | 2026-10-28-breach-victims-are-finding-their-data-was-held-b | Long without four active Shorts | 0 active children | Review historical two-Short scripts; rebuild needs four saved angles | owner-only |
| medium | 2026-10-28-breach-victims-are-finding-their-data-was-held-b | Synthetic disclosure unverified | 7cn4f6p6g3M; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt | Long without four active Shorts | 2 active children | Review historical two-Short scripts; rebuild needs four saved angles | owner-only |
| medium | 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt | Repeated Claude spend (review) | $0.6921; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt | Synthetic disclosure unverified | mX8MSCkWrbE; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt-short-1 | Synthetic disclosure unverified | M0szo5XN9tA; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt-short-2 | Synthetic disclosure unverified | hXnhJeJ82yA; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph | Repeated Claude spend (review) | $1.7500; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph | Synthetic disclosure unverified | -7shtOk0QGw; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-1 | Synthetic disclosure unverified | 9M2Zqvkr8VE; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-2 | Synthetic disclosure unverified | sV0ilmqMEZA; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-3 | Synthetic disclosure unverified | cs9em-fWO0o; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-4 | Synthetic disclosure unverified | ybDUT1dQog4; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha | Repeated Claude spend (review) | $2.5220; {'qa': 3, 'article': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha | Synthetic disclosure unverified | ba2W7hT1oQE; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-1 | Synthetic disclosure unverified | 0XVAFNKB-QQ; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-2 | Synthetic disclosure unverified | iUZkqbOXaPc; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-3 | Synthetic disclosure unverified | -XWgPC6AJtg; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-4 | Synthetic disclosure unverified | 043bQGm5A7I; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double | Repeated Claude spend (review) | $3.0728; {'article': 4} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double | Synthetic disclosure unverified | JhjYStQ7LOI; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-1 | Synthetic disclosure unverified | SKfZI3fIAK8; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-2 | Synthetic disclosure unverified | 9jboshOcVMc; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-3 | Synthetic disclosure unverified | h5ZOFBeth54; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-4 | Synthetic disclosure unverified | 5KQe4hLOxlQ; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-30-short-nasa-unveils-ambitious-20-billion-moon-b | Synthetic disclosure unverified | xkWpRD68bmA; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet | Repeated Claude spend (review) | $3.7473; {'qa': 2, 'article': 4} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet | Synthetic disclosure unverified | 3bCgk-MUjUI; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-1 | Synthetic disclosure unverified | r7jLf4Biyog; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-2 | Synthetic disclosure unverified | IbFB9qIgFmk; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-3 | Repeated Claude spend (review) | $0.0990; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-4 | Synthetic disclosure unverified | 3WzkWcdrhTE; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-10-31-short-first-light-hera-resolves-two-asteroids | Spend without rendered output | $0.1685 | Inspect failure before regeneration | re-runnable |
| medium | escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af | Repeated Claude spend (review) | $2.3414; {'article': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af | Synthetic disclosure unverified | rCCuenJrb5M; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af-short-1 | Synthetic disclosure unverified | thCmQEtKhhs; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af-short-2 | Synthetic disclosure unverified | 18eew99rL2A; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af-short-3 | Synthetic disclosure unverified | -bT-rqn-mpg; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af-short-4 | Synthetic disclosure unverified | HnaCXz6yuF4; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-11-01-short-first-light-hera-resolves-two-asteroids | Spend without rendered output | $0.1550 | Inspect failure before regeneration | re-runnable |
| medium | escapevelocity-2026-11-02-short-first-light-hera-resolves-two-asteroids | Synthetic disclosure unverified | ZTeI--MY7V0; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the | Repeated Claude spend (review) | $2.3609; {'article': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the | Synthetic disclosure unverified | jL7N6eF1ksQ; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the-short-2 | Synthetic disclosure unverified | laizPh42MmI; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the-short-3 | Synthetic disclosure unverified | cqxljm0G-Lc; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the-short-4 | Synthetic disclosure unverified | nlxPYGzIQlM; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c | Long without four active Shorts | 3 active children | Review historical two-Short scripts; rebuild needs four saved angles | owner-only |
| medium | futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c | Synthetic disclosure unverified | XMZmx3gsSlk; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c-short-1 | Spend without rendered output | $0.0371 | Inspect failure before regeneration | re-runnable |
| medium | futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c-short-2 | Synthetic disclosure unverified | 8J7-Qa7yQtk; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c-short-3 | Synthetic disclosure unverified | Crrp7hhbarY; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c-short-4 | Synthetic disclosure unverified | 9iE856l5s3U; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite | Long without four active Shorts | 2 active children | Review historical two-Short scripts; rebuild needs four saved angles | owner-only |
| medium | futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite | Repeated Claude spend (review) | $1.9390; {'article': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite | Synthetic disclosure unverified | Sjn4az2twY8; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite-short-1 | Synthetic disclosure unverified | E8sNdnCrhlo; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite-short-2 | Synthetic disclosure unverified | J2kKsAZW0c8; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r | Synthetic disclosure unverified | hBLtqpwBmZQ; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r-short-1 | Synthetic disclosure unverified | _AmPAiuS58w; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r-short-2 | Synthetic disclosure unverified | irJ9cNNe59k; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r-short-3 | Synthetic disclosure unverified | PJZV1aBLzDA; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r-short-4 | Synthetic disclosure unverified | bcGXko24oYY; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-attackers-use-microsoft-teams-it-support | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | futurework-2026-10-30-attackers-use-microsoft-teams-it-support | Repeated Claude spend (review) | $2.1821; {'article': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | futurework-2026-10-30-attackers-use-microsoft-teams-it-support | Synthetic disclosure unverified | opMAP5H4RZo; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-1 | Synthetic disclosure unverified | 2pEuNNbTTt0; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-2 | Synthetic disclosure unverified | JR_QE3VH-Q0; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-3 | Synthetic disclosure unverified | 97LW5zc5XfM; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-4 | Synthetic disclosure unverified | Tvzf4vloOFY; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-10-30-short-attackers-use-microsoft-teams-it-support | Spend without rendered output | $0.1565 | Inspect failure before regeneration | re-runnable |
| medium | futurework-2026-10-30-short-why-ai-s-time-saved-figures-converted-to | Spend without rendered output | $0.1579 | Inspect failure before regeneration | re-runnable |
| medium | futurework-2026-10-31-short-why-ai-s-time-saved-figures-converted-to | Spend without rendered output | $0.1720 | Inspect failure before regeneration | re-runnable |
| medium | futurework-2026-11-01-short-why-ai-s-time-saved-figures-converted-to | Spend without rendered output | $0.1615 | Inspect failure before regeneration | re-runnable |
| medium | futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its | Repeated Claude spend (review) | $2.0369; {'article': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its | Synthetic disclosure unverified | PKY57DG-oDU; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its-short-1 | Synthetic disclosure unverified | 8bkOpd7ui_I; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its-short-2 | Synthetic disclosure unverified | mF8TgozqAZA; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its-short-3 | Synthetic disclosure unverified | 5qw-hdPv_Ek; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its-short-4 | Synthetic disclosure unverified | O0SDd8gLFDM; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | futurework-2026-11-02-short-why-ai-s-time-saved-figures-converted-to | Spend without rendered output | $0.1658 | Inspect failure before regeneration | re-runnable |
| medium | tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe | Long without four active Shorts | 3 active children | Review historical two-Short scripts; rebuild needs four saved angles | owner-only |
| medium | tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe | Synthetic disclosure unverified | sYR-AKVTE0M; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-1 | Spend without rendered output | $0.0372 | Inspect failure before regeneration | re-runnable |
| medium | tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-2 | Synthetic disclosure unverified | sjJubDlF6hg; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-3 | Synthetic disclosure unverified | BYCzwGqAmWc; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-4 | Synthetic disclosure unverified | eBlMy0hM_P4; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o | Synthetic disclosure unverified | dcKPzhzE7hE; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-1 | Synthetic disclosure unverified | ZpvysXmwzkw; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-2 | Synthetic disclosure unverified | N7aNTcNMxAE; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-3 | Synthetic disclosure unverified | SecbL9apMpk; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-4 | Synthetic disclosure unverified | 0XK4kOwscf8; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize | Repeated Claude spend (review) | $2.5450; {'qa': 2, 'article': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize | Synthetic disclosure unverified | mTzhMe5JJPk; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-1 | Repeated Claude spend (review) | $0.0747; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-1 | Synthetic disclosure unverified | oLP3pDuG_LY; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-2 | Repeated Claude spend (review) | $0.0809; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-2 | Synthetic disclosure unverified | 8FLr_a0e68g; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-3 | Repeated Claude spend (review) | $0.0774; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-3 | Synthetic disclosure unverified | -Fdriyv32_Q; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-4 | Repeated Claude spend (review) | $0.0785; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-4 | Synthetic disclosure unverified | 2TXGSGtih1A; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve | Repeated Claude spend (review) | $2.6034; {'qa': 2, 'article': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve | Synthetic disclosure unverified | jL7nn1aK4EU; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-1 | Repeated Claude spend (review) | $0.0794; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-1 | Synthetic disclosure unverified | 6N27VrIqn60; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-2 | Repeated Claude spend (review) | $0.0794; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-2 | Synthetic disclosure unverified | xMrsWCao24I; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-3 | Repeated Claude spend (review) | $0.0819; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-3 | Synthetic disclosure unverified | bK6PPrYXgBw; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-4 | Repeated Claude spend (review) | $0.0780; {'qa': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-4 | Synthetic disclosure unverified | BmPocgDPgq0; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-30-short-trump-delays-robotics-machinery-tariffs | Synthetic disclosure unverified | 19-4WFOIhFA; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-31-short-european-gas-prices-hit-100-mwh-for-the | Spend without rendered output | $0.1554 | Inspect failure before regeneration | re-runnable |
| medium | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart | Long without article | No article row | Generate article separately when API spend is authorized | re-runnable |
| medium | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart | Repeated Claude spend (review) | $2.6639; {'article': 2} | Check retries/validation; repeated calls alone do not prove waste | owner-only |
| medium | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart | Synthetic disclosure unverified | rPvYrdCPCLE; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-1 | Synthetic disclosure unverified | LxAflfPR_Iw; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-2 | Synthetic disclosure unverified | xWRD052S2zo; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-3 | Synthetic disclosure unverified | QCxg7z7dgiw; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-4 | Synthetic disclosure unverified | n0BP8tpfHyU; field absent from response | Absent is not false; verify in Studio before any metadata write | owner-only |
| medium | tradewinds-2026-11-01-short-european-gas-prices-hit-100-mwh-for-the | Spend without rendered output | $0.1475 | Inspect failure before regeneration | re-runnable |
| medium | tradewinds-2026-11-02-short-european-gas-prices-hit-100-mwh-for-the | Spend without rendered output | $0.1538 | Inspect failure before regeneration | re-runnable |
| low | 2026-10-27-the-netherlands-plans-to-replace-about-25-000-go | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | 2026-10-28-breach-victims-are-finding-their-data-was-held-b | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | escapevelocity-2026-10-29-starship-flight-15-the-attempted-double | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | futurework-2026-10-30-attackers-use-microsoft-teams-it-support | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |
| low | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-3 | Orphan queue object | tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-3/tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-3.mp4 | Owner verify no in-flight upload before cleanup | owner-only |
| low | tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart | Long missing media_url | Long recovery relies on retained artifact or private queue | Keep recovery media before artifact expiry; public URL is not required for long uploads | owner-only |

## Per-content inventory

| Content id | Kind | Status | QA | Platforms |
|---|---|---|---|---|
| 2026-10-27-paypal-cuts-thousands-of-jobs-and-raises-its-pro | long | draft | pending |  |
| 2026-10-27-proton-is-re-interviewing-staff-about-how-they-u | long | draft | pending |  |
| 2026-10-27-the-netherlands-plans-to-replace-about-25-000-go | long | published | passed | youtube:live |
| 2026-10-27-the-netherlands-plans-to-replace-about-25-000-go-short-1 | child Short | killed | failed | youtube:live |
| 2026-10-27-the-netherlands-plans-to-replace-about-25-000-go-short-2 | child Short | killed | failed | youtube:live |
| 2026-10-28-breach-victims-are-finding-their-data-was-held-b | long | published | passed | youtube:live |
| 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt | long | published | passed | youtube:live |
| 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph | long | published | passed | youtube:live |
| escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha | long | published | passed | youtube:live |
| escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-starship-flight-15-the-attempted-double | long | published | passed | youtube:live |
| escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-29-starship-flight-15-the-attempted-double-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-30-short-nasa-unveils-ambitious-20-billion-moon-b | short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet | long | published | passed | youtube:live |
| escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-3 | child Short | qa_failed | failed |  |
| escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af | long | published | passed | youtube:live |
| escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-11-02-short-first-light-hera-resolves-two-asteroids | short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the | long | published | passed | youtube:live |
| escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the-short-1 | child Short | qa_failed | failed |  |
| escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c | long | published | passed | youtube:live |
| futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite | long | published | passed | youtube:live |
| futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r | long | published | passed | youtube:live |
| futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r-short-1 | child Short | published | passed | youtube:live |
| futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r-short-2 | child Short | published | passed | youtube:live |
| futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r-short-3 | child Short | published | passed | youtube:live |
| futurework-2026-10-30-alphabet-s-worst-day-ever-servicenow-s-r-short-4 | child Short | published | passed | youtube:live |
| futurework-2026-10-30-attackers-use-microsoft-teams-it-support | long | published | passed | youtube:live |
| futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-10-30-attackers-use-microsoft-teams-it-support-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its | long | published | passed | youtube:live |
| futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| futurework-2026-11-02-short-why-ai-s-time-saved-figures-converted-to | short | draft | pending |  |
| tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe | long | published | passed | youtube:live |
| tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o | long | published | passed | youtube:live |
| tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-1 | child Short | published | passed | youtube:live, instagram:failed, facebook:failed |
| tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-3 | child Short | published | passed | youtube:live |
| tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o-short-4 | child Short | published | passed | youtube:live |
| tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize | long | published | passed | youtube:live |
| tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-1 | child Short | published | passed | youtube:live |
| tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-2 | child Short | published | passed | youtube:live |
| tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-3 | child Short | published | passed | youtube:live |
| tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-4 | child Short | published | passed | youtube:live |
| tradewinds-2026-10-30-container-freight-rates-are-climbing-eve | long | published | passed | youtube:live |
| tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-30-short-trump-delays-robotics-machinery-tariffs | short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart | long | published | passed | youtube:live |
| tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-1 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-2 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-3 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart-short-4 | child Short | published | passed | youtube:live, instagram:live, facebook:live |
| tradewinds-2026-11-02-short-european-gas-prices-hit-100-mwh-for-the | short | draft | pending |  |

## Comparison with previous audit (2026-11-02)

- Finding keys (content id + problem): resolved/reclassified=79, still open=86, new/reclassified=109. Disclosure reclassification and time passing account for some differences; disappearing findings do not always indicate a code fix.
- Resolved: Swift YouTube queue entries 246/249/252/255 now have processed uploads; they remain private, scheduled November 9/10/11/12 at 18:00 UTC. Do not retry. Quota settings are the intended 100/10000. Previously missing Reels for Alphabet, AI chips and Hormuz Short 2 are now live.
- Still open: Webb Short 3 remains QA-failed with no platform publication. The November 2 resume (41406616051) did execute, but failed vision QA again: cropped source subtitle/timestamp in the coronagraph footage. Successful workflow conclusion does not mean every child passed. Other Webb videos retain their original IDs; no replacement upload was found.
- Still open: Hormuz Short 1 failed Instagram 235 / Facebook 236, missing media; historical schedule bursts, missing articles and repeated spend remain review items.
- New: 13 content rows, 28 publication rows and 28 cost rows since the baseline; article count unchanged at 7. New content includes Anthropic junior hiring and Voyager. Latest failed daily Shorts run is 41512476980. See the finding table for each new item.
- Retry duplicate check: no duplicate titles among all 84 remote uploads. Swift retries uploaded within 26 seconds (adjacent gaps 11, 9 and 6 seconds) with four distinct titles/IDs; a burst alone is not a duplicate. Retained result.json history also found zero older/different IDs. No evidence of retry-created YouTube duplicates; identical footage with changed titles and external Meta duplicates are not excluded by these checks.

## Synthetic disclosure investigation

Raw owner-authenticated videos.list status samples (sorted by snippet.publishedAt, which is not always upload time for scheduled/public videos):

```jsonl
{"sample": "oldest", "id": "9zCKLky80Qo", "publishedAt": "2026-10-27T17:33:41Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
{"sample": "oldest", "id": "XdErNn67XUc", "publishedAt": "2026-10-27T19:33:47Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
{"sample": "oldest", "id": "dxtzAHDpPco", "publishedAt": "2026-10-27T21:33:43Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
{"sample": "oldest", "id": "7cn4f6p6g3M", "publishedAt": "2026-10-28T13:11:42Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
{"sample": "oldest", "id": "mX8MSCkWrbE", "publishedAt": "2026-10-28T23:35:02Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
{"sample": "newest", "id": "ZTeI--MY7V0", "publishedAt": "2026-11-02T19:49:03Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
{"sample": "newest", "id": "jL7N6eF1ksQ", "publishedAt": "2026-11-03T00:09:25Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
{"sample": "newest", "id": "laizPh42MmI", "publishedAt": "2026-11-03T00:09:36Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
{"sample": "newest", "id": "cqxljm0G-Lc", "publishedAt": "2026-11-03T00:10:40Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
{"sample": "newest", "id": "nlxPYGzIQlM", "publishedAt": "2026-11-03T00:11:44Z", "containsSyntheticMedia_present": false, "containsSyntheticMedia": null}
```

All 84 responses omit the field: explicit true=0, explicit false=0, absent=84. Newest uploads do not differ. The insert body in pipeline/publish/youtube.py sets status.containsSyntheticMedia=True with part=snippet,status. Absence does not establish false; the audit bug conflated the two and now reports “Synthetic disclosure unverified” at medium severity. No disclosure updater was added or run because the requested explicit-false condition was not established. Studio verification remains an owner task. [YouTube video status reference](https://developers.google.com/youtube/data/reference/rest/v3/videos#status.containsSyntheticMedia). Any future status updater must preserve mutable fields; [videos.update costs 50 units](https://developers.google.com/youtube/data/reference/rest/v3/videos/update).

## Hormuz Short 1 recovery

Read-only exhaustive location checks: local recorded file absent; media bucket 76 objects (only Hormuz Shorts 2–4 found); youtube-queue 7 objects (no Hormuz); 3 GitHub releases (no Hormuz assets); 13 retained artifact records inspected, no unexpired videos/shorts archive contains Hormuz paths. No recoverable Short 1 media was found. Public YouTube ZpvysXmwzkw remains processed/public. YouTube Data API cannot download the public video file; do not treat its watch URL as uploadable media.

Its saved DB script exists (837 characters). Rebuild only Short 1 from that script, channel bm_george voice, and newly selected real vertical footage, then run full QA before retrying only IG/FB. The original parent's script.json/shot queries are not retained, so run_all --resume/--rerender is not currently an executable recovery path for Hormuz. Do not rebuild/reupload its live YouTube copy. No safe ready-to-run publishing command exists until replacement media passes QA and is persisted; blindly retrying 235/236 will fail again.

## Root-cause changes and verification

- Audit now distinguishes explicit false disclosure from an omitted response field, with regression coverage for absent/false/true.
- Future audit runs print oldest/newest raw disclosure samples and exact quota settings. Generated retry commands exclude known IDs and items without approved recoverable media URLs.
- tests/conftest.py was read before tests: disposable SQLite, write credential removal, HTTP and external CLI blocking confirmed. No tests used live config. Full suite: 151 passed, 8 subtests passed. No commits, dashboard/hub edits, live writes, Claude calls or workflow dispatches in this job.

## REMEDIATION

Commands below are proposals only. SAFE denotes duplicate safety, not authorization to execute during this read-only job. Deploy code fixes before using them; QA/article spend requires separate authorization.

| Class | Exact command | Why |
|---|---|---|
| SUPERSEDED | No Webb rebuild command | Latest produce 41592578778 uploaded Short 3; see follow-up. |

No Swift retry, quota reset, bulk disclosure write, delete or replacement-live-video command is justified. Hormuz is blocked on reconstruction/QA/persistence, so no speculative retry command is provided. Owner decisions: review historical public scheduling, inspect disclosure in Studio, authorize missing-article spend, and review intentional placeholders without deleting them.

## Remediation follow-up (2026-11-03, read-only)

Live reads: 90 content rows, 191 publications, 7 articles, 229 cost rows, 60 run rows. Read paginated DB tables, retained GitHub artifact members and original workflow logs. No Claude calls, platform/DB writes, dispatches or commits. Changes are confined to pipeline/, scripts/, tests/ and this report. The baseline finding table above remains historical.

### Article recovery

`scripts/backfill_articles.py` requires `--dry-run` or `--apply`; optional `--limit N` must be positive. Selection requires a non-killed long with a live YouTube publication and platform ID and no article row. Sources are local script.json, then unexpired retained artifact script.json, then DB narration text with the saved title. Artifact reads use range requests rather than downloading all footage. Failed/unavailable archives are reported, without printing request URLs or credentials. Dry-run does not call write_article, instantiate Claude or write DB/Storage. Apply checks for an article again, calls pipeline.article.write_article with the recovered script, preserves current validation and CostGuard, never forces regeneration and continues after individual failures (exit 1 if any fail). Run a single operator instance at a time; concurrent operators are not locked by a new DB claim.

Actual dry-run output (pipeline DB connection log omitted):

```text
DRY RUN: 12 of 12 missing articles; estimate $0.60 each (validation retries may cost more)
2026-10-28-breach-victims-are-finding-their-data-was-held-b | DB:content.script | $0.60
2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt | DB:content.script | $0.60
escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha | artifact:videos-escapevelocity-41281283060 | $0.60
escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet | artifact:videos-escapevelocity-41592578778 | $0.60
escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af | artifact:videos-escapevelocity-41345831741 | $0.60
escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the | artifact:videos-escapevelocity-41544570269 | $0.60
futurework-2026-10-30-attackers-use-microsoft-teams-it-support | artifact:videos-futurework-41281259162 | $0.60
futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its | artifact:videos-futurework-41471719484 | $0.60
tradewinds-2026-10-29-three-tankers-slip-out-of-hormuz-along-o | DB:content.script | $0.60
tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize | DB:content.script | $0.60
tradewinds-2026-10-30-container-freight-rates-are-climbing-eve | artifact:videos-tradewinds-41281269937 | $0.60
tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart | artifact:videos-tradewinds-41217545606 | $0.60
Recoverable: 12; estimated cost $7.20
No script source: none
```

All twelve are recoverable. $7.20 is an estimate, not a cap: current validation allows a second $0.60-estimated attempt per article, and actual token/search usage varies. Existing published articles are skipped; failed validation saves no article and a later operator retry can spend again.

### Six historical Shorts-count findings

The audit counts all non-killed children as active, including QA failures. Thus Voyager has four active children even though Short 1 failed QA. Count alone is not a publishing-health check. The following six parents have no verified retained producing artifact in the current artifact listing. No rebuild command qualifies under the artifact + saved requested Short + no duplicate risk rule. Local script files do not satisfy the retained-artifact requirement.

| Long content id | Existing / active / YouTube live children | Explanation |
|---|---|---|
| 2026-10-27-the-netherlands-plans-to-replace-about-25-000-go | 2 / 0 / 2 | Shorts 1–2 intentionally killed placeholders; keep their uploads. Historical run executed two Shorts. Local saved script has three angles: angle 3 was outside that run’s two-Short cap, angle 4 absent. Do not replace placeholders. |
| 2026-10-28-breach-victims-are-finding-their-data-was-held-b | 0 / 0 / 0 | Shorts 1–2 failed TTS before content persistence: “No audio was received” (produce 40682350555). This was not QA rejection. Historical run attempted two; 3–4 never requested by the two-Short run. Full saved script no longer retained. |
| 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt | 2 / 2 / 2 | Shorts 1–2 live. Historical two-Short run; 3–4 never requested by that run. Full saved script no longer retained, so no claim about additional generated angles. |
| futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c | 3 / 3 / 3 | Short 1 rejected by old QA (produce 40943426653), despite notes saying frames/captions were fine and text was not cut off; no child row persisted. Shorts 2–4 live. Historical QA false negative, not a never-requested angle. |
| futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite | 2 / 2 / 2 | Shorts 1–2 live. Local saved script has three angles, but run 40869811860 executed only two under the historical cap; angle 3 never requested for rendering, angle 4 absent from script. |
| tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe | 3 / 3 / 3 | Short 1 rejected by old QA (produce 40943437359): it treated the first of three frames as a thumbnail, even while notes reported no cut-off text. No child row persisted. Shorts 2–4 live. |

### Spend classification

Accounting definition: waste here means stranded paid generation for which neither a usable render nor a saved script is available in local outputs, retained artifacts or DB. It does not mean every failed attempt was avoidable. Successful recovery, safety QA and bounded article-validation retries are legitimate work. Dollar totals below use unrounded cost.usd values, count each cost row once within each class, and are not estimates. The two finding classes are analyzed separately; do not add their totals because findings may overlap.

**Stranded generation waste: $3.17522.** This is $1.73513 for the abandoned PayPal/Proton long scripts/hooks plus $1.44009 for nine daily responses without a retained usable output. Within that waste, $0.80187 is repeated same-topic daily generation on later dates after an earlier paid attempt; another $0.15378 later gas attempt is recoverable in DB and excluded from waste. Repeated spend on the same content ID is not demonstrated for scripts: every long has exactly one script and one hook cost row. These are recovery/accounting judgments, not proof that no render ever existed on a now-discarded runner.

| Spend-without-output content id (15 baseline findings) | USD | Classification / evidence |
|---|---:|---|
| 2026-10-27-microsoft-offers-voluntary-buyouts-to-about-a-qu | 0.94492 | Legitimate: final local MP4 and script exist; missing DB row makes this audit test a false positive. |
| 2026-10-27-proton-is-re-interviewing-staff-about-how-they-u | 0.76415 | Stranded generation waste: no retained usable script/render; abandoned long attempt. |
| 2026-10-27-paypal-cuts-thousands-of-jobs-and-raises-its-pro | 0.97098 | Stranded generation waste: no retained usable script/render; abandoned long attempt. |
| tradewinds-2026-10-29-america-s-50-tariffs-on-canada-take-effe-short-1 | 0.03716 | Legitimate safety QA / historical false rejection; source logs above prove rendering reached QA. Not a script purchase. |
| futurework-2026-10-29-companies-that-cut-jobs-for-ai-are-now-c-short-1 | 0.03710 | Legitimate safety QA / historical false rejection; source logs above prove rendering reached QA. Not a script purchase. |
| futurework-2026-10-30-short-attackers-use-microsoft-teams-it-support | 0.15647 | Stranded generation waste: daily response lost after failed run; no retained script/render. |
| futurework-2026-10-30-short-why-ai-s-time-saved-figures-converted-to | 0.15789 | Stranded generation waste: daily response lost after failed run; no retained script/render. |
| escapevelocity-2026-10-31-short-first-light-hera-resolves-two-asteroids | 0.16850 | Stranded generation waste: daily response lost after failed run; no retained script/render. |
| tradewinds-2026-10-31-short-european-gas-prices-hit-100-mwh-for-the | 0.15536 | Stranded generation waste: daily response lost after failed run; no retained script/render. |
| futurework-2026-10-31-short-why-ai-s-time-saved-figures-converted-to | 0.17204 | Stranded generation waste: daily response lost after failed run; no retained script/render. |
| escapevelocity-2026-11-01-short-first-light-hera-resolves-two-asteroids | 0.15502 | Stranded generation waste: daily response lost after failed run; no retained script/render. |
| tradewinds-2026-11-01-short-european-gas-prices-hit-100-mwh-for-the | 0.14749 | Stranded generation waste: daily response lost after failed run; no retained script/render. |
| futurework-2026-11-01-short-why-ai-s-time-saved-figures-converted-to | 0.16152 | Stranded generation waste: daily response lost after failed run; no retained script/render. |
| tradewinds-2026-11-02-short-european-gas-prices-hit-100-mwh-for-the | 0.15378 | Legitimate recoverable validation failure: 165-word response saved in DB qa_notes.daily_script; edit/recover before retrying. |
| futurework-2026-11-02-short-why-ai-s-time-saved-figures-converted-to | 0.16580 | Stranded generation waste: daily response lost after failed run; no retained script/render. |

The 15 findings total $4.34818: legitimate/recoverable $1.17296; stranded generation waste $3.17522. No paid regeneration or repair was performed.

The original 23 repeated-spend findings are QA re-runs/resumes and article validation retries. The newer Webb run adds three repeated-QA groups (Shorts 1, 2 and 4), for 26 now. Original 23 identifiers are included in the table below. QA costs are necessary safety checks, including re-checks after a rerender; articles are separate deliverables, not replacement video scripts. The latest Webb article attempts failed entities/self-QA validation (produce 41592578778 logs); this explains why article costs coexist with a missing article. There is no evidence of duplicate long-script purchases in these groups.

| Repeated-spend content id | QA calls / USD | Article calls / USD | Classification |
|---|---:|---:|---|
| 2026-10-27-the-netherlands-plans-to-replace-about-25-000-go | 4 / 0.09614 | 5 / 2.18173 | Legitimate QA re-run/resume or article validation |
| 2026-10-28-the-ftc-is-demanding-data-from-walmart-uber-delt | 2 / 0.05128 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| escapevelocity-2026-10-29-hera-s-first-look-at-didymos-and-dimorph | 2 / 0.08767 | 1 / 0.67292 | Legitimate QA re-run/resume or article validation |
| escapevelocity-2026-10-29-nasa-s-20-billion-moon-base-strategy-wha | 3 / 0.13636 | 2 / 1.49997 | Legitimate QA re-run/resume or article validation |
| escapevelocity-2026-10-29-starship-flight-15-the-attempted-double | 1 / 0.04204 | 4 / 2.19671 | Legitimate QA re-run/resume or article validation |
| escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet | 3 / 0.13479 | 6 / 4.14756 | Legitimate QA re-run/resume or article validation |
| escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-1 | 2 / 0.07920 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-2 | 2 / 0.07848 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-3 | 3 / 0.13980 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| escapevelocity-2026-10-30-webb-reads-the-ice-of-interstellar-comet-short-4 | 2 / 0.07858 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| escapevelocity-2026-11-01-nasa-s-swift-telescope-is-coming-home-af | 1 / 0.04675 | 2 / 1.31660 | Legitimate QA re-run/resume or article validation |
| escapevelocity-2026-11-02-voyager-1-has-gone-quiet-again-what-the | 1 / 0.04543 | 2 / 1.41658 | Legitimate QA re-run/resume or article validation |
| futurework-2026-10-29-ghost-jobs-fake-listings-and-ai-recruite | 1 / 0.04074 | 2 / 1.19555 | Legitimate QA re-run/resume or article validation |
| futurework-2026-10-30-attackers-use-microsoft-teams-it-support | 1 / 0.04465 | 2 / 1.23037 | Legitimate QA re-run/resume or article validation |
| futurework-2026-11-02-anthropic-heads-toward-an-ipo-while-its | 1 / 0.04493 | 2 / 1.23027 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize | 2 / 0.08643 | 2 / 1.51757 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-1 | 2 / 0.07470 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-2 | 2 / 0.08088 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-3 | 2 / 0.07736 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-29-twelve-million-dollars-of-ai-chips-seize-short-4 | 2 / 0.07854 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-30-container-freight-rates-are-climbing-eve | 2 / 0.08890 | 2 / 1.44718 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-1 | 2 / 0.07940 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-2 | 2 / 0.07938 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-3 | 2 / 0.08188 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-30-container-freight-rates-are-climbing-eve-short-4 | 2 / 0.07800 | 0 / 0.00000 | Legitimate QA re-run/resume or article validation |
| tradewinds-2026-10-31-two-chinese-firms-exit-kenya-s-rare-eart | 1 / 0.04385 | 2 / 1.46127 | Legitimate QA re-run/resume or article validation |

Total QA/article spend within these 26 groups: $23.51044; demonstrated duplicate-script waste in these groups: $0.00000. This includes the first QA/article call as well as repeat calls; initial script/hook costs are excluded. Failed article validation is not a published article, and repeated failed validators remain an efficiency opportunity rather than evidence of a video-script repurchase.

### Code changes and retry boundaries

- Long script responses are checkpointed immediately to paid_script.json and content.qa_notes.paid_script before hook/validation. A retry reuses script.json, the raw paid checkpoint or DB checkpoint; no new hook is purchased on checkpoint reuse. Existing script cost without recoverable data fails closed with an artifact-recovery message. Script calls disable automatic wrapper retries, preventing malformed paid JSON from silently buying another script. Transport uncertainty can still strand a response; the cost ledger is not an atomic distributed generation lock.
- Daily retries with a recorded paid call and missing checkpoint fail closed. Fresh-topic selection now includes cost-only daily topics from the last 14 days, so failed historical rows cannot disappear from topic avoidance on a new runner. Existing saved invalid daily scripts still require correction rather than another paid response.
- Article recovery supplies script_data to the existing writer; CostGuard, title guardrail, validation and normal persistence remain in force. No schema or configuration changes.

### Webb Short 3: newer result supersedes rebuild proposal

Latest produce run **41592578778**, started 2026-11-03T06:51:57Z and completed successfully at 07:34:16Z, returned all four Shorts. The DB run result and publication row record Short 3 as passed/published with YouTube ID **0D8vDCVi4Cc**. No new YouTube API check was needed to establish the recorded produce result. Its latest QA notes still mention cropped source text (“e sun.” and partial UTC timestamp) and a partial NASA source title, classified as minor; the generated caption remained legible. It is no longer QA-blocked. Per the conditional scope, no shorts/render change or rebuild was made. Preserve its existing publication ID; do not execute the old Webb rerender command.

### Exact operator commands (prepared, not executed)

From repository root:

```bash
.venv/bin/python scripts/backfill_articles.py --dry-run
.venv/bin/python scripts/backfill_articles.py --apply --limit 1
.venv/bin/python scripts/backfill_articles.py --apply
timeout 240 .venv/bin/python -m pytest tests -q
```

Apply spends Claude credit and writes articles/thumbnail storage plus the writer’s normal IndexNow notification. It requires production DB configuration and an Anthropic key; CostGuard may skip when budget is insufficient. Review the dry-run before applying. No qualifying Shorts rebuild/dispatch command is provided. No live operation was executed during this job.

Verification: disposable SQLite, credentials removed and requests/httpx/external network CLIs blocked by tests/conftest.py. Regression coverage includes source precedence, read-only dry-run, continuation after one failed article, idempotence, pre-validation checkpoint recovery from disk and DB, refusal to repurchase missing long/daily checkpoints, and cost-only daily topic avoidance. Final command: `timeout 240 .venv/bin/python -m pytest tests -q` — **160 passed, 8 subtests passed in 9.26s**. `git diff --check` passed. No dashboard/ or hub/ edits.
