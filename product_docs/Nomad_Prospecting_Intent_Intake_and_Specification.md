# Nomad Prospecting Engine
## Prospecting Intent Intake, Structured Specification & Human Confirmation

**Status:** Product / architecture definition  
**Scope:** User input, intent understanding, specification generation, confirmation, and deterministic handoff into prospect discovery  
**Primary objective:** Replace ambiguous free-text-to-agent execution with a structured, reviewable contract between the user's intent and the Prospecting Engine.

---

# 1. Executive Summary

Nomad's current prospecting flow can accept a broad natural-language description and pass it into the backend/LLM layer for interpretation and discovery.

That is useful for a prototype, but it creates an important product and engineering problem:

> **The user's intent is probabilistic and ambiguous, while the execution system needs clear, reproducible requirements.**

The proposed solution is a hybrid model:

```text
Natural-language user input
        ↓
LLM intent understanding
        ↓
Structured Prospecting Specification
        ↓
Validation / missing-information detection
        ↓
Human review and correction
        ↓
Confirmed Prospecting Specification
        ↓
Deterministic prospecting execution
```

This preserves the convenience of natural language while creating a stable contract for the discovery engine.

The key principle is:

> **Use AI to understand the user's intent; use a structured specification and deterministic systems to execute it.**

---

# 2. Why the Current Single-Description Approach Is Not Enough

The current conceptual flow is:

```text
User paragraph
     ↓
LLM
     ↓
Agent
     ↓
Search / research
```

This is acceptable for experimentation but creates several problems.

## 2.1 Ambiguity

Example:

> "Find businesses that might need route optimization."

The system does not know:

- which country
- which business types
- whether delivery or field service matters
- what company size matters
- what evidence indicates need
- which people should be found
- whether the user wants companies or people
- whether this is a sales, partnership, research, or other objective

The LLM will fill missing information using assumptions.

Those assumptions may be wrong.

---

## 2.2 Inconsistent execution

Two semantically similar requests can produce different search behavior because the raw prompt is interpreted differently.

That makes the system difficult to:

- debug
- evaluate
- reproduce
- compare
- cache
- improve

---

## 2.3 Hidden assumptions

If the LLM silently infers:

> "Large fleet = more than 50 vehicles"

the user may never realize that assumption was made.

Nomad should expose important interpretations before research begins.

---

## 2.4 Difficult user correction

With one large text prompt, correcting one misunderstanding often means rewriting the entire request.

A structured interpretation allows the user to edit only the misunderstood part.

---

# 3. Product Insight: "Product" Is Not the Core Abstraction

The prospecting engine should not assume the user always has a product.

A user may have:

### A Product

> "I sell route optimization software."

### A Service

> "We provide commercial cleaning services to large offices."

### A Consultancy

> "We help companies reduce cloud infrastructure costs."

### An Agency

> "We provide outsourced accounting for growing startups."

### A Recruitment Objective

> "We want to find companies hiring senior Python engineers."

### A Partnership Objective

> "We are looking for logistics companies that could partner with us."

### A Supplier Search

> "Find manufacturers that can produce this component."

### Market Research

> "I want to understand which UK businesses are likely to need fleet management."

### Competitive Research

> "Find companies using competing products."

### Investment / Research Thesis

> "Find companies expanding into EV infrastructure."

Therefore the system should model the broader concept:

> **Prospecting Objective**

rather than forcing every request into a "product" model.

---

# 4. Prospecting Objective Types

The system can internally classify an objective into categories such as:

```text
SELL
SERVICE
PARTNERSHIP
SUPPLIER_SEARCH
RECRUITING
MARKET_RESEARCH
COMPETITIVE_RESEARCH
INVESTMENT_RESEARCH
OTHER
```

These should generally be **inferred by the LLM**, not forced on the user as a dropdown during initial input.

The user should be able to correct the interpretation.

---

# 5. The Three-Question Intake Model

The preferred initial UX is a small number of natural-language questions.

Do not create a large form containing dozens of structured fields.

That would turn Nomad into another traditional prospecting database interface.

Instead use three descriptive questions.

---

## Question 1 — Objective

### "What are you trying to achieve?"

Placeholder:

> Describe what you're looking for in your own words.

Examples:

> "I want to find UK businesses that could benefit from our route optimization software."

> "I'm looking for UK manufacturers that could become suppliers for our electronics business."

> "I want to find companies currently hiring senior Python engineers."

Purpose:

```text
Objective / Intent
```

---

## Question 2 — Target

### "Who or what are you looking for?"

Examples:

> "Companies operating delivery fleets with multiple drivers."

> "UK SaaS companies with 50–500 employees."

> "Operations managers responsible for fleet operations."

Purpose:

```text
Target Entity
```

---

## Question 3 — Relevance / Qualification

### "What would make a result a good match?"

Examples:

> "They should have multiple delivery locations, a sizeable fleet, or evidence that they're expanding delivery operations."

> "They should be growing quickly and hiring engineers."

> "They should have manufacturing capabilities for small electronic components."

Purpose:

```text
Problem / Qualification / Evidence Hypothesis
```

---

# 6. Why Three Questions Instead of One

A single question mixes several concepts:

```text
What do you sell?
Who do you want?
Why might they need it?
Where?
Who should we contact?
```

The three-question approach separates the most important dimensions without forcing users to understand the internal data model.

It preserves:

- natural language
- low user effort
- flexibility

while improving:

- deterministic interpretation
- validation
- editability
- reproducibility

---

# 7. Do Not Force Three Questions When They Are Unnecessary

The intake should be adaptive.

If the user gives:

> "Find UK logistics companies with more than 50 vehicles."

the system already has:

```text
Target: logistics companies
Location: UK
Constraint: >50 vehicles
```

It should not ask unnecessary questions.

Instead it can generate an interpretation and request confirmation.

If the user says:

> "Find companies that might need our software."

the system should detect missing information and ask a focused follow-up:

> "What does your software help companies do?"

Therefore the intake layer needs:

```text
Intent understanding
+
Missing-information detection
```

rather than a rigid questionnaire.

---

# 8. The Intent Parser

The first LLM stage should not immediately search the web.

Its job is:

> **Understand what the user means and convert it into a structured specification.**

Architecture:

```text
User
 ↓
Natural Language Input
 ↓
Intent Parser
 ↓
ProspectingSpecification
 ↓
Validation
 ↓
Human Confirmation
 ↓
Execution
```

This is a critical architectural boundary.

---

# 9. ProspectingSpecification

The `ProspectingSpecification` becomes the contract between the Intelligence Layer and the Prospecting Engine.

Conceptual structure:

```text
ProspectingSpecification

├── objective
├── objective_type
├── target_entity
├── target_description
├── geography
├── industries
├── company_constraints
├── people_constraints
├── problem_hypothesis
├── qualification_signals
├── exclusion_rules
├── requested_information
└── research_depth
```

Not every field needs to be populated.

Fields can be:

- explicit
- inferred
- unknown
- confirmed

---

# 10. Example — Route Optimization

User input:

### Objective

> "I want to find businesses that could use our route optimization software."

### Target

> "UK companies that have drivers making multiple deliveries every day."

### Good match

> "Companies with larger fleets, multiple delivery locations, field-service operations, or evidence that they're expanding their delivery operations."

The LLM can produce a structure conceptually like:

```json
{
  "objective_type": "SELL",
  "objective": "Identify UK businesses that could benefit from route optimization software.",
  "target": {
    "entity_type": "company",
    "geography": ["United Kingdom"],
    "industries": [
      "logistics",
      "delivery",
      "field_services"
    ]
  },
  "problem_hypothesis": {
    "problem": "Inefficient multi-stop routing and fleet operations",
    "solution": "Route optimization software"
  },
  "qualification_signals": [
    "multiple delivery locations",
    "commercial vehicle fleet",
    "field-service operations",
    "delivery-related hiring",
    "operational expansion"
  ],
  "target_people": [
    "Operations Manager",
    "Fleet Manager",
    "Logistics Manager",
    "Operations Director"
  ],
  "geography": {
    "countries": ["United Kingdom"]
  }
}
```

The exact schema should be implemented as a typed backend contract rather than free-form JSON.

---

# 11. Human Confirmation Is a Core Product Feature

Nomad should show the user:

# Here's what Nomad understood

### Objective

**Find potential customers**

### Target

**UK companies operating multi-stop delivery or field-service operations**

### Why they may be relevant

- Commercial vehicle fleet
- Multiple delivery locations
- Field-service operations
- Delivery-related hiring
- Expansion signals

### People to look for

- Operations Director
- Fleet Manager
- Logistics Manager
- Operations Manager

### Geography

**United Kingdom**

Then ask:

> **"Is this what you're looking for?"**

Actions:

```text
[ Edit ]     [ Confirm & Start Research ]
```

The system should not start expensive discovery before confirmation unless the user explicitly chooses an unconfirmed/fast mode in a future version.

---

# 12. Structured Editing

The user should not need to rewrite the entire prompt.

Example:

```text
Target companies
[ UK logistics and delivery companies          ✎ ]

Relevant signals
[ Multiple locations                           ✎ ]
[ Fleet-related hiring                         ✎ ]
[ Delivery expansion                           ✎ ]

People
[ Operations Director                          ✎ ]
[ Fleet Manager                                ✎ ]

Geography
[ United Kingdom                               ✎ ]
```

This makes the LLM interpretation:

- transparent
- editable
- reviewable
- auditable

---

# 13. Separate User Requirements, Inferences and Facts

This is one of the most important data-model principles.

Nomad should distinguish:

## User Requirements

What the user explicitly said.

Example:

> "Find companies with large delivery fleets."

## Inferred Requirements

What the LLM believes the user meant.

Example:

> Fleet size is likely an important qualification signal.

## Discovered Facts

What external sources actually show.

Example:

> Company operates 120 commercial vehicles.

These must not be mixed together.

---

# 14. Hypothesis → Evidence Model

A user may say:

> "Find companies that probably have inefficient delivery operations."

That is not a fact.

It is a:

```text
Problem Hypothesis
```

Nomad should search for evidence.

Example:

```text
USER HYPOTHESIS
Inefficient delivery operations

        ↓

SEARCH

        ↓

EVIDENCE
Company operates 80 vehicles
+
Company makes 500 daily deliveries
+
Company is hiring route planners

        ↓

ACCOUNT ASSESSMENT

        ↓

Strong evidence of potential relevance
```

This gives Nomad a powerful conceptual model:

```text
User Claim
    ↓
Hypothesis
    ↓
Research
    ↓
Evidence
    ↓
Account Assessment
```

---

# 15. Avoid False Precision in Early Scoring

Do not immediately collapse every lead into:

> 87/100

This can create false confidence.

Instead expose interpretable dimensions:

```text
Target Match: HIGH

Evidence Strength: HIGH

Problem Relevance: MEDIUM
```

Later, after real user feedback and conversion data, these can be combined into a more sophisticated score.

---

# 16. Adaptive Missing-Information Detection

The Intent Parser should determine whether the request contains enough information to create a useful specification.

Example:

### User

> "Find companies that might need our software."

System detects:

```text
Missing:
- what the software does
- likely target
- geography
```

Ask the smallest useful question.

For example:

> "What problem does your software solve, and which types of organizations do you think experience that problem?"

Do not ask the user to fill ten fields.

---

# 17. Recommended End-to-End Architecture

```text
                         USER
                           │
                           ▼
                 Natural Language Input
                           │
                           ▼
                  ┌────────────────┐
                  │  Intent Parser │
                  │      LLM       │
                  └───────┬────────┘
                          │
                          ▼
             ProspectingSpecification
                          │
                   Validation Layer
                          │
                          ▼
                  Missing Info Check
                          │
              ┌───────────┴───────────┐
              │                       │
         Missing info             Sufficient
              │                       │
              ▼                       ▼
       Focused question        Human confirmation
                                      │
                                      ▼
                         Confirmed Prospecting Spec
                                      │
                                      ▼
                           Prospecting Planner
                                      │
                    ┌─────────────────┼────────────────┐
                    ▼                 ▼                ▼
                Discovery          Research       Enrichment
                  Tools             Tools            Tools
                    │                 │                │
                    └─────────────────┼────────────────┘
                                      ▼
                                   Evidence
                                      │
                                      ▼
                               Account / Leads
```

---

# 18. Where the Existing Nomad Architecture Fits

This design does not require throwing away the current architecture.

It gives existing components a clearer role.

### Existing LLM Router

Responsible for selecting/executing the model used by:

```text
Intent Parser
Research agents
Analysis
Other LLM tasks
```

### Existing LangGraph / ReAct

Should operate primarily **after the confirmed specification** when adaptive research is required.

### Existing Tool Registry

Provides discovery/research/enrichment capabilities.

### Existing Prospecting Providers

Remain implementation details behind tools/providers.

### Existing Celery

Executes long-running discovery/research after confirmation.

Therefore:

```text
Intent Parser
    ↓
Confirmed Specification
    ↓
LangGraph / deterministic workflows
    ↓
Tool Registry
    ↓
Providers
```

---

# 19. Important Architectural Rule

The Intelligence Layer should not directly control external integrations.

Prefer:

```text
LLM
 ↓
Specification
 ↓
Planner / Agent
 ↓
Tool
 ↓
Provider
 ↓
External service
```

Not:

```text
LLM
 ↓
Apollo
 ↓
Google
 ↓
LinkedIn
 ↓
DuckDuckGo
```

This keeps the intelligence layer independent from vendor implementations.

---

# 20. Determinism Boundary

The system should intentionally divide responsibilities.

## Probabilistic

Use LLMs for:

- interpreting natural language
- classifying objective
- extracting target concepts
- generating hypotheses
- identifying potential signals
- interpreting evidence
- adaptive research planning

## Deterministic

Use normal application logic for:

- validation
- schema enforcement
- human confirmation
- database persistence
- deduplication
- exclusions
- pagination
- rate limits
- retries
- permissions
- provider execution
- audit logs
- lead state transitions

This boundary is essential for reliability.

---

# 21. Why This Approach Is Strong

The proposed design gets the best of both worlds.

### Natural UX

Users can explain their goals normally.

### Structured execution

The backend gets a typed specification.

### Transparency

Users can see what Nomad understood.

### Correction

Users can fix mistakes before expensive research starts.

### Reproducibility

A confirmed specification can be stored and rerun.

### Debuggability

A research run can be tied back to the exact specification.

### Future learning

Nomad can compare:

```text
User hypothesis
vs
Nomad interpretation
vs
discovered evidence
vs
human feedback
vs
actual outcome
```

---

# 22. Cold Product Assessment

## Current approach

```text
User paragraph
     ↓
LLM
     ↓
Agent
     ↓
Search
```

### Good for

- prototype
- demos
- experimentation

### Weaknesses

- ambiguity
- inconsistent searches
- hidden assumptions
- difficult debugging
- difficult evaluation
- difficult reproducibility
- difficult editing
- difficult caching
- difficult comparison between runs

---

## Proposed approach

```text
2–3 natural inputs
     ↓
LLM interpretation
     ↓
Structured specification
     ↓
Human confirmation
     ↓
Deterministic execution
```

### Assessment

**Strong direction.**

The architecture preserves the flexibility of AI while introducing a clear deterministic contract.

The critical design challenge is to avoid turning the three questions into a large traditional search form.

---

# 23. Recommended Product Flow

A mature first version can feel like:

```text
┌──────────────────────────────────────────────┐
│ Tell Nomad what you're trying to accomplish. │
│                                              │
│ [..........................................] │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│ Who or what are you looking for?             │
│                                              │
│ [..........................................] │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│ What would make a result a good match?      │
│                                              │
│ [..........................................] │
└──────────────────────────────────────────────┘

                    [ Understand Request ]
```

Nomad then presents:

```text
Here's what I understood

Objective:
Find potential customers

Target:
UK delivery businesses

Relevant signals:
• Fleet operations
• Multiple locations
• Delivery expansion

People:
• Operations Director
• Fleet Manager

Geography:
United Kingdom

[ Edit ]     [ Confirm & Start Research ]
```

---

# 24. MVP Contract

The first implementation should establish these stages:

```text
1. Collect
2. Interpret
3. Validate
4. Ask for missing information if necessary
5. Present structured interpretation
6. Allow edits
7. Confirm
8. Persist confirmed specification
9. Start prospecting
10. Associate all resulting research with the specification
```

The `ProspectingSpecification` should become the root context for a discovery run.

---

# 25. Suggested Persistence Model

At a conceptual level:

```text
ProspectingRequest
        │
        ├── raw_user_input
        ├── parsed_specification
        ├── interpretation_version
        ├── status
        └── created_at
                │
                ▼
       ProspectingSpecification
                │
                ├── objective
                ├── target
                ├── hypotheses
                ├── signals
                ├── constraints
                ├── geography
                └── people criteria
                │
                ▼
         DiscoveryRun(s)
                │
                ▼
           LeadCompany
                │
                ├── Evidence
                ├── Signals
                └── LeadContact
```

This makes the user's intent traceable through the entire system.

---

# 26. Future Benefits

Once this contract exists, future features become easier.

The same specification can power:

- rerunning discovery
- scheduled monitoring
- saved prospecting projects
- comparing discovery runs
- changing providers
- CRM export
- human feedback
- adaptive scoring
- buying-window monitoring
- agentic research
- campaign creation later

For example:

```text
Confirmed Specification
        ↓
Run now
```

Later:

```text
Confirmed Specification
        ↓
Run every Monday
        ↓
Find new accounts
        ↓
Detect changed signals
        ↓
Notify user
```

---

# 27. Product North Star

For every future feature ask:

> **Does this help the user find a better prospect, understand why they are a prospect, or identify the right person to talk to?**

If not, it is probably outside the core discovery MVP.

---

# 28. Final Product Principle

Nomad should not try to make the user deterministic.

Humans naturally describe goals ambiguously.

Instead:

> **Let the user speak naturally, let the LLM interpret, make the interpretation explicit, let the human correct it, and only then let the deterministic system execute.**

That gives Nomad:

```text
Natural language
      +
AI understanding
      +
Human confirmation
      +
Structured state
      +
Deterministic execution
```

This should become the foundation for the next generation of the Prospecting Engine.
