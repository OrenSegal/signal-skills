# Recommended sources — mobile app growth / ASO / monetization lens

Curated for a solo/small-team consumer mobile app builder (current context:
Span/PreOpen on iOS/Flutter, Shelfie-website). Not exhaustive — a working
list that grows as mining runs and conversations surface new shows. Each
entry states the angle so a future run knows *why* it's here, not just that
it's here.

Status tags: `unmined` (never run through this skill) / `mined` (check
`ledger.py mined --show "<name>"` for which episodes).

## Already mined

- **The Superwall Podcast** — mined. Founder interviews on app growth,
  paywalls, ASO, occasional acquisition stories. Strong on paywall A/B
  mechanics since the host's product (Superwall) is a paywall tool, so
  guests skew toward talking about paywall experiments specifically.
- **The Startup Ideas Podcast** — mined (14 Isenberg-era episodes + 1
  episode in the 2026-07-23 pass, "FDE - The $1M/year AI job explained").
  General startup-idea validation show; useful as an independent
  cross-check source (the TikTok views-vs-revenue dedup hit came from here
  confirming a Superwall claim; the 4mo pass's own top-topics chart had
  nothing further this show, near-total overlap with Isenberg's guest pool
  on the episodes sampled).
- **Greg Isenberg's podcast** — mined. Broader internet-business/community
  angle, not mobile-specific, but shares guests with the acquisition/exit
  crowd (My First Million overlap).
- **App Masters (Steve P. Young's own show)** — mined, 17 episodes
  (2026-07-23 pass, 2026-03-14 through 2026-07-21). Confirmed as
  ASO/App-Store-mechanics-dense as predicted from the Superwall crossover
  episode; largest single contributor to this pass (172 tier_findings).
  Also the source of the App Masters/Sub Club "endorses fabricated social
  proof" finding that directly contradicts the evidence-first mandate,
  see the Skip tier — treat App Masters growth-hack claims with extra
  scrutiny against that mandate before adopting.
- **Mobile Dev Memo (Eric Seufert)** — mined, 5 episodes (S07E10/E17/E24/
  E25, 2026-03 through 2026-07). Data/analyst-angle claims as expected;
  lower finding density (20 tier_findings) than the founder-interview
  shows, consistent with fewer anecdotal war-story claims per episode.
- **Sub Club (RevenueCat)** — mined, 19 episodes via RSS bulk transcript
  download (`resolve.py --download`). Highest-density source this pass
  (141 tier_findings) and confirmed the intended cross-show dedup value:
  independently echoed the Superwall trial-timeline-disclosure and
  Japan-paywall-density findings from two different guests.
- **Lenny's Podcast** — mined, 5 episodes (2026-04 through 2026-07-09).
  Delivered on "finding contradictions rather than confirmations" —
  source of the onboarding-friction and external-scorer-plus-human-gate
  contradictions/confirmations in the 2026-07-23 synthesis.
- **My First Million** — mined, 2 episodes (2026-06-24, 2026-06-30). Low
  density this pass (11 tier_findings, mostly skip-tier); revisit only if
  exit optionality becomes an active lens, per the original note below.

## Direct match — mine next

(empty — all shows previously listed here were mined 2026-07-23.)

## Broader — good for stress-testing claims from a different angle

(Lenny's Podcast and My First Million, previously listed here, were mined
2026-07-23 — see "Already mined" above. Leave this section as the next
place to add a broader/contradiction-hunting show if one gets proposed.)

## Narrower / higher variance

- **Indie Hackers podcast** — smaller, rawer numbers, higher fluff ratio,
  but occasionally features a builder in the same weight class (solo/small
  team, iOS-first) as opposed to funded/agency operators.

## Adjacent categories — queued, not yet mined (iOS/vision/AI-app/UX lens)

Surfaced 2026-07-23 while scoping a Shelfie-specific mining pass. None of
these mined yet — they sit outside the growth/ASO/monetization lens above
and instead cover build-craft (Swift/SwiftUI engineering), spatial/vision
computing, and AI-app UX, which matter to Shelfie's iOS/vision/AI-feature
roadmap even though they won't feed the paywall/ASO ledger the same way.
Revisit when a mining pass specifically needs engineering or UX signal
instead of growth signal.

- **Swift by Sundell** — SwiftUI/Swift engineering craft, host interviews
  Apple-platform engineers. Not growth-relevant; relevant if a mining pass
  ever targets "how are other iOS teams actually building this."
- **Core Intuition** — long-running indie Apple-platform dev podcast,
  built-things-shipped angle rather than growth angle.
- **iPhreaks (devchat.tv)** — iOS dev panel show, broader engineering
  topics, occasional app-business crossover episodes worth filtering for.
- **Design Better** — product design process/craft, useful if a future
  pass wants onboarding/UX pattern signal rather than paywall-copy signal.
- **The AI Design Podcast** — AI-native UX/interaction-design patterns,
  directly relevant to Shelfie's AI-feature UX decisions specifically.
- **Vision Pros** — spatial computing / visionOS-focused, relevant only if
  Shelfie's vision-app work becomes active; low priority until then.
- **DeepRec.AI Leadership Lab** — AI industry leadership angle, broader
  than app-specific; lower priority, filter hard if ever mined.
- **Odysight.ai** (or similarly-named AI-vision-adjacent shows found via
  search) — unverified fit, needs a resolve.py check before committing to
  mine; listed here as a lead, not a confirmed source.

## How to use this list

1. Before mining a new show, check `ledger.py mined --show "<name>"` — if
   it has episodes recorded, don't restart from scratch, extend it.
2. Prioritize shows tagged "direct match" over "broader" unless the goal is
   explicitly to find a contradiction to something already in the ledger.
3. After mining a new show for the first time, add it to "Already mined"
   here with a one-line note on its angle, same as the entries above — the
   note is what makes a future run's source selection fast instead of
   re-researching from zero.
