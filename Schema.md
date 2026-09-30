# Client Acquisition Tool — Database Schema

## 1. Database

Database:

```text
PostgreSQL
```

Use:

* UUID primary keys
* UTC timestamps
* foreign keys
* indexes
* JSONB for flexible metadata
* constraints for status fields

---

# 2. Relationship Overview

```text
Lead
 ├── Contacts
 ├── Website Audits
 │     └── Brand Profile
 ├── Mockups
 ├── Outreach Messages
 │     └── Follow-ups
 ├── Follow-ups
 └── Activities
```

---

# 3. leads

```text
id UUID PK
business_name VARCHAR NOT NULL
slug VARCHAR
industry VARCHAR
description TEXT

country VARCHAR
city VARCHAR

website_url TEXT
website_status VARCHAR
website_quality_score INTEGER

email VARCHAR
phone VARCHAR

linkedin_url TEXT
instagram_url TEXT
facebook_url TEXT
google_maps_url TEXT

lead_score INTEGER
lead_status VARCHAR NOT NULL

source VARCHAR
tags JSONB
notes TEXT

created_at TIMESTAMP NOT NULL
updated_at TIMESTAMP NOT NULL

last_contacted_at TIMESTAMP NULL
next_followup_at TIMESTAMP NULL
```

Indexes:

```text
lead_status
industry
city
created_at
lead_score
next_followup_at
website_url
```

---

# 4. contacts

```text
id UUID PK

lead_id UUID FK → leads.id

name VARCHAR
job_title VARCHAR

email VARCHAR
phone VARCHAR

linkedin_url TEXT

is_primary BOOLEAN

created_at TIMESTAMP
updated_at TIMESTAMP
```

Index:

```text
lead_id
```

---

# 5. website_audits

```text
id UUID PK

lead_id UUID FK → leads.id

url TEXT
status VARCHAR

desktop_screenshot_url TEXT
mobile_screenshot_url TEXT

performance_score INTEGER
design_score INTEGER
mobile_score INTEGER
ux_score INTEGER
seo_score INTEGER
overall_score INTEGER

has_ssl BOOLEAN
is_mobile_responsive BOOLEAN
has_clear_cta BOOLEAN
has_contact_form BOOLEAN
has_social_proof BOOLEAN
has_modern_navigation BOOLEAN

issues JSONB
recommendations JSONB
raw_analysis JSONB

created_at TIMESTAMP
completed_at TIMESTAMP NULL
```

Indexes:

```text
lead_id
status
created_at
```

---

# 6. brand_profiles

```text
id UUID PK

lead_id UUID FK UNIQUE

logo_url TEXT

primary_color VARCHAR
secondary_color VARCHAR
accent_color VARCHAR

font_primary VARCHAR
font_secondary VARCHAR

brand_description TEXT

extracted_images JSONB
extracted_content JSONB

created_at TIMESTAMP
updated_at TIMESTAMP
```

---

# 7. mockups

```text
id UUID PK

lead_id UUID FK
audit_id UUID FK

title VARCHAR
status VARCHAR

prompt TEXT
provider VARCHAR

image_url TEXT
thumbnail_url TEXT

desktop_image_url TEXT
mobile_image_url TEXT

version INTEGER

notes TEXT

created_at TIMESTAMP
completed_at TIMESTAMP NULL
```

Recommended constraint:

```text
UNIQUE(lead_id, version)
```

Indexes:

```text
lead_id
status
created_at
```

---

# 8. outreach_templates

```text
id UUID PK

name VARCHAR
channel VARCHAR

subject TEXT
body TEXT

template_type VARCHAR
is_active BOOLEAN

created_at TIMESTAMP
updated_at TIMESTAMP
```

---

# 9. outreach_messages

```text
id UUID PK

lead_id UUID FK
contact_id UUID FK NULL

channel VARCHAR

subject TEXT
message TEXT

template_id UUID FK NULL

status VARCHAR

sent_at TIMESTAMP NULL
opened_at TIMESTAMP NULL
replied_at TIMESTAMP NULL

created_at TIMESTAMP
updated_at TIMESTAMP
```

Indexes:

```text
lead_id
status
created_at
```

---

# 10. followups

```text
id UUID PK

lead_id UUID FK
outreach_id UUID FK NULL

scheduled_for TIMESTAMP

type VARCHAR
status VARCHAR

notes TEXT

completed_at TIMESTAMP NULL

created_at TIMESTAMP
updated_at TIMESTAMP
```

Indexes:

```text
lead_id
scheduled_for
status
```

---

# 11. activities

```text
id UUID PK

lead_id UUID FK

type VARCHAR
title VARCHAR
description TEXT

metadata JSONB

created_at TIMESTAMP
```

Index:

```text
lead_id, created_at
```

---

# 12. Lead Status Enum

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

# 13. Audit Status Enum

```text
PENDING
RUNNING
COMPLETED
FAILED
```

---

# 14. Mockup Status Enum

```text
PENDING
GENERATING
READY
FAILED
ARCHIVED
```

---

# 15. Outreach Status Enum

```text
DRAFT
READY
SENT
OPENED
REPLIED
BOUNCED
CANCELLED
```

---

# 16. Follow-up Status Enum

```text
SCHEDULED
DUE
COMPLETED
CANCELLED
```

---

# 17. Future SaaS Tables

Do not implement multi-tenancy in the MVP unless needed.

Future:

```text
users
workspaces
workspace_members
```

When multi-tenancy is introduced, business tables can receive:

```text
workspace_id UUID
```

---

# 18. Data Integrity

Rules:

* Every contact must belong to a valid lead.
* Every audit must belong to a valid lead.
* Every mockup must belong to a valid lead.
* Mockup versions must be unique per lead.
* Timestamps must use UTC.
* Enum values must be validated.
* URLs must be validated.
* Emails must be validated.
* Foreign-key behavior must be explicitly defined.

---

# 19. Deletion

Deleting a lead must define behavior for:

```text
Contacts
Audits
Mockups
Outreach
Follow-ups
Activities
Storage files
```

Do not leave orphaned screenshots or mockups in object storage.

---

# 20. Data Retention

The user should eventually be able to delete:

```text
Lead
Contact
Audit
Screenshots
Mockups
Outreach
Follow-ups
Activities
```

Deletion should clean both database records and associated storage artifacts.
"""

---

## 7. `ImplementationPlan.md`

## 8. `Tracker.md`

## 9. `Security.md`