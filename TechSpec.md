# Client Acquisition Tool — Technical Specification

## 1. System Architecture

```text
React + Vite + TypeScript
          ↓
       REST API
          ↓
       FastAPI
          ↓
 ┌──────────────────────┐
 │ Services             │
 │ Repositories         │
 │ Integrations         │
 │ Background Jobs      │
 └──────────────────────┘
          ↓
 ┌──────────────────────┐
 │ PostgreSQL           │
 │ Object Storage       │
 └──────────────────────┘
```

---

# 2. Frontend Stack

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

---

# 3. Frontend Structure

```text
frontend/
├── src/
│   ├── app/
│   │   ├── router/
│   │   ├── providers/
│   │   └── App.tsx
│   │
│   ├── components/
│   │   ├── ui/
│   │   ├── layout/
│   │   ├── data/
│   │   └── feedback/
│   │
│   ├── features/
│   │   ├── leads/
│   │   ├── audits/
│   │   ├── mockups/
│   │   ├── outreach/
│   │   ├── followups/
│   │   ├── pipeline/
│   │   └── analytics/
│   │
│   ├── pages/
│   ├── services/
│   ├── hooks/
│   ├── types/
│   ├── lib/
│   └── styles/
│
└── tests/
```

---

# 4. Backend Stack

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic
* PostgreSQL
* Playwright

Optional:

* Redis
* Celery/RQ/custom worker
* n8n

---

# 5. Backend Structure

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── leads.py
│   │       ├── contacts.py
│   │       ├── audits.py
│   │       ├── mockups.py
│   │       ├── outreach.py
│   │       ├── followups.py
│   │       ├── dashboard.py
│   │       └── analytics.py
│   │
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   ├── integrations/
│   ├── jobs/
│   └── db/
│
├── alembic/
└── tests/
```

---

# 6. API Base URL

```text
/api/v1
```

---

# 7. Standard Collection Response

```json
{
  "items": [],
  "page": 1,
  "limit": 25,
  "total": 100,
  "has_next": true
}
```

---

# 8. Standard Error Response

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

# 9. Lead Endpoints

```text
POST   /leads
GET    /leads
GET    /leads/{id}
PATCH  /leads/{id}
DELETE /leads/{id}

POST   /leads/import
PATCH  /leads/bulk
PATCH  /leads/{id}/status
```

---

# 10. Contact Endpoints

```text
GET    /leads/{id}/contacts
POST   /leads/{id}/contacts

PATCH  /contacts/{id}
DELETE /contacts/{id}
```

---

# 11. Audit Endpoints

```text
POST /leads/{id}/audit
GET  /leads/{id}/audit
GET  /leads/{id}/audits
POST /audits/{id}/rerun
```

---

# 12. Mockup Endpoints

```text
POST   /leads/{id}/mockups
GET    /leads/{id}/mockups
GET    /mockups/{id}

POST   /mockups/{id}/regenerate
PATCH  /mockups/{id}
DELETE /mockups/{id}
```

---

# 13. Outreach Endpoints

```text
POST  /leads/{id}/outreach/generate
GET   /leads/{id}/outreach
POST  /outreach
PATCH /outreach/{id}

POST  /outreach/{id}/mark-contacted
POST  /outreach/{id}/mark-replied
```

---

# 14. Follow-up Endpoints

```text
GET    /followups
POST   /followups
PATCH  /followups/{id}
POST   /followups/{id}/complete
DELETE /followups/{id}
```

---

# 15. Dashboard Endpoints

```text
GET /dashboard/summary
GET /dashboard/pipeline
GET /dashboard/recent-activity
GET /dashboard/followups
```

---

# 16. Analytics Endpoints

```text
GET /analytics/overview
GET /analytics/pipeline
GET /analytics/outreach
GET /analytics/conversion
```

---

# 17. Service Architecture

## LeadService

Responsibilities:

* lead CRUD
* searching
* filtering
* status changes
* bulk updates
* tags

## AuditService

Responsibilities:

* URL validation
* audit creation
* Playwright execution
* screenshot capture
* website analysis
* brand extraction
* persistence

## MockupService

Responsibilities:

* brand context
* prompt construction
* image provider
* versioning
* storage

## OutreachService

Responsibilities:

* template selection
* context creation
* AI generation
* message persistence
* lifecycle management

## FollowupService

Responsibilities:

* scheduling
* due state
* completion
* rescheduling
* cancellation

---

# 18. Provider Interfaces

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

---

# 19. Async Job Architecture

```text
Frontend
   ↓
POST /audit
   ↓
API
   ↓
Create Job
   ↓
Worker
   ↓
Playwright
   ↓
Website Analysis
   ↓
Object Storage
   ↓
PostgreSQL
   ↓
Frontend refresh/polling
```

---

# 20. Website Audit Process

```text
Validate URL
    ↓
SSRF Check
    ↓
Resolve DNS Safely
    ↓
Launch Isolated Browser
    ↓
Desktop Screenshot
    ↓
Mobile Screenshot
    ↓
Inspect Content
    ↓
Extract Brand
    ↓
Perform Checks
    ↓
Generate Findings
    ↓
Persist Results
```

---

# 21. Audit Checks

Potential checks:

* HTTPS
* responsive layout
* mobile usability
* page title
* meta description
* CTA presence
* contact form
* phone visibility
* navigation quality
* social proof
* content clarity
* performance indicators
* image quality
* outdated design indicators

---

# 22. Opportunity Score

The score is a transparent internal prioritization signal.

Example:

```text
Missing website       +30
Poor mobile UX        +20
Outdated design       +15
Weak CTA              +10
No contact form       +10
Poor performance       +5
No HTTPS              +10
```

Store individual findings so the score can be explained.

---

# 23. Storage Structure

```text
leads/{lead_id}/audits/
leads/{lead_id}/mockups/
leads/{lead_id}/brand/
leads/{lead_id}/attachments/
```

Storage must remain private.

Use:

* signed URLs
* authenticated endpoints
* expiring access

---

# 24. Environment Variables

```text
DATABASE_URL=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=

TEXT_PROVIDER_API_KEY=
IMAGE_PROVIDER_API_KEY=

REDIS_URL=

APP_ENV=
CORS_ORIGINS=
```

Server-only secrets must never be exposed through the React application.

---

# 25. API Rules

* UUID identifiers
* UTC timestamps
* Pydantic validation
* pagination
* stable errors
* correct HTTP status codes
* duplicate-job protection
* timeouts
* predictable response structures

---

# 26. Testing

Backend:

* unit tests
* service tests
* API tests
* URL validation tests
* scoring tests
* provider failure tests

Frontend:

* component tests
* form tests
* hook tests
* API state tests

E2E:

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
```

---

# 27. Performance

Use:

* pagination
* database indexes
* caching where useful
* lazy-loaded routes
* optimized thumbnails
* background jobs
* compressed screenshots where appropriate

Do not load hundreds of leads/mockups into the browser simultaneously.

---

# 28. Observability

Log:

* request ID
* job ID
* audit lifecycle
* mockup lifecycle
* provider errors
* security events

Never log:

* passwords
* API keys
* access tokens
* cookies
* secrets
* unnecessary sensitive contact/message data
  """

---

## 4. `AppFlow.md`

## 5. `Design.md`

## 6. `Schema.md`