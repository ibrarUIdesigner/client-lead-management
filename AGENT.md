# Client Acquisition Tool — AI/Developer Agent Instructions

## 1. Project Overview

The Client Acquisition Tool is a personal lead-generation and client-acquisition workspace for web developers and small agencies.

The system helps the user:

1. Find businesses with no website or a weak/outdated website.
2. Store and organize prospects.
3. Analyze prospect websites.
4. Capture desktop and mobile screenshots.
5. Extract branding information.
6. Identify potential website improvement opportunities.
7. Generate personalized homepage mockups.
8. Generate personalized outreach.
9. Track contacts, replies, and follow-ups.
10. Manage the complete sales pipeline.
11. Review acquisition analytics.

Core workflow:

```text
Prospect
   ↓
Website Analysis
   ↓
Opportunity
   ↓
Personalized Mockup
   ↓
Outreach
   ↓
Follow-up
   ↓
Reply
   ↓
Meeting
   ↓
Proposal
   ↓
Won / Lost
```

---

# 2. Project Mission

Build a practical internal tool that makes client acquisition faster and more organized.

The product should not become a generic CRM.

Its primary purpose is:

> Find businesses that may need better websites, demonstrate the opportunity visually, personalize outreach, and track the resulting sales process.

---

# 3. Primary Technology Stack

## Frontend

* React
* Vite
* TypeScript
* Tailwind CSS
* React Router
* Axios
* TanStack Query
* React Hook Form
* Zod
* Lucide React
* Framer Motion
* Recharts

## Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic
* PostgreSQL

## Browser Automation

* Playwright

## Storage

One of:

* Supabase Storage
* S3-compatible storage

## Optional Infrastructure

* Redis
* Background worker
* n8n

---

# 4. Architecture

High-level architecture:

```text
React + Vite
      ↓
 REST / JSON
      ↓
FastAPI
 ├── Routers
 ├── Services
 ├── Repositories
 ├── Integrations
 └── Background Jobs
      ↓
PostgreSQL + Object Storage
```

Frontend architecture:

```text
Pages
  ↓
Domain Components / Hooks
  ↓
Services
  ↓
API
```

Backend architecture:

```text
Router
  ↓
Validation
  ↓
Service
  ↓
Repository / Data Access
  ↓
Database
```

---

# 5. General Development Rules

## Rule 1 — Preserve Existing Functionality

When modifying an existing feature:

* Do not remove existing functionality.
* Do not modify backend behavior during a UI redesign unless explicitly required.
* Do not change API contracts unnecessarily.
* Do not replace working components without a reason.
* Do not remove fields because they appear unused.

Before modifying code:

```text
Inspect
→ Understand
→ Plan
→ Modify
→ Test
```

---

# 6. Frontend Rules

Use strict TypeScript.

Avoid:

```typescript
any
```

unless there is a documented reason.

Use:

* reusable components
* typed API responses
* reusable hooks
* feature-based organization
* TanStack Query for server state
* React Hook Form for forms
* Zod for client-side validation

Do not put API requests directly inside large presentation components.

Preferred:

```text
Component
    ↓
Hook
    ↓
Service
    ↓
API
```

---

# 7. Backend Rules

Route handlers must remain thin.

Preferred:

```text
Router
  ↓
Service
  ↓
Repository
  ↓
Database
```

Do not place large business logic blocks inside FastAPI route handlers.

Use:

* Pydantic validation
* SQLAlchemy
* transactions
* service classes/functions
* stable error codes
* UTC timestamps
* UUID identifiers

---

# 8. API Rules

API base path:

```text
/api/v1
```

Collection endpoints must support pagination.

Standard response:

```json
{
  "items": [],
  "page": 1,
  "limit": 25,
  "total": 100,
  "has_next": true
}
```

Standard error:

```json
{
  "error": {
    "code": "LEAD_NOT_FOUND",
    "message": "Lead was not found.",
    "details": {}
  }
}
```

---

# 9. Async Operations

The following operations should not block normal HTTP requests:

* website auditing
* Playwright screenshots
* mockup generation
* large CSV imports
* expensive AI provider calls

Preferred architecture:

```text
API
 ↓
Create Job
 ↓
Worker
 ↓
Playwright / Provider
 ↓
Storage
 ↓
Database
 ↓
Frontend Status
```

Job states:

```text
PENDING
RUNNING
COMPLETED
FAILED
```

Every long-running job should have:

* timeout
* failure reason
* retry strategy
* duplicate-job protection
* frontend status

---

# 10. Provider Abstraction

External providers must be replaceable.

Example:

```python
class ImageProvider:
    async def generate_mockup(self, request):
        ...


class TextProvider:
    async def generate_outreach(self, request):
        ...


class StorageProvider:
    async def upload(self, file, path):
        ...
```

Do not tightly couple the business logic to a single AI provider.

---

# 11. Lead Statuses

Use the following statuses:

```text
NEW
QUALIFIED
AUDIT_PENDING
AUDIT_COMPLETE
MOCKUP_PENDING
MOCKUP_READY
CONTACTED
FOLLOW_UP
REPLIED
MEETING
PROPOSAL
WON
LOST
NOT_INTERESTED
```

---

# 12. UI Rules

Follow `Design.md`.

Visual direction:

* premium
* modern
* clean
* professional
* spacious
* editorial
* trustworthy
* fast

Avoid:

* neon-heavy UI
* excessive gradients
* excessive glassmorphism
* giant rounded cards
* excessive shadows
* generic AI dashboard aesthetics

Use Lucide React for icons.

Use Framer Motion only where motion improves understanding.

---

# 13. State Rules

Every asynchronous UI operation should support:

```text
Loading
Success
Empty
Error
Retry
```

Do not leave users looking at blank screens while an operation is running.

---

# 14. Responsive Rules

Support:

```text
320px
375px
390px
414px
768px
1024px
1280px
1440px
1920px
```

Mobile:

* sidebar becomes drawer
* tables become cards
* multi-column forms stack
* filters become collapsible
* touch targets ≥44px
* no horizontal page overflow

---

# 15. Security Rules

Treat all external content as untrusted.

This includes:

* website URLs
* website HTML
* screenshots
* uploaded files
* extracted text
* AI-generated text
* AI-generated images
* provider responses

Website analysis must include SSRF protection.

Block:

* localhost
* loopback
* private IP ranges
* link-local IPs
* cloud metadata services
* internal hostnames

Never expose server secrets to the frontend.

---

# 16. Git Rules

Before committing:

```bash
git status
git diff
```

Use small, focused commits.

Do not mix unrelated changes.

Never commit:

* `.env`
* API keys
* credentials
* tokens
* secrets

Run relevant tests before pushing.

---

# 17. Definition of Done

A feature is complete only when:

* functionality works
* API works
* validation exists
* loading state exists
* empty state exists
* error state exists
* responsive behavior works
* accessibility is considered
* critical tests exist
* security implications are reviewed
* documentation is updated
* unrelated functionality remains intact