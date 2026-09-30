# Client Acquisition Tool — Application Flow

## 1. Main Navigation

```text
Dashboard
Leads
Pipeline
Mockups
Outreach
Follow-ups
Analytics
Settings
```

---

# 2. Dashboard Flow

```text
Open Dashboard
      ↓
View Summary
      ↓
Review Pipeline
      ↓
Review Due Follow-ups
      ↓
Review Recent Activity
      ↓
Quick Add Lead
```

The dashboard should answer:

> What should I work on next?

---

# 3. Add Lead Flow

```text
Leads
  ↓
Add Lead
  ↓
Business Details
  ├── Business Name
  ├── Industry
  ├── City
  ├── Country
  ├── Website
  ├── Email
  ├── Phone
  ├── Source
  ├── Tags
  └── Notes
  ↓
Save
  ↓
Lead Details
```

Alternative:

```text
Save & Analyze
      ↓
Audit Job
      ↓
Audit Results
```

---

# 4. Lead List Flow

User can:

```text
Search
Filter
Sort
Select
Bulk Update
Open Lead
```

Filters:

* status
* industry
* city
* country
* source
* tags
* score
* website status

Desktop:

```text
Table
```

Mobile:

```text
Lead Cards
```

---

# 5. Lead Details Flow

Tabs:

```text
Overview
Audit
Mockups
Outreach
Activity
```

Primary actions:

```text
Analyze Website
Create Mockup
Generate Outreach
Schedule Follow-up
```

---

# 6. Website Audit Flow

```text
Lead Details
      ↓
Analyze Website
      ↓
Validate URL
      ↓
Create Audit Job
      ↓
Running
      ↓
Desktop Screenshot
      ↓
Mobile Screenshot
      ↓
Website Checks
      ↓
Brand Extraction
      ↓
Opportunity Findings
      ↓
Persist Results
      ↓
Audit Complete
```

State:

```text
Idle
 ↓
Loading
 ├── Success
 └── Error
       ↓
     Retry
```

---

# 7. Audit Results Flow

Display:

```text
Website URL
Audit Date
Desktop Screenshot
Mobile Screenshot
Overall Findings
Performance
Mobile
Design
UX
SEO
HTTPS
CTA
Contact Form
Navigation
Issues
Recommendations
Brand Profile
```

The user should be able to move directly from audit results to:

```text
Create Mockup
```

---

# 8. Mockup Flow

```text
Audit Complete
      ↓
Create Mockup
      ↓
Review Brand Profile
      ↓
Choose Style
      ↓
Choose Sections
      ↓
Generate
      ↓
Generating
      ↓
Preview
      ↓
Save Version
```

Example:

```text
V1
V2
V3
```

Regeneration creates a new version.

---

# 9. Outreach Flow

```text
Lead
  ↓
Generate Outreach
  ↓
Select Template
  ↓
Build Context
  ├── Business
  ├── Industry
  ├── Website
  ├── Audit Findings
  └── Mockup
  ↓
Generate Draft
  ↓
Edit
  ↓
Copy / Manual Send
  ↓
Mark Contacted
  ↓
Schedule Follow-up
```

The user must be able to edit generated outreach before sending.

---

# 10. Follow-up Flow

```text
Contacted
    ↓
Schedule
    ↓
Upcoming
    ↓
Due
    ├── Complete
    ├── Reschedule
    └── Cancel
```

Reply:

```text
Contacted
   ↓
Replied
   ↓
Meeting
   ↓
Proposal
   ↓
Won / Lost
```

---

# 11. Pipeline Flow

Columns:

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

Drag/drop process:

```text
Drag Card
    ↓
Optimistic Update
    ↓
PATCH API
    ↓
Success
```

Failure:

```text
PATCH Failed
    ↓
Rollback UI
    ↓
Show Error
```

---

# 12. CSV Import Flow

```text
Upload CSV
    ↓
Validate File
    ↓
Validate Columns
    ↓
Preview
    ↓
Show Valid / Invalid Rows
    ↓
Confirm Import
    ↓
Create Leads
    ↓
Import Summary
```

Invalid rows must not disappear silently.

---

# 13. Follow-up Page

Sections:

```text
Today
Overdue
Upcoming
Completed
```

Each follow-up should support:

* complete
* reschedule
* cancel
* open lead

---

# 14. Analytics Flow

```text
Analytics
   ↓
Overview
   ├── Leads
   ├── Audits
   ├── Mockups
   ├── Contacted
   ├── Replies
   ├── Meetings
   └── Wins
```

Filters:

* date range
* industry
* city
* source
* status

---

# 15. Mobile Flow

Mobile navigation:

```text
Topbar
  ↓
Menu Button
  ↓
Sidebar Drawer
```

Tables become:

```text
Cards
```

Forms become:

```text
Single Column
```

Mockup studio becomes:

```text
Preview
↓
Controls
```

Filters become:

```text
Filter Button
↓
Filter Drawer
```

Touch targets:

```text
Minimum 44px
```

No horizontal page overflow.

---

# 16. State Management

Server state:

```text
TanStack Query
```

Local UI state:

```text
React useState / useReducer
```

Forms:

```text
React Hook Form
```

Validation:

```text
Zod
```

Avoid unnecessary global state.
