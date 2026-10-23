import type { Audit } from "../types/audit";
import type { Lead, LeadDetail } from "../types/lead";
import type { LeadResearch } from "../types/research";
import type { FollowupItem, MockupItem, OutreachMessageItem } from "../types/workspace";

export type NextBestAction = {
  action: string;
  reason: string;
  badge: string;
  targetTab: "overview" | "audit" | "intelligence" | "research" | "mockups" | "outreach" | "activity";
  ctaLabel: string;
  tone: "primary" | "warning" | "success" | "neutral";
  priority: "critical" | "high" | "medium" | "low";
};

export type JourneyStepStatus = "completed" | "current" | "upcoming";

export type JourneyStep = {
  id: string;
  label: string;
  status: JourneyStepStatus;
  description: string;
  tabId?: "overview" | "audit" | "intelligence" | "research" | "mockups" | "outreach" | "activity";
};

export function getNextBestAction(
  lead: Lead | LeadDetail,
  options?: {
    audit?: Audit | null;
    research?: LeadResearch | null;
    mockups?: MockupItem[] | null;
    outreach?: OutreachMessageItem[] | null;
    followups?: FollowupItem[] | null;
  },
): NextBestAction {
  const audit = options?.audit;
  const research = options?.research;
  const mockups = options?.mockups ?? [];
  const outreach = options?.outreach ?? [];
  const followups = options?.followups ?? [];

  // Check unread replies or REPLIED status
  if (lead.email_unread || lead.lead_status === "REPLIED") {
    return {
      action: "Respond to Prospect",
      reason: "Prospect sent a reply. Respond quickly while the conversation is active.",
      badge: "Reply Received",
      targetTab: "outreach",
      ctaLabel: "Open Conversation →",
      tone: "warning",
      priority: "critical",
    };
  }

  // Check Won / Lost / Do Not Contact
  if (lead.lead_status === "WON") {
    return {
      action: "Active Client",
      reason: "Deal closed successfully. Deliver services and foster retention.",
      badge: "Won",
      targetTab: "overview",
      ctaLabel: "View Client →",
      tone: "success",
      priority: "low",
    };
  }

  if (lead.lead_status === "LOST" || lead.do_not_contact) {
    return {
      action: "Archive or Revisit Later",
      reason: lead.do_not_contact
        ? "Lead is flagged as Do Not Contact."
        : "Lead marked lost. No immediate outreach needed.",
      badge: "Closed",
      targetTab: "overview",
      ctaLabel: "View Details →",
      tone: "neutral",
      priority: "low",
    };
  }

  // Follow-ups due
  const hasDueFollowup =
    (lead.next_followup_at && new Date(lead.next_followup_at).getTime() <= Date.now()) ||
    followups.some(
      (f) =>
        f.status === "DUE" ||
        (f.status === "SCHEDULED" && new Date(f.scheduled_for).getTime() <= Date.now()),
    );

  if (hasDueFollowup) {
    return {
      action: "Send Follow-up",
      reason: "Follow-up is due today. Re-engaging now significantly boosts response rates.",
      badge: "Follow-up Due",
      targetTab: "outreach",
      ctaLabel: "Send Follow-up →",
      tone: "warning",
      priority: "high",
    };
  }

  // Check draft outreach messages
  const existingDraft = outreach.find(
    (m) => m.status === "DRAFT" || m.status === "READY",
  );
  if (existingDraft) {
    return {
      action: "Review & Send Outreach",
      reason: "A tailored draft is ready for manual review and delivery.",
      badge: "Draft Ready",
      targetTab: "outreach",
      ctaLabel: "Review Outreach →",
      tone: "primary",
      priority: "high",
    };
  }

  // Check if already contacted
  const sentMessages = outreach.filter(
    (m) => m.status === "SENT" || m.status === "OPENED",
  );
  if (lead.last_contacted_at || sentMessages.length > 0 || lead.lead_status === "CONTACTED") {
    return {
      action: "Schedule Follow-up",
      reason: "Initial outreach sent. Set a scheduled check-in to ensure no prospect goes cold.",
      badge: "Contacted",
      targetTab: "outreach",
      ctaLabel: "Schedule Follow-up →",
      tone: "neutral",
      priority: "medium",
    };
  }

  // Check if mockups are ready
  const readyMockup = mockups.find((m) => m.status === "READY");
  if (readyMockup) {
    return {
      action: "Prepare Personalized Outreach",
      reason: `Homepage mockup "${readyMockup.title || readyMockup.design_guide_name || "Concept"}" is ready to showcase in your pitch.`,
      badge: "Mockup Ready",
      targetTab: "outreach",
      ctaLabel: "Write Outreach →",
      tone: "primary",
      priority: "high",
    };
  }

  // Check research status
  const researchDone = research?.status === "COMPLETED";
  const auditDone = audit?.status === "COMPLETED";

  // If research is done and audit is done, generate mockup (or outreach if no website)
  if (researchDone && auditDone) {
    const hasWebsite = Boolean(lead.website_url);
    const lowDesignScore = (audit?.design_score ?? 100) < 55;
    if (!hasWebsite || lowDesignScore) {
      return {
        action: "Generate Website Mockup",
        reason: "Audit and business intelligence gathered. Produce a modern homepage concept.",
        badge: "Ready for Mockup",
        targetTab: "mockups",
        ctaLabel: "Generate Mockup →",
        tone: "primary",
        priority: "high",
      };
    }
    return {
      action: "Prepare Personalized Outreach",
      reason: "Audit and research findings are ready. Draft a hyper-personalized acquisition pitch.",
      badge: "Ready for Outreach",
      targetTab: "outreach",
      ctaLabel: "Write Outreach →",
      tone: "primary",
      priority: "high",
    };
  }

  // If audit is done, but research is not yet completed
  if (auditDone && !researchDone) {
    return {
      action: "Research Lead Intelligence",
      reason: "Audit completed. Run Tavily & Exa research to extract competitor gaps and commercial pain points.",
      badge: "Audit Done",
      targetTab: "research",
      ctaLabel: "Research Lead →",
      tone: "primary",
      priority: "high",
    };
  }

  // If lead has website and no audit yet
  if (lead.website_url && !auditDone) {
    return {
      action: "Run Website Audit",
      reason: "Analyze performance, mobile responsiveness, and SEO to identify concrete sales angles.",
      badge: "Needs Audit",
      targetTab: "audit",
      ctaLabel: "Run Audit →",
      tone: "primary",
      priority: "high",
    };
  }

  // If lead has no website
  if (!lead.website_url) {
    if (!researchDone) {
      return {
        action: "Research Business",
        reason: "Prospect has no website listed. Research their digital presence and local standing.",
        badge: "No Website",
        targetTab: "research",
        ctaLabel: "Research Lead →",
        tone: "warning",
        priority: "high",
      };
    }
    return {
      action: "Generate Mockup & Pitch New Site",
      reason: "Pitch a brand new online presence tailored for their local market.",
      badge: "New Site Pitch",
      targetTab: "mockups",
      ctaLabel: "Generate Mockup →",
      tone: "primary",
      priority: "high",
    };
  }

  return {
    action: "Qualify & Audit Lead",
    reason: "Review business details and initiate discovery audit.",
    badge: "New Lead",
    targetTab: "overview",
    ctaLabel: "Qualify Lead →",
    tone: "neutral",
    priority: "medium",
  };
}

export function getLeadJourneySteps(
  lead: Lead | LeadDetail,
  options?: {
    audit?: Audit | null;
    research?: LeadResearch | null;
    mockups?: MockupItem[] | null;
    outreach?: OutreachMessageItem[] | null;
  },
): JourneyStep[] {
  const audit = options?.audit;
  const research = options?.research;
  const mockups = options?.mockups ?? [];
  const outreach = options?.outreach ?? [];

  const auditCompleted = audit?.status === "COMPLETED";
  const researchCompleted = research?.status === "COMPLETED";
  const mockupReady = mockups.some((m) => m.status === "READY");
  const outreachSent =
    Boolean(lead.last_contacted_at) ||
    outreach.some((m) => m.status === "SENT" || m.status === "OPENED" || m.status === "REPLIED") ||
    lead.lead_status === "CONTACTED" ||
    lead.lead_status === "FOLLOW_UP" ||
    lead.lead_status === "REPLIED" ||
    lead.lead_status === "MEETING" ||
    lead.lead_status === "PROPOSAL" ||
    lead.lead_status === "WON";

  const followUpActive =
    Boolean(lead.next_followup_at) ||
    lead.lead_status === "FOLLOW_UP" ||
    lead.lead_status === "REPLIED" ||
    lead.lead_status === "MEETING" ||
    lead.lead_status === "PROPOSAL" ||
    lead.lead_status === "WON";

  const isWon = lead.lead_status === "WON";

  return [
    {
      id: "discovered",
      label: "Overview",
      status: "completed",
      description: `Source: ${lead.source || "Database"}`,
      tabId: "overview",
    },
    {
      id: "audited",
      label: "Audit",
      status: auditCompleted
        ? "completed"
        : !lead.website_url
        ? "completed"
        : lead.lead_status === "NEW" && !lead.lead_score
        ? "current"
        : "current",
      description: auditCompleted
        ? `Health: ${audit?.performance_score ?? "Audited"}`
        : !lead.website_url
        ? "No website"
        : "Website check",
      tabId: "audit",
    },
    {
      id: "intelligence",
      label: "Intelligence",
      status:
        lead.lead_score !== null && lead.lead_score !== undefined
          ? "completed"
          : auditCompleted
          ? "current"
          : "upcoming",
      description:
        lead.lead_score !== null && lead.lead_score !== undefined
          ? `Score: ${lead.lead_score}/100`
          : auditCompleted
          ? "Signals ready"
          : "Signals & Score",
      tabId: "intelligence",
    },
    {
      id: "researched",
      label: "Research",
      status: researchCompleted
        ? "completed"
        : auditCompleted
        ? "current"
        : "upcoming",
      description: researchCompleted ? "Market intel" : "Tavily & Exa",
      tabId: "research",
    },
    {
      id: "mockup",
      label: "Mockups",
      status: mockupReady
        ? "completed"
        : researchCompleted || auditCompleted
        ? "current"
        : "upcoming",
      description: mockupReady
        ? `${mockups.filter((m) => m.status === "READY").length} Ready`
        : "Homepage concept",
      tabId: "mockups",
    },
    {
      id: "outreach",
      label: "Outreach",
      status: outreachSent
        ? "completed"
        : mockupReady || researchCompleted
        ? "current"
        : "upcoming",
      description: outreachSent ? "Pitch delivered" : "Personalized pitch",
      tabId: "outreach",
    },
    {
      id: "activity",
      label: "Activity",
      status: isWon
        ? "completed"
        : followUpActive
        ? "current"
        : outreachSent
        ? "current"
        : "upcoming",
      description: lead.last_replied_at
        ? "Replied"
        : lead.next_followup_at
        ? "Follow-up due"
        : "History & Timeline",
      tabId: "activity",
    },
  ];
}

export function getOpportunitySummary(
  lead: Lead | LeadDetail,
  audit?: Audit | null,
  research?: LeadResearch | null,
): { title: string; bullets: string[]; highlightScore: number | null } {
  const score = lead.lead_score ?? audit?.raw_analysis?.opportunity_score ?? null;
  const bullets: string[] = [];

  if (!lead.website_url) {
    bullets.push("Business operates with no discovered official website, presenting a direct opening for a modern digital presence.");
  } else if (audit?.raw_analysis) {
    const analysis = audit.raw_analysis;
    if (analysis.opportunity_breakdown && analysis.opportunity_breakdown.length > 0) {
      for (const item of analysis.opportunity_breakdown.slice(0, 3)) {
        bullets.push(`${item.label} (Impact: ${item.points} pts)`);
      }
    } else if (audit.performance_score && audit.performance_score < 60) {
      bullets.push(`Performance score is low (${audit.performance_score}/100), slowing mobile loading and bounce rates.`);
    }
  }

  if (research?.research_data) {
    const data = research.research_data;
    if (Array.isArray(data.high_impact_opportunities) && data.high_impact_opportunities.length > 0) {
      for (const opp of data.high_impact_opportunities.slice(0, 2)) {
        if (typeof opp === "string") bullets.push(opp);
      }
    }
    if (Array.isArray(data.pain_points_and_gaps) && data.pain_points_and_gaps.length > 0) {
      const gap = data.pain_points_and_gaps[0];
      if (typeof gap === "string" && !bullets.includes(gap)) {
        bullets.push(`Identified operational gap: ${gap}`);
      }
    }
  }

  if (bullets.length === 0) {
    if (lead.industry) {
      bullets.push(`Operating in the ${lead.industry} space with commercial acquisition potential.`);
    }
    bullets.push("Qualified prospect with verified business data ready for structured audit and outreach.");
  }

  const title =
    score && score >= 75
      ? "High-Priority Redesign Prospect"
      : score && score >= 50
      ? "Promising Opportunity with Actionable Gaps"
      : "Standard Prospect Profile";

  return { title, bullets, highlightScore: score };
}
