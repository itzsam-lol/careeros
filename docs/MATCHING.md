# Matching

Every discovered role is scored against **your verified profile** (`careeros/matching/`). The
score is relevance to you, never a prediction of being hired.

## 1. Eligibility (hard checks)

A role that fails any of these is marked *Not eligible*, and the app hides it by default:

- **Location**
  - Outside your target countries or cities.
  - Remote, but only for people in another country ("Remote, Turkey").
- **Work authorisation**
  - The country needs a visa and the posting doesn't sponsor one.
  - In *sponsorship-only* countries (Australia for you), a role that doesn't explicitly offer a
    visa is hidden automatically.
- **Experience, seniority, degree, student status, graduation year**, when the posting states
  them.
- **Your exclusions:** companies and title keywords.

## 2. Requirement coverage

Each required or preferred skill in the posting is checked against the profile:

| Status | Meaning |
| --- | --- |
| Matched | A verified skill, or a verified project or job that used it |
| Partial | Unverified evidence, a broader skill implied by a specific tool you used (FastAPI → REST APIs), or an adjacent skill (PyTorch for TensorFlow) |
| Missing | Nothing on the profile; shown as a gap, never invented |

## 3. Scores

Six dimensions, weighted into the overall score:

| Dimension | Weight | What it measures |
| --- | --- | --- |
| Skills | 30% | Coverage of the required (double weight) and preferred skills |
| Projects | 20% | The best single project for the job's skills, or its closest project write-up |
| Experience | 15% | Relevant work, plus how well the role's **level** fits you |
| Domain | 15% | The job's field vs. the fields in your target roles and technologies |
| Preferences | 15% | Role type, location, employment type, work style, pay |
| Research | 5% | Research and publications (25% for research roles) |

**Role type.** The title tells what the job actually is: software engineering, data and AI,
research, hardware, product, design, sales, support, HR, legal, finance or operations.

- A role in a different line of work from all of your target roles is scored down by 40%, and the
  explanation says so. A sales role at an AI company no longer looks like an AI role.
- Titles that don't state a clear function are not penalised.

**Level.** For a student or recent graduate, intern and entry-level roles fit best.

- Mid-level roles ("Engineer II") are a stretch, and the explanation mentions it.
- Senior, lead and manager roles fail eligibility.

## 4. Explanation

Every match lists:

- **Strengths:** skills covered, evidence from your verified work, location and authorisation.
- **Gaps:** missing skills and failed checks.
- **Concerns:** a role type outside your targets, a level stretch, unknown authorisation.

If an LLM is configured it may rewrite the explanation, but every strength must cite your
evidence, and numbers must appear in that evidence.

## When things change

- Editing the profile re-scores open matches (profile version).
- A new scorer version (currently `match-v3`) re-scores open matches automatically, 500 a minute.
- After improving location or level detection, run
  `python -m careeros.tools.refresh_jobs` to recompute stored countries and levels.
