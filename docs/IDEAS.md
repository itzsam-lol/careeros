# Ideas backlog

Features **not** covered in detail by the product specification, identified while designing the
architecture. None of these are part of the MVP; each needs an explicit decision before it is
scheduled. Priorities: **P0** critical · **P1** high value · **P2** useful · **P3** experimental.

## Summary

| # | Idea | Area | Priority | Complexity |
| --- | --- | --- | --- | --- |
| 1 | Grounding & extraction eval suite | AI quality / DX | P0 | Medium |
| 2 | PII minimisation proxy for LLM calls | Privacy | P0 | Medium |
| 3 | Step-up confirmation for irreversible actions | Security | P0 | Low |
| 4 | Data export & delete-my-data | Privacy | P1 | Medium |
| 5 | Posting freshness & ghost-job scoring | Career intelligence | P1 | Medium |
| 6 | Hiring-season calendar | Career intelligence | P1 | Medium |
| 7 | Sponsorship likelihood per company | Career intelligence | P1 | Medium |
| 8 | Dismissal reasons feedback loop | Personalisation | P1 | Low |
| 9 | Preference suggestions from behaviour | Personalisation | P2 | Medium |
| 10 | Editable agent memory ("house rules") | Agent memory | P1 | Medium |
| 11 | Edit-diff style learning | Agent memory | P2 | Medium |
| 12 | Weekly application plan under a time budget | Decision support | P1 | Medium |
| 13 | Effort estimate per application | Decision support | P2 | Low |
| 14 | Offer comparison workspace | Decision support | P2 | Low |
| 15 | Lab & professor paper digest | Research workflows | P1 | Medium |
| 16 | Team tech-stack fingerprinting | Company intelligence | P2 | Medium |
| 17 | Hiring health signals for watched companies | Company intelligence | P2 | Medium |
| 18 | Question-bank clustering & pre-drafting | Application efficiency | P1 | Medium |
| 19 | Portal account tracker (no passwords) | Application efficiency | P2 | Low |
| 20 | Warm-path finder from user-provided network data | Networking | P1 | Medium |
| 21 | Relationship CRM with check-in reminders | Networking | P2 | Low |
| 22 | Event, hackathon & career-fair radar | Networking | P2 | Medium |
| 23 | Approve-and-schedule send windows | Outreach | P1 | Low |
| 24 | Reply assistant for recruiter responses | Outreach | P2 | Medium |
| 25 | Bounce handling & contact quality feedback | Outreach | P1 | Low |
| 26 | Mock interview simulator | Interview prep | P2 | High |
| 27 | Competency coverage map for stories | Interview prep | P2 | Medium |
| 28 | Gap-closing portfolio project planner | Skill development | P2 | Medium |
| 29 | Evidence capture from new work (GitHub import) | Skill development | P1 | Medium |
| 30 | Funnel analytics with statistical guardrails | Analytics | P1 | Medium |
| 31 | Source yield scoring | Analytics | P2 | Low |
| 32 | Rules engine ("when X, prepare Y") | Workflow automation | P1 | Medium |
| 33 | Daily digest (email/push) | Workflow automation | P1 | Low |
| 34 | Calendar sync for deadlines & interviews | Workflow automation | P2 | Low |
| 35 | Adapter SDK with recorded-fixture contract tests | Developer experience | P1 | Medium |
| 36 | LLM trace viewer & replay | Observability | P1 | Medium |
| 37 | Freshness SLOs & source breakage alerts | Observability | P2 | Low |
| 38 | Adaptive model cascade | Cost optimisation | P1 | Medium |
| 39 | Batch inference for bulk work | Cost optimisation | P2 | Medium |
| 40 | Per-user AI budget with graceful degradation | Cost optimisation | P2 | Low |
| 41 | Local-model provider (fully offline mode) | Privacy / cost | P3 | Medium |
| 42 | Anomaly detection on outbound actions | Security | P2 | Medium |

---

## Details

### 1. Grounding & extraction eval suite
- **Problem:** Prompt or model changes can silently degrade extraction accuracy or introduce ungrounded claims.
- **Why it matters:** Grounding is CareerOS's core promise; regressions must be caught before users see them.
- **Implementation:** Golden datasets (synthetic JDs, profiles, expected extractions, expected rejections); `careeros eval` command computes field-level F1, grounding-violation rate, eligibility accuracy; runs in CI for prompt/model changes with thresholds.
- **Data:** Curated fixtures in `fixtures/evals`, labelled by hand.
- **AI involvement:** Evaluates AI outputs; optional LLM-as-judge only for tone, never for grounding (which stays deterministic).
- **Complexity:** Medium.
- **Risks:** Overfitting prompts to the golden set; dataset maintenance cost.
- **Priority:** P0.

### 2. PII minimisation proxy for LLM calls
- **Problem:** Prompts can contain phone numbers, emails, addresses and demographic answers that providers do not need.
- **Why it matters:** Reduces exposure of personal data to third parties and simplifies compliance.
- **Implementation:** A prompt pre-processor replaces PII with stable placeholders (`<PHONE_1>`), keeps a per-call mapping in memory, and rehydrates model output; allow-list per task.
- **Data:** Profile fields with sensitivity labels.
- **AI involvement:** None (deterministic), optionally a small NER pass.
- **Complexity:** Medium.
- **Risks:** Placeholder leakage into final documents; over-redaction harming quality.
- **Priority:** P0.

### 3. Step-up confirmation for irreversible actions
- **Problem:** A stolen or long-lived session could send emails or submit applications.
- **Why it matters:** These actions are external and irreversible.
- **Implementation:** Require a recent `auth_time` (Firebase re-authentication or passkey) for send/submit endpoints; approvals bound to the content hash expire after N minutes.
- **Data:** Token `auth_time`, approval records.
- **AI involvement:** None.
- **Complexity:** Low.
- **Risks:** Friction on mobile; must degrade gracefully.
- **Priority:** P0.

### 4. Data export & delete-my-data
- **Problem:** Users need portability and the ability to erase their professional data, resumes and email tokens.
- **Why it matters:** Trust, and legal requirements in many jurisdictions (GDPR/DPDP).
- **Implementation:** Export job producing a signed ZIP (JSON + PDFs); delete job cascading DB rows, storage objects and revoking OAuth tokens; audit record retained without content.
- **Data:** Everything owned by the user.
- **AI involvement:** None.
- **Complexity:** Medium.
- **Risks:** Missing an orphaned copy (caches, logs); irreversible deletion by mistake (needs step-up).
- **Priority:** P1.

### 5. Posting freshness & ghost-job scoring
- **Problem:** Evergreen, reposted or stale postings waste application effort.
- **Why it matters:** Effort should go to roles that are actually hiring.
- **Implementation:** Features: days open, repost count across sources, JD churn, generic-JD score, company hiring signals; a transparent score shown on cards with reasons.
- **Data:** `first_seen_at`, `last_seen_at`, source mappings, description history.
- **AI involvement:** Optional classifier for "generic JD" language.
- **Complexity:** Medium.
- **Risks:** False negatives hiding real roles — must only down-rank, never hide.
- **Priority:** P1.

### 6. Hiring-season calendar
- **Problem:** Internship cycles open at predictable times per company, and early applicants have an edge.
- **Why it matters:** Lets the agent prompt the user before a cycle opens.
- **Implementation:** Aggregate historical `first_seen_at` per company × role family; forecast windows; "cycle likely opening" notifications for watched companies.
- **Data:** Months of discovery history.
- **AI involvement:** None (statistics).
- **Complexity:** Medium.
- **Risks:** Sparse data early on — show confidence and sample size.
- **Priority:** P1.

### 7. Sponsorship likelihood per company
- **Problem:** International candidates waste effort on companies that never sponsor.
- **Why it matters:** A hard constraint for many users.
- **Implementation:** Combine JD statements across the company's postings with public labour-certification disclosure datasets where available; show evidence and dates.
- **Data:** JD extractions, public government datasets.
- **AI involvement:** Extraction of sponsorship statements (already exists) aggregated per company.
- **Complexity:** Medium.
- **Risks:** Outdated public data; must never be presented as certainty.
- **Priority:** P1.

### 8. Dismissal reasons feedback loop
- **Problem:** Dismissing a job teaches the system nothing today.
- **Why it matters:** Cheap, explicit signal to improve ranking.
- **Implementation:** One-tap reasons (location, seniority, domain, company, compensation); reasons feed a per-user ranking adjustment and preference suggestions.
- **Data:** Dismiss events with reasons.
- **AI involvement:** None initially.
- **Complexity:** Low.
- **Risks:** Over-fitting to a few dismissals — decay and caps.
- **Priority:** P1.

### 9. Preference suggestions from behaviour
- **Problem:** Users rarely keep preferences up to date.
- **Why it matters:** Better targeting without manual upkeep.
- **Implementation:** Detect consistent patterns (e.g. every "Sales Engineer" dismissed) and propose a preference change; never change preferences silently.
- **Data:** Saves, dismissals, applications.
- **AI involvement:** Pattern summarisation.
- **Complexity:** Medium.
- **Risks:** Creepy or wrong suggestions; keep explainable.
- **Priority:** P2.

### 10. Editable agent memory ("house rules")
- **Problem:** Users repeat the same corrections ("never mention project X for finance roles").
- **Why it matters:** Personalisation that the user can see and control.
- **Implementation:** A `agent_rules` table of scoped, user-editable rules injected into relevant prompts as trusted user instructions; each rule shows where it was applied.
- **Data:** User-authored rules.
- **AI involvement:** Rules applied during generation; validators check compliance where deterministic.
- **Complexity:** Medium.
- **Risks:** Conflicting rules; prompt bloat — scope rules by task.
- **Priority:** P1.

### 11. Edit-diff style learning
- **Problem:** Users repeatedly edit generated bullets and emails in the same way.
- **Why it matters:** Drafts should converge to the user's voice.
- **Implementation:** Store before/after diffs; derive style hints (length, formality, banned phrases) shown to the user for approval before use.
- **Data:** Edit history.
- **AI involvement:** Summarising edits into style hints.
- **Complexity:** Medium.
- **Risks:** Learning accidental edits; keep hints reviewable.
- **Priority:** P2.

### 12. Weekly application plan under a time budget
- **Problem:** Too many good options and too little time; deadlines collide.
- **Why it matters:** Converts a ranked list into an achievable plan.
- **Implementation:** Knapsack-style planner over (match, deadline urgency, estimated effort, readiness) within the user's weekly hours; plan updates as work completes.
- **Data:** Matches, deadlines, effort estimates (#13), application states.
- **AI involvement:** Optional rationale text; core is deterministic optimisation.
- **Complexity:** Medium.
- **Risks:** Users treating it as prescriptive; show trade-offs.
- **Priority:** P1.

### 13. Effort estimate per application
- **Problem:** Some portals take 5 minutes, others 90.
- **Why it matters:** Feeds planning and prioritisation.
- **Implementation:** Estimate from portal type, number of free-text questions, account requirement, historical completion times.
- **Data:** Form inspections, application timings.
- **AI involvement:** None.
- **Complexity:** Low.
- **Risks:** Inaccurate for unknown portals.
- **Priority:** P2.

### 14. Offer comparison workspace
- **Problem:** Comparing offers across compensation, location, visa, growth and learning is ad hoc.
- **Why it matters:** High-stakes decision with many dimensions.
- **Implementation:** Structured offer entries, user-weighted criteria, sensitivity analysis ("if you weight growth higher, B wins").
- **Data:** User-entered offer details.
- **AI involvement:** Optional summarisation of trade-offs.
- **Complexity:** Low.
- **Risks:** False precision; keep it a thinking tool.
- **Priority:** P2.

### 15. Lab & professor paper digest
- **Problem:** Research outreach is only credible when it references the lab's actual work.
- **Why it matters:** Makes professor/lab outreach specific and honest.
- **Implementation:** Pull recent papers from open scholarly APIs (arXiv, Semantic Scholar, OpenAlex) for the PI; summarise and map overlaps with the user's research evidence; every reference keeps provenance.
- **Data:** Public paper metadata/abstracts.
- **AI involvement:** Summarisation and overlap mapping, grounded in abstracts.
- **Complexity:** Medium.
- **Risks:** Author disambiguation errors; API rate limits.
- **Priority:** P1.

### 16. Team tech-stack fingerprinting
- **Problem:** Job ads rarely describe the real stack of a specific team.
- **Why it matters:** Sharper tailoring and interview prep.
- **Implementation:** Aggregate technologies across the company's postings over time, public engineering blogs and public GitHub organisations; show evidence per technology.
- **Data:** JD history, public blogs/repos.
- **AI involvement:** Extraction from blog text.
- **Complexity:** Medium.
- **Risks:** Stale signals; attributing org-wide tech to a team.
- **Priority:** P2.

### 17. Hiring health signals for watched companies
- **Problem:** Layoffs or hiring freezes make applications futile; funding rounds signal growth.
- **Why it matters:** Adjusts priority and expectations.
- **Implementation:** Track posting volume deltas per company plus optional news search; surface signals with sources on the company page.
- **Data:** Posting history, search API results.
- **AI involvement:** News classification with provenance.
- **Complexity:** Medium.
- **Risks:** Misreading news; must link sources and avoid conclusions.
- **Priority:** P2.

### 18. Question-bank clustering & pre-drafting
- **Problem:** Portals ask the same questions in different words.
- **Why it matters:** Pre-drafted, verified answers make applications minutes long.
- **Implementation:** Embed every question encountered; cluster; pre-draft grounded answers for top clusters; user verifies once, reuse everywhere with similarity thresholds.
- **Data:** Application questions and answers.
- **AI involvement:** Clustering and grounded drafting.
- **Complexity:** Medium.
- **Risks:** Reusing an answer where nuance differs — show the matched question.
- **Priority:** P1.

### 19. Portal account tracker (no passwords)
- **Problem:** Users forget which Workday tenants they already registered with.
- **Why it matters:** Avoids duplicate accounts and lockouts.
- **Implementation:** Record portal tenant + login email + last used (never passwords); link to the user's password manager.
- **Data:** Application portal metadata.
- **AI involvement:** None.
- **Complexity:** Low.
- **Risks:** None significant if no secrets are stored.
- **Priority:** P2.

### 20. Warm-path finder from user-provided network data
- **Problem:** Warm introductions outperform cold emails but are hard to spot.
- **Why it matters:** Higher-quality outreach with less spam.
- **Implementation:** Import the user's own connection export (CSV) or alumni lists they provide; match to companies of interest; suggest asking for advice/intro with a drafted message.
- **Data:** User-provided network data only.
- **AI involvement:** Matching and drafting.
- **Complexity:** Medium.
- **Risks:** Privacy of third parties — keep data local to the user, no enrichment.
- **Priority:** P1.

### 21. Relationship CRM with check-in reminders
- **Problem:** Contacts go cold after a single exchange.
- **Why it matters:** Networking compounds over time.
- **Implementation:** Interaction log per contact, configurable check-in cadence, reminder notifications, drafts on request.
- **Data:** Outreach threads, manual notes.
- **AI involvement:** Optional drafting.
- **Complexity:** Low.
- **Risks:** Pestering contacts — reminders only, never automatic sends.
- **Priority:** P2.

### 22. Event, hackathon & career-fair radar
- **Problem:** Career fairs, info sessions and hackathons are high-yield but scattered.
- **Why it matters:** Opens doors that job boards do not.
- **Implementation:** Adapters for public event feeds (university career centre calendars, Devpost, conference sites); match to interests and location; calendar export.
- **Data:** Public event listings.
- **AI involvement:** Relevance scoring.
- **Complexity:** Medium.
- **Risks:** Feed variety and maintenance.
- **Priority:** P2.

### 23. Approve-and-schedule send windows
- **Problem:** Emails sent at 2 a.m. recipient time get buried.
- **Why it matters:** Better response rates with no extra user effort.
- **Implementation:** On approval, choose a send time within the recipient's business hours (timezone from company/contact location); the approval still binds to the exact content.
- **Data:** Contact/company location.
- **AI involvement:** None.
- **Complexity:** Low.
- **Risks:** Scheduled sends after circumstances changed — allow cancel until sent.
- **Priority:** P1.

### 24. Reply assistant for recruiter responses
- **Problem:** Replies (scheduling, questions) need quick, accurate answers.
- **Why it matters:** Momentum matters after a reply.
- **Implementation:** Detect replies (existing tracking), draft grounded responses and availability windows; user approval required.
- **Data:** Thread content (minimal), calendar availability.
- **AI involvement:** Drafting.
- **Complexity:** Medium.
- **Risks:** Misunderstanding requests — always a draft.
- **Priority:** P2.

### 25. Bounce handling & contact quality feedback
- **Problem:** Invalid addresses harm sender reputation and waste effort.
- **Why it matters:** Protects the user's email account.
- **Implementation:** Parse bounce notifications in the thread; mark contact email invalid; lower source confidence for the discovery method that produced it.
- **Data:** Gmail thread metadata.
- **AI involvement:** None.
- **Complexity:** Low.
- **Risks:** Misclassifying auto-replies as bounces.
- **Priority:** P1.

### 26. Mock interview simulator
- **Problem:** Practising with realistic, role-specific questions is hard alone.
- **Why it matters:** Converts interviews into offers.
- **Implementation:** Text (later voice) sessions generated from JD + company brief + the user's evidence; rubric-based feedback; transcripts saved privately.
- **Data:** JD, research, profile evidence.
- **AI involvement:** Heavy (question generation, evaluation).
- **Complexity:** High.
- **Risks:** Unreliable feedback; cost.
- **Priority:** P2.

### 27. Competency coverage map for stories
- **Problem:** Users over-rely on one story for every behavioural question.
- **Why it matters:** Balanced preparation.
- **Implementation:** Map experiences/projects to competencies (leadership, conflict, failure, impact) and show gaps per target role family.
- **Data:** Profile evidence.
- **AI involvement:** Classification with evidence links.
- **Complexity:** Medium.
- **Risks:** Shallow classification.
- **Priority:** P2.

### 28. Gap-closing portfolio project planner
- **Problem:** Gap analysis says what is missing but not how to demonstrate it.
- **Why it matters:** Evidence beats claims.
- **Implementation:** Suggest scoped portfolio projects per missing skill cluster, track progress, convert completed projects into (unverified → verified) evidence.
- **Data:** Aggregated JD requirements, profile evidence.
- **AI involvement:** Project ideation.
- **Complexity:** Medium.
- **Risks:** Generic suggestions; time sink for the user.
- **Priority:** P2.

### 29. Evidence capture from new work (GitHub import)
- **Problem:** Profiles go stale as users ship new work.
- **Why it matters:** Fresh evidence improves every downstream artefact.
- **Implementation:** Optional GitHub OAuth; propose project entries from the user's repositories (README, languages, stars) as UNVERIFIED items for review.
- **Data:** User's public/authorised repositories.
- **AI involvement:** Summarising repositories into project entries.
- **Complexity:** Medium.
- **Risks:** Overstating contributions to shared repos — only use the user's own commits.
- **Priority:** P1.

### 30. Funnel analytics with statistical guardrails
- **Problem:** Users cannot see what actually works (roles, resume variants, outreach styles).
- **Why it matters:** Enables learning without superstition.
- **Implementation:** Stage conversion rates by segment with sample sizes and confidence intervals; suppress conclusions below minimum sample sizes.
- **Data:** Application and outreach outcomes.
- **AI involvement:** None for statistics; optional narrative summary.
- **Complexity:** Medium.
- **Risks:** Causal over-interpretation — explicit guardrails in UI copy.
- **Priority:** P1.

### 31. Source yield scoring
- **Problem:** Some sources produce duplicates or irrelevant roles.
- **Why it matters:** Less noise, lower cost.
- **Implementation:** Per-source unique-job rate, high-match rate and freshness; suggest disabling low-yield sources.
- **Data:** Discovery runs, matches.
- **AI involvement:** None.
- **Complexity:** Low.
- **Risks:** Minimal.
- **Priority:** P2.

### 32. Rules engine ("when X, prepare Y")
- **Problem:** Users want more automation for their best opportunities without giving up control.
- **Why it matters:** Removes repetitive clicks while keeping approvals.
- **Implementation:** Declarative rules (conditions on match, company, deadline) triggering *preparation* tasks only (resume, research, drafts) and urgent notifications; sends/submits remain manual.
- **Data:** Rules, events.
- **AI involvement:** None in the engine.
- **Complexity:** Medium.
- **Risks:** Runaway costs — budget limits (#40).
- **Priority:** P1.

### 33. Daily digest (email/push)
- **Problem:** Users do not open the dashboard every day.
- **Why it matters:** Keeps the loop alive with minimal attention.
- **Implementation:** Scheduled summary of top new matches, deadlines and pending approvals via email or mobile push; configurable.
- **Data:** Notifications, matches.
- **AI involvement:** Optional summary.
- **Complexity:** Low.
- **Risks:** Notification fatigue.
- **Priority:** P1.

### 34. Calendar sync for deadlines & interviews
- **Problem:** Deadlines and interviews live outside the user's calendar.
- **Why it matters:** Fewer missed deadlines.
- **Implementation:** Google Calendar OAuth; create events on approval; update on changes.
- **Data:** Deadlines, interview dates.
- **AI involvement:** None.
- **Complexity:** Low.
- **Risks:** Duplicate events; OAuth scope creep.
- **Priority:** P2.

### 35. Adapter SDK with recorded-fixture contract tests
- **Problem:** Career sites and portals change; adapters break silently.
- **Why it matters:** Adapter breadth is a long-term moat; maintenance must be cheap.
- **Implementation:** `scripts/new_adapter` scaffolding, record/replay HTTP cassettes and DOM snapshots, nightly canary runs against live sources that open issues on drift.
- **Data:** Recorded fixtures.
- **AI involvement:** Optional selector-repair suggestions.
- **Complexity:** Medium.
- **Risks:** Fixture staleness.
- **Priority:** P1.

### 36. LLM trace viewer & replay
- **Problem:** Debugging agent behaviour requires seeing exactly what the model saw.
- **Why it matters:** Transparency and faster fixes.
- **Implementation:** Store redacted prompts/outputs per task (opt-in, short retention), with tokens, cost, latency and validation outcome; replay against another model.
- **Data:** LLM calls (redacted).
- **AI involvement:** None.
- **Complexity:** Medium.
- **Risks:** Storing sensitive prompts — redaction + retention limits.
- **Priority:** P1.

### 37. Freshness SLOs & source breakage alerts
- **Problem:** A broken adapter silently stops discovery.
- **Why it matters:** Discovery freshness is the product's heartbeat.
- **Implementation:** SLOs on time-to-discovery and source success rate; Cloud Monitoring alerts; health badge in settings.
- **Data:** Source runs.
- **AI involvement:** None.
- **Complexity:** Low.
- **Risks:** Alert noise.
- **Priority:** P2.

### 38. Adaptive model cascade
- **Problem:** Using the best model for everything is expensive; the cheapest is sometimes wrong.
- **Why it matters:** Quality at minimal cost.
- **Implementation:** Try the cheap model; escalate only when schema validation or grounding checks fail or confidence is low; track cost per accepted artefact.
- **Data:** Validation outcomes, usage.
- **AI involvement:** Routing.
- **Complexity:** Medium.
- **Risks:** Latency from retries.
- **Priority:** P1.

### 39. Batch inference for bulk work
- **Problem:** Re-embedding or re-extracting thousands of jobs at interactive prices is wasteful.
- **Why it matters:** Large cost savings on non-urgent work.
- **Implementation:** Provider batch APIs for nightly backfills; results ingested by task handlers.
- **Data:** Job backlog.
- **AI involvement:** Same tasks, batched.
- **Complexity:** Medium.
- **Risks:** Batch latency; partial failures.
- **Priority:** P2.

### 40. Per-user AI budget with graceful degradation
- **Problem:** Automation can burn through API spend unexpectedly.
- **Why it matters:** Predictable costs.
- **Implementation:** Monthly budget per user and task; when exceeded, fall back to local heuristics and notify.
- **Data:** `llm_usage`.
- **AI involvement:** None.
- **Complexity:** Low.
- **Risks:** Silent quality drop — always notify.
- **Priority:** P2.

### 41. Local-model provider (fully offline mode)
- **Problem:** Some users do not want any profile data to leave their machine.
- **Why it matters:** Maximum privacy.
- **Implementation:** An `LLMProvider` for a local runtime (e.g. an OpenAI-compatible local server) and local embeddings.
- **Data:** None external.
- **AI involvement:** Local models.
- **Complexity:** Medium.
- **Risks:** Lower quality; hardware requirements.
- **Priority:** P3.

### 42. Anomaly detection on outbound actions
- **Problem:** Bugs or compromised sessions could trigger unusual volumes of drafts or sends.
- **Why it matters:** Defence in depth for external actions.
- **Implementation:** Baselines per user; alert and require step-up (#3) on spikes, new-domain bursts or unusual hours.
- **Data:** Audit log.
- **AI involvement:** None.
- **Complexity:** Medium.
- **Risks:** False positives blocking legitimate bursts.
- **Priority:** P2.
