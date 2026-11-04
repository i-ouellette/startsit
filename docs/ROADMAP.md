# Roadmap

Each milestone ends with something demoable.

## M0: Scaffold ✅
- Monorepo layout, docs, CI
- FastAPI app with Sleeper client, baseline projector, optimal lineup solver, tests
- Next.js shell: username → leagues → lineup with risk slider

## M1: Real lineups end to end (week 1)
- [ ] Run against a live Sleeper league locally
- [ ] Map league `scoring_settings` (PPR / half / standard, TE premium) into projections
- [ ] Handle bye weeks and players with no data gracefully
- [ ] Deploy API (Railway) + web (Vercel)

**Demo:** paste a Sleeper username, get your optimal lineup.

## M2: Floor / ceiling model (weeks 2–3)
- [ ] `ml/`: pull nflverse weekly data 2018–present
- [ ] Features: rolling usage (snap %, target share, carries, air yards, red-zone touches), opponent position defence, Vegas implied team total, home/away
- [ ] Train LightGBM quantile models (p10/p50/p90) per position group
- [ ] Backtest: MAE of p50 and p10–p90 coverage per position; compare against a rolling-average baseline
- [ ] Ship the artifact; swap `BaselineProjector` → `ModelProjector`

**Demo:** the slider meaningfully reshuffles close calls; publish backtest numbers in the README.

## M3: Game-day alerts (week 4)
- [ ] Persist subscriptions (Postgres)
- [ ] Scheduled `inactive_watch` job (Sunday 9:00–13:00 ET every 15 min + TNF/MNF)
- [ ] Email via Resend, then web push
- [ ] Dedupe + "suggested swap" in the alert

**Demo:** mark a test player Out → alert arrives with the swap.

## M4: Polish + credibility (weeks 5–6)
- [ ] Recommendation log + weekly grading → accuracy page (vs a simple consensus baseline)
- [ ] "Why?" explanations per pick (feature contributions, optional LLM summary)
- [ ] Auto risk suggestion from matchup win probability
- [ ] Landing page, screenshots, short demo video for the README

## Stretch
- Yahoo (OAuth) and ESPN (cookie) providers
- Waiver suggestions using the same projector
- Trade analyzer (rest-of-season distributions)

## Resume bullets to aim for
- "Built a full-stack fantasy football lineup optimizer (Next.js, FastAPI) that syncs live Sleeper leagues and serves ___ users"
- "Trained LightGBM quantile models producing floor/ceiling projections; p50 MAE ___ vs ___ for baseline; ___% interval coverage"
- "Shipped a game-day alert pipeline that detects inactive starters and recommends optimal swaps within ___ min of status changes"
