# Signal Playbook

Deterministic mapping of detected website, business, and sales intent triggers to sales angles and mockup strategies.

## 1. Signal Taxonomy

Every detected signal must strictly include:
- `name`: Identifier string (e.g. `NO_WEBSITE`, `SLOW_WEBSITE`, `WEAK_CTA`)
- `type`: Category (`website` | `business` | `sales`)
- `source`: Tool or evidence source (`Website Audit`, `Market Research`, `Google Places`, etc.)
- `confidence`: Decimal score between 0.0 and 1.0
- `evidence`: Specific factual quote, metric, or DOM finding

---

## 2. Website Signals

### `NO_WEBSITE`
- **Condition**: Lead has no `website_url` or `website_status == 'missing'`.
- **Confidence**: 0.95
- **Opportunity**: Build a clean initial digital presence.
- **Angle**: Opportunity-led framework; emphasize capturing searchers who need proof of legitimacy.
- **Mockup Strategy**: Build a 6-section modern foundation with high-contrast hero, services grid, trust indicators, and contact form.

### `SLOW_WEBSITE`
- **Condition**: Page load time > 4000ms or LCP > 4000ms.
- **Confidence**: 0.90
- **Opportunity**: Mobile performance optimization & image compression.
- **Angle**: Audit-led framework; note that slow mobile loading causes customers to tap back to search results.

### `POOR_MOBILE_UX`
- **Condition**: `horizontal_overflow == True` or `is_mobile_responsive == False` or viewport meta missing.
- **Confidence**: 0.92
- **Opportunity**: Mobile-first responsive refactoring.
- **Angle**: Highlight that 65%+ of local service inquiries happen on smartphones.

### `WEAK_CTA` / `NO_CLEAR_CTA`
- **Condition**: Audit finds 0 primary action buttons or `has_clear_cta == False`.
- **Confidence**: 0.88
- **Opportunity**: High-contrast primary call-to-action button in header and hero.
- **Angle**: Visitors want to book or call immediately; make the next step frictionless.

### `MISSING_BOOKING`
- **Condition**: Industry is appointment-driven (dental, salon, clinic, contractor) but audit/research detects no booking widget or scheduling CTA.
- **Confidence**: 0.85
- **Opportunity**: Dedicated appointment request section and calendar integration.
- **Angle**: Capture customers after-hours when the phone is not manned.

### `MISSING_CONTACT_FORM`
- **Condition**: `form_count == 0` or `input_count == 0`.
- **Confidence**: 0.90
- **Opportunity**: Add a streamlined 3-field quote/inquiry form.

### `WEAK_SERVICE_PRESENTATION`
- **Condition**: Research identifies specific high-ticket services (e.g. cosmetic dentistry, roof replacement, commercial litigation) that are either unlisted or buried on the homepage.
- **Confidence**: 0.82
- **Opportunity**: Featured service cards with clear benefits and direct CTAs.

### `POOR_SEO` / `MISSING_META`
- **Condition**: `seo_score < 60` or missing meta description / missing schema.
- **Confidence**: 0.80
- **Opportunity**: Local SEO architecture and structured schema.

---

## 3. Business Signals

### `HIGH_REVIEW_COUNT`
- **Condition**: Verified 20+ reviews or rating >= 4.5.
- **Confidence**: 0.95
- **Opportunity**: Social proof showcase; feature 5-star ratings prominently in the hero and trust bar.
- **Angle**: Translate existing local goodwill into higher website conversion.

### `EXPANDING` / `NEW_LOCATION`
- **Condition**: Research or news indicates recent opening or new service area.
- **Confidence**: 0.85
- **Opportunity**: Multi-location landing page or expanded service area selector.

### `HIRING`
- **Condition**: Research detects open job postings or team expansion.
- **Confidence**: 0.80
- **Opportunity**: Growing business with active cashflow looking to scale capacity.

### `RUNNING_ADS`
- **Condition**: Paid ad presence or sponsored listings detected.
- **Confidence**: 0.85
- **Opportunity**: High intent to generate leads; high bounce rates on slow sites directly waste ad budget.

---

## 4. Sales Intent Signals

### `HIGH_INTENT`
- Lead matches target industry + high-ticket service + confirmed decision maker or email + clear conversion bottleneck.
- **Action**: Immediate high-priority personalized outreach with custom mockup.

### `MEDIUM_INTENT`
- Lead has viable opportunity but partial contact info or moderate digital maturity.
- **Action**: Research and generate mockup, queue draft for human verification.

### `LOW_INTENT`
- Lead already has a modern, fast site with modern booking and strong UX.
- **Action**: Deprioritize; avoid spamming satisfied prospects.
