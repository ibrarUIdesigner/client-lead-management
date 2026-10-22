import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Compass,
  Copy,
  ExternalLink,
  Globe,
  Lightbulb,
  Newspaper,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { useState } from "react";

import { useToast } from "../../components/feedback/useToast";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { useLeadResearch, useTriggerResearch } from "../../hooks/useResearch";
import { cn } from "../../lib/cn";
import { formatWhen } from "../../lib/format";
import type { LeadDetail } from "../../types/lead";

type LeadResearchSectionProps = {
  lead: LeadDetail;
  onSelectTab?: (tabId: string) => void;
};

export function LeadResearchSection({ lead, onSelectTab }: LeadResearchSectionProps) {
  const { notify } = useToast();
  const researchQuery = useLeadResearch(lead.id);
  const triggerResearch = useTriggerResearch(lead.id);

  const [activeSection, setActiveSection] = useState<"research" | "summary">("summary");
  const [copied, setCopied] = useState(false);
  const [customQuery, setCustomQuery] = useState("");
  const [showQueryInput, setShowQueryInput] = useState(false);
  const [preferredTool, setPreferredTool] = useState<"tavily" | "exa">("tavily");

  const research = researchQuery.data;
  const isRunning = research?.status === "RUNNING" || triggerResearch.isPending;

  const handleRun = (force = false) => {
    triggerResearch.mutate(
      {
        force_refresh: force,
        custom_query: customQuery.trim() || undefined,
        preferred_tool: preferredTool,
      },
      {
        onSuccess: (data: any) => {
          if (data?.research_data?.fallback_used) {
            notify("Tavily reached limits. Fallback to Exa succeeded.", "info");
          } else {
            notify("Lead research completed successfully.", "success");
          }
        },
        onError: (err: any) => {
          notify(err?.response?.data?.message || "Failed to research lead.", "danger");
        },
      },
    );
  };

  const handleCopySummary = async () => {
    if (!research?.summary) return;
    try {
      await navigator.clipboard.writeText(research.summary);
      setCopied(true);
      notify("Research summary & proactive solutions copied to clipboard.", "success");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      notify("Failed to copy to clipboard.", "danger");
    }
  };

  return (
    <Card className="overflow-hidden border-primary-200 bg-white p-0 shadow-sm">
      {/* Header Banner */}
      <div className="border-b border-gray-100 bg-gradient-to-r from-primary-50/70 via-indigo-50/40 to-white px-5 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary-600 text-white shadow-sm">
              <Sparkles className="size-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-h4 font-bold text-ink">Lead Research & Intelligence</h3>
                <span className="flex items-center gap-1.5">
                  {research && research.status === "COMPLETED" ? (
                    research.research_data?.fallback_used ? (
                      <Badge tone="orange">Exa (Tavily limit fallback)</Badge>
                    ) : (
                      <Badge tone={research.research_data?.provider_used === "exa" ? "blue" : "indigo"}>
                        {research.research_data?.provider_used === "exa" ? "Exa Neural Search" : "Tavily Search"}
                      </Badge>
                    )
                  ) : (
                    <>
                      <Badge tone="indigo">Tavily (Primary)</Badge>
                      <Badge tone="gray">Exa (Fallback)</Badge>
                    </>
                  )}
                </span>
              </div>
              <p className="mt-0.5 text-caption text-gray-600">
                Researches company offerings, online presence, and generates proactive solutions before pitch.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {research && research.status === "COMPLETED" ? (
              <>
                <Button
                  variant="secondary"
                  className="h-8 px-2.5 text-small"
                  onClick={handleCopySummary}
                  disabled={isRunning}
                >
                  {copied ? (
                    <>
                      <Check className="size-3.5 text-emerald-600" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="size-3.5" />
                      Copy Summary
                    </>
                  )}
                </Button>
                <Button
                  variant="secondary"
                  className="h-8 px-2.5 text-small"
                  onClick={() => handleRun(true)}
                  disabled={isRunning}
                >
                  <RefreshCw className={cn("size-3.5", isRunning && "animate-spin")} />
                  Re-run Research
                </Button>
              </>
            ) : null}

            {!research && !isRunning ? (
              <Button
                variant="primary"
                className="h-8 px-2.5 text-small"
                onClick={() => handleRun(false)}
                disabled={isRunning}
              >
                <Search className="size-3.5" />
                Research Lead
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="p-5">
        {/* Loading / Running state */}
        {isRunning ? (
          <div className="py-8 text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-primary-50 text-primary-600">
              <RefreshCw className="size-6 animate-spin" />
            </div>
            <h4 className="mt-4 text-body font-semibold text-ink">
              Researching {lead.business_name} with {preferredTool === "tavily" ? "Tavily (Tool 1)" : "Exa (Tool 2)"}...
            </h4>
            <p className="mx-auto mt-1 max-w-md text-small text-gray-600">
              Analyzing company offerings. If {preferredTool === "tavily" ? "Tavily" : "Exa"} hits limits, the other tool will automatically engage as fallback.
            </p>
          </div>
        ) : null}

        {/* Failed state */}
        {!isRunning && research?.status === "FAILED" ? (
          <div className="rounded-lg border border-red-200 bg-red-50/50 p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="size-5 text-red-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <h4 className="text-small font-semibold text-red-900">Research Failed</h4>
                <p className="mt-1 text-caption text-red-700">
                  {research.error_message || "Could not retrieve web research intelligence for this lead."}
                </p>
                <Button
                  variant="secondary"
                  className="mt-3 h-8 bg-white px-2.5 text-small"
                  onClick={() => handleRun(true)}
                >
                  <RefreshCw className="size-3.5" />
                  Try Again
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {/* Empty State: Not Researched Yet */}
        {!isRunning && !research ? (
          <div className="rounded-card border border-dashed border-gray-300 bg-gray-50/50 p-6 text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-white text-primary-600 shadow-sm border border-gray-100">
              <Compass className="size-6" />
            </div>
            <h4 className="mt-3 text-body font-semibold text-ink">
              No research data gathered yet
            </h4>
            <p className="mx-auto mt-1 max-w-lg text-small text-gray-600">
              Perform deep intelligence search before generating mockups and outreach.
              Uses Tavily as primary tool, with automatic fallback to Exa if limits are reached.
            </p>

            <div className="mt-4 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Button variant="primary" onClick={() => handleRun(false)}>
                <Search className="size-4" />
                Run Lead Research Now
              </Button>
              <Button
                variant="ghost"
                className="h-8 px-2.5 text-small"
                onClick={() => setShowQueryInput(!showQueryInput)}
              >
                {showQueryInput ? "Hide custom query" : "Customize search query"}
              </Button>
            </div>

            {showQueryInput ? (
              <div className="mx-auto mt-3 max-w-md space-y-2">
                <input
                  type="text"
                  placeholder={`${lead.business_name} ${lead.city || ""} ${lead.industry || ""}`}
                  value={customQuery}
                  onChange={(e) => setCustomQuery(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-small text-ink focus:border-primary-500 focus:outline-none"
                />
                <div className="flex items-center justify-center gap-2 text-caption text-gray-600">
                  <span>Primary tool:</span>
                  <label className="flex items-center gap-1 cursor-pointer">
                    <input
                      type="radio"
                      name="primaryTool"
                      value="tavily"
                      checked={preferredTool === "tavily"}
                      onChange={() => setPreferredTool("tavily")}
                    />
                    Tavily (Exa fallback)
                  </label>
                  <label className="flex items-center gap-1 cursor-pointer">
                    <input
                      type="radio"
                      name="primaryTool"
                      value="exa"
                      checked={preferredTool === "exa"}
                      onChange={() => setPreferredTool("exa")}
                    />
                    Exa (Tavily fallback)
                  </label>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {/* Completed State: 2 Comprehensive Sections */}
        {!isRunning && research?.status === "COMPLETED" ? (
          <div className="space-y-5">
            {/* Section Tabs Switcher */}
            <div className="flex border-b border-gray-200">
              <button
                type="button"
                onClick={() => setActiveSection("summary")}
                className={cn(
                  "flex items-center gap-2 border-b-2 px-4 py-2.5 text-small font-semibold transition-colors",
                  activeSection === "summary"
                    ? "border-primary-600 text-primary-700"
                    : "border-transparent text-gray-500 hover:text-ink",
                )}
              >
                <Lightbulb className="size-4" />
                Section 2: Summary & Proactive Solutions
                <span className="rounded-full bg-primary-100 px-2 py-0.5 text-caption font-medium text-primary-800">
                  {research.research_data?.proactive_solutions?.length || 0} Solutions
                </span>
              </button>

              <button
                type="button"
                onClick={() => setActiveSection("research")}
                className={cn(
                  "flex items-center gap-2 border-b-2 px-4 py-2.5 text-small font-semibold transition-colors",
                  activeSection === "research"
                    ? "border-primary-600 text-primary-700"
                    : "border-transparent text-gray-500 hover:text-ink",
                )}
              >
                <Compass className="size-4" />
                Section 1: Comprehensive Research
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-caption font-medium text-gray-700">
                  {research.sources?.length || 0} Sources
                </span>
              </button>
            </div>

            {/* SECTION 2: SUMMARY & PROACTIVE SOLUTIONS */}
            {activeSection === "summary" ? (
              <div className="space-y-5">
                {/* Executive Summary Card */}
                <div className="rounded-card border border-indigo-100 bg-indigo-50/30 p-4 sm:p-5">
                  <div className="flex items-center gap-2 text-primary-900 font-semibold text-small">
                    <Target className="size-4 text-primary-600" />
                    Strategic Assessment & Executive Summary
                  </div>
                  <p className="mt-2 whitespace-pre-line text-body text-gray-800 leading-relaxed">
                    {research.research_data?.executive_summary ||
                      research.summary?.split("---")[1] ||
                      "Strategic summary available."}
                  </p>
                </div>

                {/* Proactive Solutions Grid */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="flex items-center gap-2 text-small font-bold text-ink uppercase tracking-wide">
                      <Lightbulb className="size-4 text-amber-500" />
                      Proactive Solutions to Pitch Customers
                    </h4>
                    <span className="text-caption text-gray-500">
                      Weaved automatically into email drafts
                    </span>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {(research.research_data?.proactive_solutions || []).map((solution, i) => (
                      <div
                        key={i}
                        className="group flex flex-col justify-between rounded-lg border border-emerald-200 bg-emerald-50/30 p-4 transition-all hover:border-emerald-400 hover:shadow-sm"
                      >
                        <div>
                          <div className="flex items-center justify-between">
                            <span className="flex items-center gap-1.5 text-caption font-bold text-emerald-800">
                              <CheckCircle2 className="size-4 text-emerald-600" />
                              Solution {i + 1}
                            </span>
                            <Badge tone="green">Ready to Pitch</Badge>
                          </div>
                          <p className="mt-2 text-small font-medium text-ink leading-snug">
                            {solution}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* High Impact Opportunities */}
                {research.research_data?.high_impact_opportunities?.length ? (
                  <div className="rounded-card border border-gray-200 bg-gray-50/50 p-4">
                    <h5 className="flex items-center gap-2 text-small font-semibold text-ink">
                      <TrendingUp className="size-4 text-blue-600" />
                      High-Impact Growth & Conversion Opportunities
                    </h5>
                    <ul className="mt-2 space-y-1.5">
                      {research.research_data.high_impact_opportunities.map((opp, i) => (
                        <li key={i} className="flex items-start gap-2 text-small text-gray-700">
                          <ChevronRight className="size-4 text-blue-500 shrink-0 mt-0.5" />
                          <span>{opp}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {/* Call To Actions */}
                <div className="flex flex-wrap items-center gap-3 pt-2">
                  {onSelectTab ? (
                    <>
                      <Button
                        variant="primary"
                        onClick={() => onSelectTab("outreach")}
                      >
                        <span>Draft Outreach with Solutions</span>
                        <ArrowRight className="size-4 ml-1" />
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => onSelectTab("mockups")}
                      >
                        <span>Generate Mockup from Insights</span>
                      </Button>
                    </>
                  ) : null}
                </div>
              </div>
            ) : null}

            {/* SECTION 1: COMPREHENSIVE RESEARCH */}
            {activeSection === "research" ? (
              <div className="space-y-5">
                {/* Company Profile & Offerings */}
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-card border border-gray-200 p-4">
                    <h5 className="text-caption font-bold text-gray-500 uppercase tracking-wider">
                      Company Profile & Background
                    </h5>
                    <p className="mt-2 text-small text-gray-800 leading-relaxed">
                      {research.research_data?.company_profile || "Information collected via search."}
                    </p>
                  </div>

                  <div className="rounded-card border border-gray-200 p-4">
                    <h5 className="text-caption font-bold text-gray-500 uppercase tracking-wider">
                      Services & Offerings
                    </h5>
                    <p className="mt-2 text-small text-gray-800 leading-relaxed">
                      {research.research_data?.services_and_offerings || "Core commercial services."}
                    </p>
                  </div>
                </div>

                {/* Pain Points & Bottlenecks */}
                <div className="rounded-card border border-amber-200 bg-amber-50/40 p-4 sm:p-5">
                  <h5 className="flex items-center gap-2 text-small font-bold text-amber-900">
                    <ShieldAlert className="size-4 text-amber-600" />
                    Identified Operational & Digital Bottlenecks
                  </h5>
                  <ul className="mt-3 space-y-2">
                    {(research.research_data?.pain_points_and_gaps || []).map((point, i) => (
                      <li key={i} className="flex items-start gap-2 text-small text-amber-950">
                        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-amber-200/80 text-caption font-bold text-amber-900 mt-0.5">
                          {i + 1}
                        </span>
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Digital Presence & Market Competitors */}
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-card border border-gray-200 p-4">
                    <h5 className="flex items-center gap-2 text-caption font-bold text-gray-500 uppercase tracking-wider">
                      <Globe className="size-3.5 text-gray-400" />
                      Digital & Online Presence
                    </h5>
                    <p className="mt-2 text-small text-gray-700 leading-relaxed">
                      {research.research_data?.digital_presence || "Digital channels analyzed."}
                    </p>
                  </div>

                  <div className="rounded-card border border-gray-200 p-4">
                    <h5 className="flex items-center gap-2 text-caption font-bold text-gray-500 uppercase tracking-wider">
                      <Newspaper className="size-3.5 text-gray-400" />
                      Market & Competitive Positioning
                    </h5>
                    <p className="mt-2 text-small text-gray-700 leading-relaxed">
                      {research.research_data?.competitors_and_market || "Market landscape analyzed."}
                    </p>
                  </div>
                </div>

                {/* Verified Research Sources (Tavily & Exa) */}
                <div>
                  <h5 className="text-caption font-bold text-gray-500 uppercase tracking-wider mb-2">
                    Verified Sources & Citations ({research.sources?.length || 0})
                  </h5>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {(research.sources || []).map((src, i) => (
                      <div
                        key={i}
                        className="flex flex-col justify-between rounded-lg border border-gray-200 bg-white p-3 hover:border-primary-300"
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2">
                            <span className="line-clamp-1 text-small font-semibold text-ink">
                              {src.title}
                            </span>
                            <Badge tone={src.provider === "tavily" ? "indigo" : "blue"}>
                              {src.provider.toUpperCase()}
                            </Badge>
                          </div>
                          {src.snippet ? (
                            <p className="mt-1 line-clamp-2 text-caption text-gray-600">
                              {src.snippet}
                            </p>
                          ) : null}
                        </div>
                        {src.url ? (
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-2 inline-flex items-center gap-1 text-caption font-medium text-primary-700 hover:underline"
                          >
                            <ExternalLink className="size-3" />
                            Visit Source
                          </a>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}

            {/* Research Completed Timestamp Footer */}
            {research.completed_at ? (
              <div className="border-t border-gray-100 pt-3 text-caption text-gray-500 flex items-center justify-between">
                <span>
                  Intelligence via <strong>{research.research_data?.provider_used === "exa" ? "Exa" : "Tavily"}</strong>
                  {research.research_data?.fallback_used ? " (fallback after limit)" : ""} · {formatWhen(research.completed_at)} · Query: &ldquo;{research.query_used}&rdquo;
                </span>
                <span className="flex items-center gap-1 text-emerald-700">
                  <CheckCircle2 className="size-3.5" />
                  Verified
                </span>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}
