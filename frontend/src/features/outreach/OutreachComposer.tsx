import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useToast } from "../../components/feedback/useToast";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import { useLatestAudit } from "../../hooks/useAudit";
import { useHealth } from "../../hooks/useHealth";
import { useGenerateOutreach, useSuggestOutreachOffer } from "../../hooks/useOutreach";
import { useOutreachTemplates } from "../../hooks/useWorkspace";
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

const toneOptions: { value: OutreachTone; label: string }[] = [
  { value: "professional", label: "Professional" },
  { value: "warm", label: "Warm" },
  { value: "direct", label: "Direct" },
  { value: "brief", label: "Brief" },
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
  const [templateId, setTemplateId] = useState("");
  const [offer, setOffer] = useState(() => readStored(OFFER_KEY, DEFAULT_OFFER));
  const [tone, setTone] = useState<OutreachTone>(() => readTone());
  const [senderName, setSenderName] = useState(() => readStored(SENDER_KEY, ""));
  const [pending, setPending] = useState<"ai" | "template" | null>(null);
  const [offerTouched, setOfferTouched] = useState(() => {
    const stored = readStored(OFFER_KEY, "");
    return Boolean(stored) && stored !== DEFAULT_OFFER;
  });
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
            sender_name: senderName.trim() || undefined,
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
      <div className="mt-6 border-t border-gray-200 pt-6">
        <p className="text-caption font-semibold text-gray-500">2. Generate the draft</p>
        <p className="mt-1 text-body text-gray-600">
          {email
            ? `This opens in your mail app to ${email}. `
            : "Add an email on this lead before Open in email can be used. "}
          You review the draft here, then send it from your own inbox.
        </p>
        <div className="mt-4 grid gap-4">
          <Input
            label="Your name"
            hint="Optional. Used as the sign-off."
            value={senderName}
            onChange={(event) => {
              const next = event.target.value;
              setSenderName(next);
              writeStored(SENDER_KEY, next);
            }}
          />
          <div>
            <Textarea
              label="Your offer"
              hint={offerHint(suggestion.data?.source, suggestion.isFetching, offerTouched)}
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
            ? "With a website, the draft uses the audit findings, including design, SEO, and performance. "
            : "With no website, the draft uses the business details and offers to create one. "}
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
  if (source === "ai") {
    return "Suggested from the audit findings with AI. Edit freely.";
  }
  if (source === "audit") {
    return "Suggested from the audit findings. Edit freely.";
  }
  return "What you want this email to propose.";
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
