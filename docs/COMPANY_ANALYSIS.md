# Martell Group: what it does, and where you could add value

Based on public pages found in October 2026. Anything marked *hypothesis* is an inference to test
in the interview, not a known fact about their internal systems.

## What the company does
- **A group of four companies** spanning media, B2B SaaS and AI, founded by Dan Martell, an entrepreneur and angel investor. (Job posting.)
- **Martell Media** is the content-and-coaching engine, based in Kelowna, BC. Small team (listed as roughly 11 to 50 people), founded in 2019. It produces content and coaching for founders. It is hiring across sales, content and growth, which suggests a business scaling its revenue operations.
- **Martell Ventures** is an AI-first venture studio that co-founds AI-driven software companies with operators, using Dan's audience to validate products.
- **Dan AI** is an AI business coach built on Dan's frameworks, available around the clock to subscribers. This is a paid product where an AI speaks in the founder's name, so quality and trust matter a great deal.
- **History**: SaaS Academy (2016, coaching for B2B SaaS founders), and the book *Buy Back Your Time*.
- **The business shape**: a large audience, monetised through coaching programs, community memberships, events and AI products. That implies recurring revenue, renewals, email and SMS at volume, and a CRM at the centre.
- **Revio**: the posting mentions a "Revio CRM". Public results were ambiguous (several unrelated companies share the name), so I could not confirm which product it is. Ask.

## What the role is really for (from the posting)
They just finished a multi-month move from GoHighLevel to HubSpot, real customers depend on the
stack, and the team is AI-first (everyone uses Claude Code daily). So the job is: **keep revenue
automation reliable, finish the migration cleanup, ship AI features safely, and make non-developers
self-sufficient.**

## Where you could do better for them (hypotheses, ranked)
1. **Prove the revenue path is correct, not just working.** After a migration, silent drift is the likely failure: a paying member without access, a cancelled one who kept it. Idempotent webhooks plus a nightly three-way reconciliation turns "someone noticed" into "we knew by morning". *(Project 01.)*
2. **Finish the migration cleanup with numbers.** Property sprawl, dead or duplicated workflows, and marketing-contact tiers are routine post-migration costs; quantifying the saving makes it easy to approve. *(Project 05.)*
3. **Make the CEO's morning report say what changed.** A report of figures is easy to ignore; anomaly flags, a save list of subscriptions set to cancel, and failed-payment follow-ups make it actionable. *(Project 02.)*
4. **Treat Dan AI like a product with regression tests.** When an AI speaks as the founder, a bad answer is a brand risk. Eval suites that gate every prompt or corpus change, citation checks, and refusal testing are the controls. *(Project 04.)*
5. **Monitor deliverability and SMS compliance continuously.** A coaching business lives on email and text. Failed A2P registration or a weak DMARC policy quietly caps reach. *(Project 06.)*
6. **Ground the sales copilot in what actually won**, keep a human in the loop, and measure it (reply rate, time to first response) before expanding it. *(Project 07.)*
7. **Reduce the asks.** Rank recurring questions by minutes and build the tool for the top one first. *(Project 08.)*

## Questions to ask them (these also test the hypotheses)
- What broke most in the last two months of the migration, and how did you find out?
- How do you currently know a paying member has access, and a cancelled one does not?
- How is Dan AI evaluated today when the prompt or knowledge base changes?
- What are the top three questions colleagues ask the current owner of this stack?
- Which Revio is in use, and what does its inbox expose to an extension?

## A note on how you present this
The posting asks for 5+ years of production Python. These projects demonstrate skills; they do not
replace experience. Describe them as what they are (portfolio projects built against this job
description, tested with fakes) and let the depth of your explanations carry the argument.
Claiming they ran in production would be the quickest way to lose an interview.

## Sources
- Martell Group job posting (pod7.app.loxo.co) and the screenshots you provided
- Martell Group openings on Greenhouse (job-boards.greenhouse.io/martellgrowthsolutions)
- ai.danmartell.com (Dan AI)
- allbusiness.africa/investors/dan-martell (SaaS Academy, Martell Ventures)
- hirebase.org/company/martell-media and prospeo.io/c/martell-media (size, location, founding year)
