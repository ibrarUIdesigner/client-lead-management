# Follow-up Strategy Playbook

Context-aware multi-step follow-up sequences, timing rules, and stop-on-reply automation logic.

## 1. Follow-up Cadence & Sequence

Cold outreach rarely converts on the first email. The Harvey-inspired follow-up sequence relies on progressive value delivery rather than nagging:

```text
Day 0: Initial Outreach (Mockup-led, Audit-led, or Opportunity-led)
  ↓ (No reply for 4 days)
Day 4: Quick Value-Add Follow-up (References the mockup link or a single high-impact observation)
  ↓ (No reply for 6 days)
Day 10: Perspective / Social Proof Angle (Customer psychology or local competitor trend)
  ↓ (No reply for 10 days)
Day 20: Graceful Breakup / Clean Closeout (Respectful exit leaving the door open)
```

---

## 2. Sequence Templates

### Follow-up 1 (Day 4: Value Bump)
- **Goal**: Re-surface the conversation without guilt tripping ("Just following up").
- **Word count**: Under 50 words.

```text
Hi {{first_name|there}},

Following up briefly on my earlier note about {{business_name}}'s homepage.

In case you missed it, I had put together a quick preview concept showing a cleaner mobile layout with a direct booking section:
{{mockup_url}}

Would you be open to taking a quick look this week?

Best,
{{sender_name}}
```

---

### Follow-up 2 (Day 10: Competitor / Customer Friction Angle)
- **Goal**: Introduce a fresh perspective on customer behavior.
- **Word count**: Under 65 words.

```text
Hi {{first_name|there}},

One trend we're seeing across {{industry_label}} in {{city}} is that over 60% of bookings happen outside typical working hours via mobile.

Without an easy way to request a quote or book online, those prospective clients usually bounce over to the next provider.

Happy to walk you through how the concept we designed solves that. Are you free for 5 minutes Thursday?

Best,
{{sender_name}}
```

---

### Follow-up 3 (Day 20: Graceful Breakup)
- **Goal**: Remove sales pressure and invite a response if timing was just off.
- **Word count**: Under 45 words.

```text
Hi {{first_name|there}},

I know you're busy running {{business_name}}, so I won't clutter your inbox further.

If you ever decide to refresh your website or improve mobile inquiries down the road, feel free to reach out anytime.

Wishing you and the team continued success!

Best,
{{sender_name}}
```

---

## 3. Strict Rules & Guardrails
- **Immediate Stop-On-Reply**: Any incoming reply, bounce, or opt-out automatically marks pending follow-ups as cancelled.
- **Daily Sending Caps**: Strictly observe mailbox daily sending limits.
- **Do Not Follow Up on Unsubscribes**: Never queue or send follow-ups to contacts who expressed disinterest or opt-out.
