# Client Acquisition Tool — Implementation Plan

## 1. Development Strategy

Build the core acquisition loop first.

Priority:

```text
1. Leads
2. Website Audit
3. Mockups
4. Outreach
5. Follow-ups
6. Pipeline
7. Analytics
```

Do not spend significant time polishing the dashboard before the lead-to-client workflow works.

---

# Phase 0 — Foundation

## Goals

Create a stable development foundation.

### Tasks

* create repository
* initialize frontend
* initialize backend
* configure PostgreSQL
* configure environment variables
* configure Alembic
* configure linting
* configure formatting
* create health endpoint
* establish API error structure
* configure logging
* configure CORS
* establish routing

### Deliverable

Running:

```text
React Frontend
+
FastAPI Backend
+
PostgreSQL
```

---

# Phase 1 — Design System

### Tasks

Create:

```text
Button
Input
Textarea
Select
Checkbox
Radio
Switch
Badge
Card
Modal
Drawer
Toast
Skeleton
EmptyState
DataTable
Pagination
```

Create:

```text
AppShell
Sidebar
Topbar
PageHeader
```

Define:

* typography
* colors
* spacing
* shadows
* radius
* responsive behavior

### Deliverable

Reusable design system matching `Design.md`.

---

# Phase 2 — Database

Implement:

```text
Leads
Contacts
Website Audits
Brand Profiles
Mockups
Outreach Templates
Outreach Messages
Follow-ups
Activities
```

Add:

* migrations
* indexes
* constraints
* seed data

### Deliverable

Stable versioned PostgreSQL schema.

---

# Phase 3 — Lead CRM

### Backend

Implement:

* CRUD
* search
* filtering
* pagination
* sorting
* contacts
* notes
* tags
* statuses
* CSV import
* bulk updates

### Frontend

Implement:

```text
Lead List
Add Lead
Edit Lead
Lead Details
Contacts
Pipeline
```

### Deliverable

Complete lead-management workflow.

---

# Phase 4 — Website Audit

### Tasks

* URL validation
* SSRF protection
* Playwright
* desktop screenshot
* mobile screenshot
* HTTPS check
* responsive check
* CTA check
* contact-form check
* navigation check
* SEO/content checks
* brand extraction
* opportunity scoring
* persistence
* retry handling
* error handling
* private storage

### Deliverable

User can:

```text
Select Lead
→ Analyze Website
→ Wait
→ Review Results
```

---

# Phase 5 — Mockups

### Tasks

* brand profile
* mockup provider abstraction
* prompt builder
* generation
* storage
* job status
* preview
* thumbnails
* versioning
* comparison
* regeneration
* archive

### Deliverable

User can create:

```text
V1
V2
V3
```

for a prospect.

---

# Phase 6 — Outreach

### Tasks

* templates
* template variables
* context builder
* text provider abstraction
* generation
* editable editor
* copy action
* manual send workflow
* contacted state
* replied state
* history

### Deliverable

User can create personalized outreach for a lead.

---

# Phase 7 — Follow-ups

### Tasks

* create
* today
* upcoming
* overdue
* complete
* reschedule
* cancel
* activity timeline integration

### Deliverable

The user can reliably track follow-up work.

---

# Phase 8 — Analytics

### Tasks

* overview
* pipeline
* outreach
* conversion
* date filtering
* industry breakdown
* city breakdown
* source breakdown

### Deliverable

User can understand acquisition activity over time.

---

# Phase 9 — Optional Automation

Only after the core product is stable.

Potential additions:

```text
Redis
Background Worker
Scheduled Jobs
n8n
Notifications
```

Automation must remain user-controlled.

---

# Phase 10 — Testing

## Backend

Test:

* services
* API endpoints
* URL validation
* SSRF protection
* opportunity scoring
* provider failures

## Frontend

Test:

* components
* forms
* validation
* loading states
* error states

## E2E

Critical workflow:

```text
Create Lead
→ Audit
→ Mockup
→ Outreach
→ Contact
→ Follow-up
→ Reply
→ Meeting
→ Proposal
→ Won/Lost
```

---

# Phase 11 — Final Polish

Tasks:

* responsive QA
* accessibility QA
* loading states
* empty states
* error states
* dark mode
* performance optimization
* security review
* dependency audit
* documentation
* deployment

---

# Recommended Build Order

```text
Foundation
    ↓
Design System
    ↓
Database
    ↓
Lead CRM
    ↓
Website Audit
    ↓
Mockups
    ↓
Outreach
    ↓
Follow-ups
    ↓
Pipeline Refinement
    ↓
Analytics
    ↓
Security Hardening
    ↓
Testing
    ↓
Deployment
```

---

# Things NOT to Overbuild

Avoid initially:

* multi-tenant architecture
* complex RBAC
* billing
* subscriptions
* autonomous agents
* automatic social messaging
* advanced marketing automation
* enterprise reporting
* distributed infrastructure

The first objective is a working personal client-acquisition machine.
