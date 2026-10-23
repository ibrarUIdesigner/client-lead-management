import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Compass, Sparkles } from "lucide-react";

import { useToast } from "../../components/feedback/useToast";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import { useLatestAudit } from "../../hooks/useAudit";
import { useHealth } from "../../hooks/useHealth";
import { useLeadIntelligence } from "../../hooks/useIntelligence";
import { useGenerateOutreach, useSuggestOutreachOffer } from "../../hooks/useOutreach";
import { useLeadResearch } from "../../hooks/useResearch";
import { useMockups, useOutreachTemplates } from "../../hooks/useWorkspace";
import { apiErrorCode, apiErrorMessage } from "../../lib/apiError";
import { cn, focusRing } from "../../lib/cn";
import type { OutreachTone } from "../../services/outreach";
import { findingLines } from "./findings";

type OutreachComposerProps = {
  leadId: string;
  email: string | null;
  hasWebsite: boolean;
  onCreated: (messageId: string) => void;
};

const DEFAULT_OFFER =
  "I design clearer websites for local businesses, starting with a homepage that makes the next step obvious.";
const OFFER_KEY = "outreach-offer";
const TONE_KEY = "outreach-tone";
const SENDER_KEY = "outreach-sender-name";
const SENDER_EMAIL_KEY = "outreach-sender-email";
const SENDER_WHATSAPP_KEY = "outreach-sender-whatsapp";
const SENDER_PORTFOLIO_KEY = "outreach-sender-portfolio";

const toneOptions: { value: OutreachTone; label: string }[] = [
  { value: "professional", label: "Professional" },
  { value: "warm", label: "Warm" },
  { value: "direct", label: "Direct" },
  { value: "brief", label: "Brief" },
];

const frameworkOptions = [
  { value: "auto", label: "Auto (Recommended by Strategist)" },
  { value: "mockup_led", label: "Mockup-Led (Highlight custom homepage concept)" },
  { value: "audit_led", label: "Audit-Led (Focus on mobile speed & UX friction)" },
  { value: "research_led", label: "Research-Led (Competitor gap & market position)" },
  { value: "opportunity_led", label: "Opportunity-Led (Frame lost inquiries / new site)" },
  { value: "problem_solution", label: "Problem + Solution (Direct observation & fix)" },
];

export function OutreachComposer({
  leadId,
  email,
  hasWebsite,
  onCreated,
}: OutreachComposerProps) {
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const templates = useOutreachTemplates();
  const audit = useLatestAudit(leadId);
  const health = useHealth();
  const generate = useGenerateOutreach(leadId);
  const researchQuery = useLeadResearch(leadId);
  const research = researchQuery.data;
  const intel = useLeadIntelligence(leadId);
  const mockupsQuery = useMockups(leadId);
  const mockups = mockupsQuery.data ?? [];
  const [framework, setFramework] = useState("auto");
  const [mockupId, setMockupId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [offer, setOffer] = useState(() => readStored(OFFER_KEY, DEFAULT_OFFER));
  const [tone, setTone] = useState<OutreachTone>(() => readTone());
  const [senderName, setSenderName] = useState(() => readStored(SENDER_KEY, "Ibrar"));
  const [senderEmail, setSenderEmail] = useState(() => readStored(SENDER_EMAIL_KEY, "ibraruidesigner@gmail.com"));
  const [senderWhatsapp, setSenderWhatsapp] = useState(() => readStored(SENDER_WHATSAPP_KEY, "+923028131491"));
  const [senderPortfolio, setSenderPortfolio] = useState(() => readStored(SENDER_PORTFOLIO_KEY, "https://ibrardevportfolio.netlify.app/"));
  const [pending, setPending] = useState<"ai" | "template" | null>(null);
  const [offerTouched, setOfferTouched] = useState(false);
  const appliedSuggestion = useRef<string | null>(null);
  const activeTemplates = (templates.data ?? []).filter((item) => item.is_active);
  const missingAudit = audit.isError && apiErrorCode(audit.error) === "AUDIT_NOT_FOUND";
  const running = audit.data?.status === "PENDING" || audit.data?.status === "RUNNING";
  const auditReady =
    !hasWebsite ||
    (audit.data?.status === "COMPLETED" && !running) ||
    (audit.data?.status === "FAILED" && !running) ||
    missingAudit;
  const suggestion = useSuggestOutreachOffer(leadId, auditReady && !offerTouched);
  const lines = findingLines(audit.data);
  const provider = health.data?.email_drafts;
  const aiBlocked = provider === "unconfigured";

  useEffect(() => {
    const next = suggestion.data?.offer?.trim();
    if (!next || offerTouched) {
      return;
    }
    if (appliedSuggestion.current === next) {
      return;
    }
    appliedSuggestion.current = next;
    setOffer(next);
    writeStored(OFFER_KEY, next);
  }, [offerTouched, suggestion.data?.offer]);

  const createDraft = (useAi: boolean) => {
    setPending(useAi ? "ai" : "template");
    generate.mutate(
      useAi
        ? {
            offer: offer.trim() || undefined,
            tone,
            framework: framework !== "auto" ? framework : undefined,
            mockup_id: mockupId || undefined,
            sender_name: senderName.trim() || undefined,
            sender_email: senderEmail.trim() || undefined,
            sender_whatsapp: senderWhatsapp.trim() || undefined,
            sender_portfolio: senderPortfolio.trim() || undefined,
            use_ai: true,
          }
        : {
            template_id: templateId || undefined,
            use_ai: false,
          },
      {
        onSuccess: (message) => {
          notify(
            useAi
              ? "Draft generated. Review it, then send it from your email app."
              : "Draft written from the template. Send it from your email app.",
            "success",
          );
          onCreated(message.id);
        },
        onError: (error) => {
          notify(apiErrorMessage(error, "Could not create the draft."), "danger");
        },
        onSettled: () => {
          setPending(null);
        },
      },
    );
  };

  const refreshOffer = () => {
    setOfferTouched(false);
    appliedSuggestion.current = null;
    void queryClient.invalidateQueries({ queryKey: ["outreach-offer", leadId] });
  };

  return (
    <Card>
      <p className="text-caption font-semibold text-gray-500">1. What the email will say</p>
      <h2 className="mt-1 text-h4 font-semibold text-ink">Findings from the latest audit</h2>
      <Findings
        loading={audit.isPending}
        missing={missingAudit}
        running={running}
        failed={audit.data?.status === "FAILED"}
        hasWebsite={hasWebsite}
        lines={lines}
      />

      {research && research.status === "COMPLETED" && research.research_data?.proactive_solutions?.length ? (
        <div className="mt-4 rounded-lg border border-primary-200 bg-primary-50/50 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="size-4 text-primary-600" />
              <h4 className="text-small font-semibold text-primary-950">
                Researched Proactive Solutions
              </h4>
            </div>
            <div className="flex items-center gap-1.5">
              <Badge tone="indigo">Tavily</Badge>
              <Badge tone="blue">Exa</Badge>
            </div>
          </div>
          <p className="mt-1 text-caption text-primary-800">
            These tailored proactive solutions were extracted from lead intelligence and will be included in the AI draft:
          </p>
          <div className="mt-2.5 space-y-2">
            {research.research_data.proactive_solutions.slice(0, 3).map((solution, i) => (
              <div
                key={i}
                className="flex items-start justify-between gap-2 rounded border border-primary-100 bg-white/90 p-2.5 text-small text-gray-800 shadow-2xs"
              >
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="size-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>{solution}</span>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  className="h-7 px-2 shrink-0 text-caption text-primary-700 hover:text-primary-900"
                  onClick={() => {
                    setOffer(solution);
                    setOfferTouched(true);
                    writeStored(OFFER_KEY, solution);
                    notify("Applied proactive solution as email offer.", "success");
                  }}
                >
                  Use as offer
                </Button>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {intel.data?.strategy ? (
        <div className="mt-4 rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50/70 via-white to-purple-50/40 p-4 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Compass className="size-4 text-indigo-600" />
              <h4 className="text-small font-semibold text-indigo-950">
                Harvey Outreach Strategy
              </h4>
              <Badge tone="indigo">{intel.data.strategy.recommended_framework.toUpperCase()}</Badge>
            </div>
            {intel.data.opportunity_score ? (
              <span className="text-caption font-semibold text-indigo-700 bg-indigo-100/80 px-2 py-0.5 rounded-full">
                Score: {intel.data.opportunity_score.total_score}/100 ({intel.data.opportunity_score.tier})
              </span>
            ) : null}
          </div>
          <p className="mt-2 text-small text-gray-700 leading-relaxed">
            <strong className="text-gray-900">Sales Angle: </strong>
            {intel.data.strategy.outreach_angle}
          </p>
          {intel.data.strategy.primary_opportunity ? (
            <div className="mt-2 text-caption text-indigo-950 bg-indigo-50/60 p-2 rounded-md border border-indigo-100">
              <strong>Focus Opportunity: </strong>
              {intel.data.strategy.primary_opportunity}
            </div>
          ) : null}
          {intel.data.strategy.suggested_offer ? (
            <div className="mt-3 flex items-center justify-between gap-2 border-t border-indigo-100 pt-2.5">
              <p className="text-caption text-indigo-900 truncate">
                <span className="font-semibold">Suggested Offer: </span>
                {intel.data.strategy.suggested_offer}
              </p>
              <Button
                type="button"
                variant="ghost"
                className="h-7 px-2 shrink-0 text-caption font-semibold text-indigo-700 hover:text-indigo-900"
                onClick={() => {
                  if (intel.data?.strategy) {
                    setOffer(intel.data.strategy.suggested_offer);
                    setOfferTouched(true);
                    writeStored(OFFER_KEY, intel.data.strategy.suggested_offer);
                    if (intel.data.strategy.recommended_framework) {
                      setFramework(intel.data.strategy.recommended_framework);
                    }
                    notify("Applied Harvey sales strategy and recommended framework.", "success");
                  }
                }}
              >
                Apply Strategy
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-6 border-t border-gray-200 pt-6">
        <p className="text-caption font-semibold text-gray-500">2. Generate the draft</p>
        <p className="mt-1 text-body text-gray-600">
          {email
            ? `This opens in your mail app to ${email}. `
            : "Add an email on this lead before Open in email can be used. "}
          You review the draft here, then send it from your own inbox.
        </p>
        <div className="mt-4 grid gap-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Input
              label="Your name"
              value={senderName}
              onChange={(event) => {
                const next = event.target.value;
                setSenderName(next);
                writeStored(SENDER_KEY, next);
              }}
            />
            <Input
              label="Your email"
              type="email"
              value={senderEmail}
              onChange={(event) => {
                const next = event.target.value;
                setSenderEmail(next);
                writeStored(SENDER_EMAIL_KEY, next);
              }}
            />
            <Input
              label="Your WhatsApp"
              value={senderWhatsapp}
              onChange={(event) => {
                const next = event.target.value;
                setSenderWhatsapp(next);
                writeStored(SENDER_WHATSAPP_KEY, next);
              }}
            />
            <Input
              label="Your Portfolio"
              value={senderPortfolio}
              onChange={(event) => {
                const next = event.target.value;
                setSenderPortfolio(next);
                writeStored(SENDER_PORTFOLIO_KEY, next);
              }}
            />
          </div>
          <div>
            <Textarea
              label="Your offer"
              hint={offerHint(suggestion.data?.source, suggestion.isFetching, offerTouched)}
              rows={6}
              value={offer}
              onChange={(event) => {
                const next = event.target.value;
                setOfferTouched(true);
                setOffer(next);
                writeStored(OFFER_KEY, next);
              }}
            />
            <div className="mt-2">
              <Button
                type="button"
                variant="ghost"
                disabled={suggestion.isFetching || generate.isPending}
                onClick={refreshOffer}
              >
                {suggestion.isFetching ? "Updating offer…" : "Suggest from audit"}
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Select
              label="Framework"
              value={framework}
              onChange={(event) => setFramework(event.target.value)}
              options={frameworkOptions}
            />
            <Select
              label="Tone"
              value={tone}
              onChange={(event) => {
                const next = event.target.value;
                if (!isTone(next)) {
                  return;
                }
                setTone(next);
                writeStored(TONE_KEY, next);
              }}
              options={toneOptions}
            />
            <Select
              label="Include Mockup"
              value={mockupId}
              onChange={(event) => setMockupId(event.target.value)}
              options={[
                { value: "", label: mockups.length ? "Auto / Latest Mockup" : "No Mockup Generated" },
                ...mockups.map((m) => ({
                  value: m.id,
                  label: `${m.title || `Mockup v${m.version}`} (${m.status})`,
                })),
              ]}
            />
          </div>
        </div>
        <div className="mt-4">
          <Button
            onClick={() => {
              createDraft(true);
            }}
            isLoading={pending === "ai"}
            disabled={(hasWebsite && running) || aiBlocked || generate.isPending}
          >
            Generate email draft
          </Button>
        </div>
        <p className="mt-3 text-small text-gray-600">
          {hasWebsite
            ? "With a website, the draft uses the audit findings and the offer above, including its price. "
            : "With no website, the draft uses the business details and the offer above, including its price. "}
          Notes, phone numbers, and past emails stay here.
          {provider === "gemini"
            ? " Google's free API tier can use that content to improve its products."
            : ""}
        </p>
        {aiBlocked ? (
          <p className="mt-2 text-small text-gray-600">
            Add a{" "}
            <ExternalLink href="https://aistudio.google.com/apikey">Gemini API key</ExternalLink> or
            a <ExternalLink href="https://console.groq.com/keys">Groq API key</ExternalLink> in the
            server environment, then restart the API. A template can be used until then.
          </p>
        ) : null}
        <div className="mt-6 border-t border-gray-200 pt-6">
          <p className="text-caption font-semibold text-gray-500">Or write from a template</p>
          {activeTemplates.length > 0 ? (
            <div className="mt-4">
              <Select
                label="Template"
                value={templateId}
                onChange={(event) => {
                  setTemplateId(event.target.value);
                }}
                placeholder="Homepage concept"
                options={activeTemplates.map((item) => ({ value: item.id, label: item.name }))}
              />
            </div>
          ) : null}
          <div className="mt-4">
            <Button
              variant="secondary"
              onClick={() => {
                createDraft(false);
              }}
              isLoading={pending === "template"}
              disabled={running || generate.isPending}
            >
              Write from template
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

function offerHint(
  source: "ai" | "audit" | "default" | undefined,
  loading: boolean,
  touched: boolean,
): string {
  if (loading) {
    return "Building an offer from the latest audit findings…";
  }
  if (touched) {
    return "Edited by you. Click Suggest from audit to replace it.";
  }
  if (source === "ai" || source === "audit") {
    return "Written from the audit findings, with a settled price for the work. The email keeps this offer. Edit freely.";
  }
  return "What you want this email to propose. The generated email includes this text.";
}

function ExternalLink({ href, children }: { href: string; children: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={cn("text-primary-700 underline", focusRing)}
    >
      {children}
    </a>
  );
}

function Findings({
  loading,
  missing,
  running,
  failed,
  hasWebsite,
  lines,
}: {
  loading: boolean;
  missing: boolean;
  running: boolean;
  failed: boolean;
  hasWebsite: boolean;
  lines: { title: string; detail: string }[];
}) {
  if (!hasWebsite) {
    return (
      <p className="mt-3 text-body text-gray-600">
        This lead has no website. The email will use the business name, industry, and city, and
        offer to create a professional site.
      </p>
    );
  }
  if (loading) {
    return <p className="mt-3 text-body text-gray-600">Loading the latest audit.</p>;
  }
  if (running) {
    return (
      <p className="mt-3 text-body text-gray-600">
        The audit is still running. The email can be written when those findings are ready.
      </p>
    );
  }
  if (missing) {
    return (
      <p className="mt-3 text-body text-gray-600">
        No audit yet. Open the Audit tab and analyze the website, then come back. The email is
        written from those findings.
      </p>
    );
  }
  if (failed) {
    return (
      <p className="mt-3 text-body text-gray-600">
        The last audit did not finish. You can still write a general note, or run the audit again.
      </p>
    );
  }
  if (lines.length === 0) {
    return (
      <p className="mt-3 text-body text-gray-600">
        The latest audit did not list problems. The email will stay general.
      </p>
    );
  }
  return (
    <ul className="mt-4 space-y-2">
      {lines.map((line) => (
        <li
          key={`${line.title}-${line.detail}`}
          className="rounded-control border border-gray-200 bg-gray-50 px-3 py-2"
        >
          <p className="font-medium text-ink">{line.title}</p>
          <p className="text-small text-gray-600">{line.detail}</p>
        </li>
      ))}
    </ul>
  );
}

function readStored(key: string, fallback: string): string {
  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeStored(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage can be blocked. The draft still uses the current field values.
  }
}

function readTone(): OutreachTone {
  const stored = readStored(TONE_KEY, "professional");
  return isTone(stored) ? stored : "professional";
}

function isTone(value: string): value is OutreachTone {
  return toneOptions.some((option) => option.value === value);
}
