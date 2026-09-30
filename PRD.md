# Client Acquisition Tool — Product Requirements Document

## 1. Product Summary

The Client Acquisition Tool is a personal CRM and prospecting platform for web developers and small agencies.

It helps the user discover businesses that may need a better website, analyze their existing website, generate a personalized homepage mockup, prepare outreach, and track the prospect through the sales process.

Core workflow:

```text
Prospect
→ Analyze
→ Opportunity
→ Mockup
→ Outreach
→ Follow-up
→ Reply
→ Meeting
→ Proposal
→ Won/Lost
```

---

# 2. Problem

Client acquisition is often fragmented across:

* Google Maps
* Google Search
* spreadsheets
* browser tabs
* screenshots
* email
* notes
* AI tools
* design tools
* CRMs

The developer repeatedly performs the same tasks:

1. Find a business.
2. Visit its website.
3. Determine whether the website needs improvement.
4. Capture screenshots.
5. Research the business.
6. Create a redesign concept.
7. Write outreach.
8. Follow up.
9. Track the response.

The product combines these steps into one workflow.

---

# 3. Target Users

## Primary Users

### Independent Web Developer

A developer who needs a consistent way to find and contact potential clients.

### Freelancer

A freelancer who wants to manage prospects without using a large CRM.

### Small Web Agency

An agency that wants a lightweight internal prospecting system.

---

# 4. Product Goal

Reduce the time required to move from:

```text
Potential Business
```

to:

```text
Personalized Outreach
```

while keeping the user in control of the final communication.

---

# 5. MVP Scope

## Lead Management

* create lead
* edit lead
* delete lead
* search
* filtering
* sorting
* pagination
* tags
* notes
* contacts
* lead status
* CSV import

## Website Audit

* URL validation
* website accessibility check
* desktop screenshot
* mobile screenshot
* HTTPS check
* responsive check
* CTA check
* contact-form check
* navigation check
* basic SEO checks
* basic content analysis
* brand extraction
* recommendations

## Mockups

* brand profile
* mockup generation
* generation status
* preview
* versioning
* regeneration
* archive
* comparison

## Outreach

* outreach templates
* personalized generation
* editable message
* subject
* message body
* copy
* manual sending workflow
* contacted status
* replied status
* outreach history

## Follow-ups

* schedule
* today
* upcoming
* overdue
* complete
* reschedule
* cancel

## Pipeline

* Kanban
* drag and drop
* persistent statuses
* rollback on failure

## Analytics

* lead count
* audits
* mockups
* contacted
* replies
* meetings
* proposals
* wins
* losses
* conversion metrics

---

# 6. Non-Goals

Do not build initially:

* SaaS billing
* complex multi-tenancy
* public marketplace
* accounting
* autonomous sales agents
* automatic LinkedIn messaging
* automatic WhatsApp messaging
* large marketing automation platform
* complex team permissions

These can be added later if the core workflow proves useful.

---

# 7. Functional Requirements

## FR-01 — Lead Creation

The user must be able to create a lead with:

* business name
* industry
* location
* website
* contact information
* source
* tags
* notes

---

## FR-02 — Lead Search

The user must be able to search by:

* business name
* website
* contact
* city
* industry
* tags

---

## FR-03 — Website Audit

The user must be able to start an audit for a public website.

The audit should capture:

* screenshots
* technical checks
* UX findings
* design findings
* mobile findings
* basic SEO findings
* brand information

---

## FR-04 — Audit Results

The user must see:

* screenshots
* findings
* scores
* issues
* recommendations
* brand information

---

## FR-05 — Mockup Generation

The user can generate a homepage concept based on:

* business
* website
* brand
* audit findings
* selected style
* selected sections

---

## FR-06 — Mockup Versioning

Every regeneration creates a new version.

Example:

```text
Mockup V1
Mockup V2
Mockup V3
```

Existing versions must not be silently overwritten.

---

## FR-07 — Outreach Generation

The system generates personalized outreach using:

* business name
* website findings
* industry
* relevant improvements
* mockup information

The user must be able to edit the result before sending.

---

## FR-08 — Follow-ups

The user can:

* schedule
* complete
* reschedule
* cancel

follow-ups.

---

## FR-09 — Pipeline

The user can move prospects through:

```text
New
Qualified
Audit Complete
Mockup Ready
Contacted
Follow-up
Replied
Meeting
Proposal
Won
Lost
```

---

## FR-10 — Analytics

The system provides descriptive metrics about the user's acquisition activity.

Examples:

* leads added
* audits completed
* mockups generated
* contacts made
* replies received
* meetings recorded
* proposals recorded
* wins/losses

---

# 8. User Stories

## Prospecting

> As a developer, I want to quickly add a business so that I can start qualifying it.

> As a developer, I want to import leads from CSV so that I don't have to manually create every record.

> As a developer, I want to filter leads by industry and location so that I can focus my prospecting.

## Auditing

> As a developer, I want to analyze a website so that I can understand its current state.

> As a developer, I want desktop and mobile screenshots so that I can visually inspect the website.

> As a developer, I want extracted brand information so that generated mockups feel relevant.

## Mockups

> As a developer, I want to create a personalized homepage concept so that I can demonstrate a possible redesign.

## Outreach

> As a developer, I want personalized outreach drafts so that I can reduce repetitive writing.

> As a developer, I want to edit AI-generated outreach before sending it.

## Follow-ups

> As a developer, I want follow-up reminders so that I don't forget prospects.

---

# 9. Success Metrics

The application should track:

* leads added
* leads audited
* audits completed
* mockups generated
* outreach drafts created
* leads contacted
* replies recorded
* meetings recorded
* proposals recorded
* wins recorded
* losses recorded
* follow-ups completed
* average time from lead creation to contact

These are measurement metrics, not guarantees of business outcomes.

---

# 10. UX Principles

1. Always make the next action obvious.
2. Keep lead context visible.
3. Generated content must remain editable.
4. Never hide errors.
5. Keep prospecting fast.
6. Avoid unnecessary configuration.
7. Keep the user in control of outreach.
8. Do not overwhelm the dashboard with information.
9. Prefer progressive disclosure.
10. Make the mockup and audit experience visually strong.

---

# 11. MVP Acceptance Criteria

The MVP is complete when the user can perform:

```text
Create Lead
    ↓
Analyze Website
    ↓
Review Audit
    ↓
Generate Mockup
    ↓
Review Mockup
    ↓
Generate Outreach
    ↓
Edit Outreach
    ↓
Mark Contacted
    ↓
Schedule Follow-up
    ↓
Record Reply
    ↓
Meeting
    ↓
Proposal
    ↓
Won / Lost
```

All important state changes must persist after refreshing the browser.
