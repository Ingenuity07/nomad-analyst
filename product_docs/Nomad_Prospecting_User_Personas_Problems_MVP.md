# Nomad Prospecting Engine — User Personas, Problems & MVP

## 1. Product Direction

Nomad should initially be an **AI prospect research engine** that turns a sales hypothesis into an evidence-backed list of companies and relevant people worth contacting.

Core question:

> **“Find me businesses worth talking to, and show me why.”**

Nomad is not initially:

- another Apollo
- another ZoomInfo
- another CRM
- another email sequencer
- another generic AI SDR
- another Google search wrapper
- a massive contact database

The product should focus on **discovery, research, evidence and actionable lead lists**.

---

## 2. Core Problem

A typical B2B seller already knows roughly what they sell and who they want to sell to. The difficult part is repeatedly researching the market.

Manual process:

```text
Define ICP / sales hypothesis
        ↓
Search Google / Maps / directories
        ↓
Open company websites
        ↓
Understand what company does
        ↓
Look for evidence of the problem
        ↓
Search LinkedIn / other sources
        ↓
Find relevant person
        ↓
Find contact information
        ↓
Create spreadsheet
        ↓
Decide whether company is worth contacting
```

Nomad should compress this into:

```text
Describe what you sell
+
Describe who you want
+
Describe the problem / opportunity
        ↓
Nomad researches the market
        ↓
Company discovery
        ↓
Evidence collection
        ↓
Account understanding
        ↓
Relevant-person discovery
        ↓
Actionable lead list
```

---

# 3. Core Job To Be Done

> **“Find me businesses worth talking to, and show me why.”**

The implementation details — scraping, APIs, LLM reasoning, enrichment, search providers — are supporting capabilities.

The customer is not buying “AI search”.

The customer is buying **better prospect discovery with less manual research**.

---

# 4. Primary Lead Object

Nomad should be **account-first**, rather than contact-first.

```text
Account
│
├── Company information
├── Why it matches
├── Evidence
├── Signals
├── Buying window
├── Relevant people
└── Sources
```

A contact without context is just a contact.

A useful prospect should explain:

- who the company is
- why it matches
- what evidence supports that
- what signal was detected
- who might care
- where the information came from

Example:

```text
ABC Logistics Ltd

WHY IT MATCHES
Large last-mile delivery operation.

EVIDENCE
• Multiple delivery locations
• Fleet-related hiring
• Delivery services advertised
• Operational expansion

RELEVANT PERSON
Operations Director

CONTACT
Email / LinkedIn / available contact data

SOURCES
Company website
Job posting
Business directory
Other verified sources
```

---

# 5. Persona 1 — Founder Doing Their Own Sales

## Who

Founder/owner of a small B2B company who personally handles sales.

Typical setup:

```text
Founder
+
small team
+
limited/no sales research team
```

## Problem

They know what they sell but don't have enough time to research potential customers.

Example:

> “I sell fleet-management software and want UK businesses operating commercial delivery fleets.”

They need to discover:

- relevant companies
- company type
- location
- fleet evidence
- growth evidence
- relevant decision maker
- contact details

## Current workflow

```text
Google
↓
Google Maps
↓
Company website
↓
LinkedIn
↓
Directories
↓
Spreadsheet
```

## Pain

- repetitive
- time-consuming
- inconsistent
- difficult to scale
- easy to miss good prospects

## Nomad value

Nomad acts as a research assistant.

The founder spends time deciding:

> “Which of these should I contact?”

instead of spending hours finding them.

---

# 6. Persona 2 — SDR / BDR

## Who

Sales Development / Business Development Representatives.

Typical workflow:

```text
Find accounts
↓
Find people
↓
Research
↓
Contact
↓
Book meetings
```

## Problem

They may receive targets such as:

> “Find UK construction companies that are expanding and identify operations/procurement decision makers.”

The research itself consumes significant time.

## Nomad value

Produce:

```text
Account
+
Evidence
+
Buying signal
+
Relevant person
+
Contact information
```

Nomad does not necessarily replace the SDR.

It replaces part of the **manual research-assistant work** the SDR currently performs.

---

# 7. Persona 3 — Small B2B Sales Team

## Who

Small sales organization:

```text
Founder / Sales Lead
+
2–5 salespeople
+
marketing support
```

## Problem

They repeatedly need new prospect lists.

Examples:

```text
UK logistics companies
```

```text
Companies opening new locations
```

```text
Companies hiring fleet managers
```

```text
Businesses with delivery operations
```

## Nomad value

Create repeatable discovery projects/lists.

Each list contains:

- companies
- evidence
- signals
- relevant people
- sources

Nomad becomes a repeatable market-research engine.

---

# 8. Persona 4 — Lead Generation Agency

## Who

Agency generating leads for multiple clients.

Example:

> Agency provides lead-generation services for roofing companies, IT companies and logistics companies.

## Problem

The agency repeatedly performs prospect research for multiple clients.

Current workflow can involve:

```text
Google
Google Maps
directories
LinkedIn
Apollo
spreadsheets
manual research
```

## Nomad value

Create separate research projects per client.

Example:

```text
Client:
Commercial Roofing Company

Target:
London commercial property companies

Evidence:
Large buildings
multiple properties
recent expansion
```

Nomad produces the researched account list.

## Why this persona matters

One agency can run many prospecting projects, creating potentially high recurring usage.

---

# 9. Persona 5 — Recruitment Agency

## Who

Recruiters and recruitment agencies searching for companies with hiring demand.

## Problem

They need to identify companies hiring for roles matching their candidate pool.

Example:

> “Find UK companies hiring Senior Python engineers that appear to be expanding engineering teams.”

## Nomad flow

```text
Company discovery
↓
Job postings
↓
Hiring signals
↓
Engineering growth
↓
Relevant department
↓
Potential hiring manager
↓
Evidence
```

## Output

```text
Company
Role
Hiring signal
Job URL
Relevant department
Potential hiring manager
Contact information
Evidence
```

---

# 10. Persona 6 — B2B Service Businesses

Examples:

- commercial cleaning companies
- security companies
- fleet-management providers
- IT managed-service providers
- accounting firms
- HR consultancies
- logistics providers
- field-service software companies
- marketing agencies
- business consultants

## Common problem

They have a definable target market but need to repeatedly identify businesses that fit.

Examples:

### Commercial cleaning

> Find offices with 100+ employees in London.

### Security

> Find warehouses and industrial facilities in Birmingham.

### Fleet management

> Find companies operating commercial fleets.

### HR consultancy

> Find companies rapidly hiring.

### IT MSP

> Find companies opening offices or expanding.

### Accounting

> Find growing SMEs.

Common question:

> **“Which businesses should I approach, and why now?”**

---

# 11. Who Should NOT Be the Initial Target

## Consumers

Example:

> “Find plumbers near me.”

Search/maps already solve this reasonably well.

## Massive enterprise database buyers

Companies needing huge historical datasets, massive contact databases and enterprise intent infrastructure are better served initially by established platforms.

## Users who only need email addresses

Email-data providers already specialize in this.

## Users who only need LinkedIn contacts

Existing professional prospecting platforms are stronger here.

## Pure mass-outreach users

Nomad should not initially position itself as:

> “Send thousands of AI-generated emails automatically.”

That is a later downstream capability with additional deliverability and compliance concerns.

---

# 12. Ideal Initial Customer

The strongest initial target is:

> **Small B2B sales teams, founders doing their own sales, and lead-generation agencies.**

Particularly those who:

- sell a specific product/service
- have a definable ICP
- repeatedly research prospects
- currently use spreadsheets/manual research
- need evidence about companies
- don't need a massive enterprise platform
- can manually validate discovered leads

---

# 13. Route Optimization — First Real Dogfooding Use Case

The existing Route Optimization product is an excellent real-world test case.

Example request:

> “Find UK businesses that operate multi-stop delivery or field-service operations and could benefit from route optimization.”

Potential sources:

```text
Google / Maps
Web
Business directories
Company websites
Job postings
Apify
Apollo
other available data sources
```

Potential output:

```text
Company
Website
Location
Business type
Delivery/field-service evidence
Fleet evidence
Number of locations
Relevant employee
Contact information
Source URLs
Reason route optimization may be useful
```

This gives Nomad a real feedback loop:

```text
Nomad finds prospects
        ↓
Human reviews
        ↓
Human contacts prospects
        ↓
Responses
        ↓
Feedback
        ↓
Learn which signals matter
```

---

# 14. Account-First Lead List

A normal database might provide:

| Name | Email | Company | Title |
|---|---|---|---|
| John | john@... | ABC | Manager |

Nomad should aim for:

| Company | Why Match | Evidence | Signal | Relevant Person | Contact |
|---|---|---|---|---|---|
| ABC Logistics | Delivery operation | Fleet hiring + locations | Expansion | Operations Director | Contact |

The **reason for discovery** should be visible.

---

# 15. Important Product Principle — Don't Over-Filter Early

During initial product validation, do not automatically discard leads based purely on an AI score.

Prefer:

```text
Strong evidence
Medium evidence
Weak evidence
```

and let humans review.

Human feedback can later improve:

- signal quality
- discovery queries
- relevance models
- scoring
- provider selection
- buying-window detection

The first goal is **useful recall + human review**, not perfect automated qualification.

---

# 16. MVP — Discovery → Research → Lead List

The initial MVP should focus only on:

```text
Discovery
    ↓
Research
    ↓
Lead List
```

Do not initially build:

- campaigns
- email automation
- CRM replacement
- advanced notifications
- automated outreach
- complex analytics
- autonomous sales agent

---

# 17. MVP User Flow

```text
User describes target
        ↓
Nomad understands sales hypothesis
        ↓
Discover companies
        ↓
Research companies
        ↓
Collect evidence
        ↓
Identify relevant people
        ↓
Create actionable lead list
        ↓
Human reviews
        ↓
Export / use leads
```

---

# 18. MVP Input

Eventually capture:

```text
What do you sell?
Who do you want to sell to?
Where?
What problem does your product solve?
What signals indicate they might need it?
Optional exclusions
Optional company-size constraints
Optional industry constraints
```

The user should be able to describe the sales problem naturally.

They should not need to understand search-engine syntax.

---

# 19. MVP Output

Each account should eventually contain:

```text
Company
Website
Location
Industry/category

Why this company matches

Evidence
    ├── source
    ├── observation
    └── freshness

Detected signals

Potential buying window

Relevant person(s)

Contact information where available

Source URLs

Confidence / evidence strength
```

---

# 20. Human Review Loop

For each lead:

```text
Useful
Not useful
Maybe
```

Potential feedback:

```text
Wrong industry
Wrong company size
No relevant problem
Excellent prospect
Already uses competitor
Wrong person
Evidence outdated
```

This feedback becomes valuable product data.

---

# 21. What the MVP Is NOT Trying to Solve

The first product does not need to answer:

> “Can Nomad sell the product for me?”

It needs to answer:

> **“Can Nomad reliably find the right businesses and give me enough evidence to decide whether they are worth contacting?”**

That is the first product milestone.

---

# 22. Product North Star

For every future feature ask:

> **Does this help the user find a better prospect, understand why they are a prospect, or identify the right person to talk to?**

If not, it is probably outside the core discovery MVP.

---

# 23. Current Product Thesis

> **Existing sales databases are good at telling users who exists. Nomad should focus on helping users discover who is worth pursuing by combining broad discovery, web research, evidence extraction, company understanding, and relevant-person identification.**

This is a product hypothesis to validate with real users.

---

# 24. What We Need to Validate Before Expanding

Before major backend expansion, validate:

1. What users currently search for.
2. What information they manually collect.
3. What makes them decide a company is worth contacting.
4. What evidence they trust.
5. Which sources they use.
6. Which information is missing from existing platforms.
7. How much time they spend per researched account.
8. Whether Nomad's discovered accounts are useful.
9. Which signals correlate with positive responses.
10. Which fields belong in the final lead record.

The architecture should be derived from these validated workflows.

---

# 25. Current Scope Boundary

## Build now

```text
Sales hypothesis
       ↓
Company discovery
       ↓
Company research
       ↓
Evidence
       ↓
Relevant people
       ↓
Lead list
       ↓
Human review
```

## Build later

```text
Lists
CRM integrations
Email drafting
Email sending
Campaigns
Reply detection
Automated monitoring
Adaptive scoring
Advanced analytics
Multi-channel orchestration
```

The immediate objective is to make **Discovery + Research + Lead Listing genuinely useful** before expanding downstream into sales automation.

---

# 26. Next Product-Discovery Step

This document establishes the concrete personas, problems and MVP.

The next step is to incorporate the additional product suggestions and then converge on:

1. **Primary ICP/persona**
2. **Exact user problem**
3. **Ideal user input**
4. **Ideal lead record**
5. **Discovery sources**
6. **Evidence model**
7. **Human-review workflow**
8. **Success metrics**
9. **MVP feature boundary**

Only after those are concrete should the backend/tool architecture be finalized.
