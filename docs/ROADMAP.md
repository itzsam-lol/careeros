# Roadmap: next phase

What is built is listed in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md). This is the plan for
what comes next, in order. The rules stay the same:

- every application or email needs an explicit approval;
- no CAPTCHA, login or bot-protection bypass;
- nothing is scraped from sites whose terms forbid it.

## 1. Apply kit (done)

Make applying to a matched role take two minutes instead of twenty.

- A per-job **Apply kit** screen that collects everything in one place:
  - the tailored résumé PDF and cover letter;
  - copy-ready answers to common application questions (from the profile's *answers* section:
    notice period, expected stipend or salary, work authorisation, graduation date, links);
  - the apply link.
- **"I applied"** in one tap: sets the tracker stage, applied date and a 7-day follow-up reminder.
- Highlight portal questions that need a fresh answer (e.g. "Why this company?") and draft one from
  the company insights and verified profile, for the user to edit.

## 2. Email with approval (done)

- Connect Gmail with an app password (Google Account > Security > App passwords), stored encrypted.
  An OAuth client in testing mode signs you out every 7 days, and publishing it needs Google's
  review for the Gmail scopes; an app password needs neither.
- Outreach drafts (referral request, follow-up, thank-you) get a **Send** button. Each send shows the
  final email and needs a tap to approve. `AUTO_SEND_EMAILS` stays off.
- Daily sending limit, an audit-log entry per email, and reply detection (`REPLY_RECEIVED` alerts).

## 2b. Instant push alerts (needs a one-time Firebase step)

- The server pushes every alert through Firebase Cloud Messaging as it is created, authenticated
  with the VM's own service account (no key files). Built and deployed; it switches on once
  Firebase is added to the CareerOS GCP project and the app is rebuilt with its config.
- Needs from you: add Firebase to the existing GCP project in the Firebase console (free; it asks
  you to accept Firebase's terms).

## 3. More sources

- **iCIMS, SuccessFactors, Eightfold and Phenom** career sites, which many Indian IT and services firms
  use (Mphasis, Persistent, Infosys, Wipro), where they expose public JSON feeds.
- **Campus and graduate programme calendars:** recurring programmes (Mastercard Launch, CommBank
  grads, Atlassian grads) tracked even before the posting opens, with an alert when it does.
- Re-probe the catalogue monthly; drop dead boards and add new verified ones.

Out of scope: LinkedIn, Indeed and Naukri (no public API; their terms forbid scraping), Internshala and
Unstop (no API), and Workday tenants behind bot protection (Dell, Qualcomm, Walmart).

## 4. Smarter matching (optional, billable)

- Enable an LLM provider (Gemini or Claude via Bedrock) for job-description extraction and grounded
  rephrasing. That gives better skill extraction from messy postings and more natural cover letters.
- Costs money per call, so it only runs on roles that pass eligibility. It needs your explicit OK
  before it is switched on.

## 5. Insights

- A weekly summary: new roles found, applications sent, responses, interviews, and which skills keep
  appearing as gaps (with the projects that would close them).
- Funnel by company type (startup, MNC, GCC) and source, to show where applications get replies.

## 6. Assisted form filling (later, careful)

- On a laptop only: open the application form in the user's own browser and pre-fill it from the
  profile. The user reviews it and presses Submit. `AUTO_SUBMIT_APPLICATIONS` stays off; nothing
  runs on the server with the user's accounts.
