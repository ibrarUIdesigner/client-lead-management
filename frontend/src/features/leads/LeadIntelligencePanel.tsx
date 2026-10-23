import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Check,
  Compass,
  Copy,
  Flame,
  Layers,
  Lightbulb,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";
import { useToast } from "../../components/feedback/useToast";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { useLeadIntelligence, useRefreshLeadIntelligence } from "../../hooks/useIntelligence";
import { cn } from "../../lib/cn";
import type { SignalItem } from "../../types/intelligence";

type LeadIntelligencePanelProps = {
  leadId: string;
  onSelectTab: (tabId: string) => void;
};

export function LeadIntelligencePanel({ leadId, onSelectTab }: LeadIntelligencePanelProps) {
  const { notify } = useToast();
  const { data: intel, isLoading, isError, refetch } = useLeadIntelligence(leadId);
  const refreshMutation = useRefreshLeadIntelligence(leadId);
  const [copiedSection, setCopiedSection] = useState<string | null>(null);
  const [activeSignalFilter, setActiveSignalFilter] = useState<"all" | "website" | "business" | "sales">("all");

  if (isLoading) {
    return (
      <Card className="p-12 text-center shadow-xs">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-primary-50">
          <RefreshCw className="size-6 animate-spin text-primary-600" />
        </div>
        <h3 className="mt-3 text-h4 font-bold text-ink">Synthesizing Sales Intelligence</h3>
        <p className="mt-1 text-small text-gray-500">
          Correlating website audit findings, market signals, and custom sales strategy...
        </p>
      </Card>
    );
  }

  if (isError || !intel) {
    return (
      <Card className="p-8 text-center shadow-xs border-danger-200 bg-red-50/20">
        <div className="mx-auto flex size-10 items-center justify-center rounded-full bg-red-100 text-danger">
          <AlertCircle className="size-5" />
        </div>
        <h3 className="mt-2 text-h4 font-bold text-ink">Could Not Load Lead Intelligence</h3>
        <p className="mt-1 text-small text-gray-600">
          Unable to retrieve signals and opportunities for this lead.
        </p>
        <Button variant="secondary" className="mt-4" onClick={() => void refetch()}>
          Retry Loading
        </Button>
      </Card>
    );
  }

  const { opportunity_score: score, signals, opportunities, strategy, next_action } = intel;

  const webSignals = signals.filter((s) => s.type === "website");
  const bizSignals = signals.filter((s) => s.type === "business");
  const salesSignals = signals.filter((s) => s.type === "sales");

  const filteredSignals =
    activeSignalFilter === "website"
      ? webSignals
      : activeSignalFilter === "business"
      ? bizSignals
      : activeSignalFilter === "sales"
      ? salesSignals
      : signals;

  const scoreBadgeTone =
    score.total_score >= 70
      ? "bg-amber-100 text-amber-900 border-amber-300"
      : score.total_score >= 40
      ? "bg-blue-100 text-blue-900 border-blue-300"
      : "bg-gray-100 text-gray-800 border-gray-300";

  const scoreProgressBg =
    score.total_score >= 70
      ? "bg-gradient-to-r from-amber-500 to-orange-500"
      : score.total_score >= 40
      ? "bg-gradient-to-r from-blue-500 to-indigo-500"
      : "bg-gray-400";

  const frameworkInfo = humanizeFramework(strategy.recommended_framework);

  const copyBattleCard = () => {
    const text = [
      `Sales Battle Card: ${intel.business_name}`,
      `Opportunity Score: ${score.total_score}/100 (${score.tier_label})`,
      `Recommended Framework: ${frameworkInfo.label}`,
      `Settled Price: $${strategy.settled_price}`,
      `Sales Angle: ${strategy.outreach_angle}`,
      `Suggested Offer: "${strategy.suggested_offer}"`,
      `Mockup Focus: ${strategy.mockup_focus}`,
      "",
      "Primary Opportunities:",
      ...opportunities.map((o) => `- ${o.problem} (${o.impact.toUpperCase()} IMPACT) -> Solution: ${o.recommended_solution}`),
      "",
      `Top Signals (${signals.length}):`,
      ...signals.map((s) => `- [${s.type.toUpperCase()}] ${s.name}: ${s.evidence} (${Math.round(s.confidence * 100)}% conf)`),
    ].join("\n");

    navigator.clipboard.writeText(text);
    setCopiedSection("battlecard");
    notify("Sales battle card copied to clipboard.", "success");
    setTimeout(() => setCopiedSection(null), 2500);
  };

  const copyText = (content: string, id: string, label: string) => {
    navigator.clipboard.writeText(content);
    setCopiedSection(id);
    notify(`${label} copied to clipboard.`, "success");
    setTimeout(() => setCopiedSection(null), 2500);
  };

  return (
    <div className="space-y-6">
      {/* Intelligence Header Bar & Feeder Sources */}
      <div className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 shadow-2xs sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
              <Sparkles className="size-4" />
            </span>
            <h2 className="text-h4 font-bold text-ink">Harvey Sales Intelligence</h2>
            <Badge tone="indigo">Autonomous Scout & Strategist</Badge>
          </div>
          <p className="mt-0.5 text-caption text-gray-500">
            Real-time cross-correlation of website audit metrics, search signals, and objection strategy.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            className="h-8 px-2.5 text-caption font-semibold"
            onClick={copyBattleCard}
            title="Copy full executive sales cheat sheet"
          >
            {copiedSection === "battlecard" ? (
              <Check className="size-3.5 mr-1 text-emerald-600" />
            ) : (
              <Copy className="size-3.5 mr-1 text-gray-500" />
            )}
            <span>{copiedSection === "battlecard" ? "Copied" : "Copy Battle Card"}</span>
          </Button>

          <Button
            variant="ghost"
            className="h-8 px-2.5 text-caption font-semibold text-gray-600 hover:text-ink"
            isLoading={refreshMutation.isPending}
            onClick={() => {
              refreshMutation.mutate(undefined, {
                onSuccess: () => notify("Sales intelligence and score recalculated.", "success"),
              });
            }}
            title="Recalculate signals and opportunities"
          >
            <RefreshCw className={cn("size-3.5 mr-1", refreshMutation.isPending && "animate-spin")} />
            Recalculate
          </Button>
        </div>
      </div>

      {/* Hero Dual Grid: Opportunity Score + Next Best Action */}
      <div className="grid gap-5 lg:grid-cols-12">
        {/* Opportunity Score Card (5 cols) */}
        <Card className="lg:col-span-5 flex flex-col justify-between border-gray-200 bg-white shadow-sm p-5">
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Compass className="size-4 text-primary-600" />
                <h3 className="text-caption font-bold tracking-wider text-gray-500 uppercase">
                  Opportunity Score
                </h3>
              </div>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-caption font-bold shadow-2xs",
                  scoreBadgeTone
                )}
              >
                <Flame className="size-3.5 fill-current" />
                {score.total_score >= 70 ? "High Opportunity" : score.total_score >= 40 ? "Medium Opportunity" : "Low Opportunity"}
              </span>
            </div>

            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-5xl font-black tracking-tight text-ink">
                {score.total_score}
              </span>
              <span className="text-h4 font-medium text-gray-400">/ 100</span>
            </div>

            {/* Visual Progress Meter */}
            <div className="mt-3">
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-100">
                <div
                  className={cn("h-full transition-all duration-700 rounded-full", scoreProgressBg)}
                  style={{ width: `${Math.max(score.total_score, 4)}%` }}
                />
              </div>
              <p className="mt-2 text-2xs text-gray-500 leading-relaxed">
                {score.total_score >= 70
                  ? "🔥 Prime conversion candidate. High website friction combined with strong business credibility makes this a top-priority outreach target."
                  : score.total_score >= 40
                  ? "⚡ Viable prospect. Demonstrates actionable website conversion friction and clear services scope."
                  : "○ Lower opportunity tier. Limited detected friction or missing public business signals."}
              </p>
            </div>

            {/* Explainable Factor Breakdown */}
            <div className="mt-5 border-t border-gray-100 pt-4">
              <div className="flex items-center justify-between mb-2.5">
                <h4 className="text-2xs font-bold text-gray-500 uppercase tracking-wider">
                  Score Breakdown ({score.breakdown.length} Factors)
                </h4>
                <span className="text-2xs text-gray-400 font-mono">100 Max</span>
              </div>

              <div className="space-y-2">
                {score.breakdown.map((factor, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-gray-100 bg-gray-50/70 p-2.5 transition-all hover:bg-gray-50 hover:border-gray-200"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center justify-center rounded-md bg-white border border-gray-200 px-1.5 py-0.5 text-caption font-bold text-ink shadow-2xs">
                          +{factor.points}
                        </span>
                        <span className="text-small font-semibold text-gray-900">{factor.label}</span>
                      </div>
                      <Badge tone={getCategoryTone(factor.category)} className="text-2xs uppercase">
                        {factor.category}
                      </Badge>
                    </div>
                    <p className="mt-1 text-caption text-gray-600 leading-snug">
                      {factor.reason}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>

        {/* Next Best Action Card (7 cols) */}
        <Card className="lg:col-span-7 flex flex-col justify-between border-indigo-200 bg-gradient-to-br from-indigo-50/60 via-white to-purple-50/30 shadow-sm p-5">
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-caption font-bold uppercase tracking-wider text-indigo-900">
                <span className="flex size-6 items-center justify-center rounded-full bg-indigo-600 text-white shadow-2xs">
                  <Zap className="size-3.5" />
                </span>
                <span>Next Best Action</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Badge tone={next_action.priority === "critical" ? "red" : next_action.priority === "high" ? "orange" : "indigo"}>
                  {next_action.priority.toUpperCase()} PRIORITY
                </Badge>
                <Badge tone="gray">
                  {Math.round(next_action.confidence * 100)}% Confidence
                </Badge>
              </div>
            </div>

            <div className="mt-4">
              <h3 className="text-h3 font-black text-ink">{next_action.action}</h3>
              <p className="mt-2 text-body text-gray-700 leading-relaxed font-normal">
                {next_action.reason}
              </p>
            </div>

            {/* Quick Context Card */}
            <div className="mt-5 rounded-xl border border-indigo-100 bg-white/90 p-4 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-caption font-bold uppercase text-indigo-950 flex items-center gap-1.5">
                  <Sparkles className="size-3.5 text-indigo-600" />
                  Strategist Context
                </span>
                <span className="text-2xs font-semibold text-gray-500">
                  Target: {frameworkInfo.label}
                </span>
              </div>
              <p className="mt-1.5 text-small text-gray-800 leading-relaxed">
                <strong className="text-gray-900">Angle: </strong>
                &ldquo;{strategy.outreach_angle}&rdquo;
              </p>
              {strategy.mockup_focus ? (
                <p className="mt-1 text-caption text-gray-600">
                  <strong className="text-gray-800">Concept Mockup: </strong>
                  {strategy.mockup_focus}
                </p>
              ) : null}
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-3 border-t border-indigo-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <span className="text-caption text-gray-600">
              Pipeline Stage: <strong className="text-ink">{intel.lead_status}</strong>
            </span>
            <Button
              variant="primary"
              className="h-10 px-5 text-small font-bold shadow-sm flex items-center justify-center gap-1.5"
              onClick={() => onSelectTab(next_action.target_tab)}
            >
              <span>{next_action.cta_label}</span>
              <ArrowRight className="size-4" />
            </Button>
          </div>
        </Card>
      </div>

      {/* Harvey Sales Battle Card (Dedicated Strategic Section) */}
      <Card className="border-indigo-200 bg-gradient-to-br from-white via-indigo-50/20 to-purple-50/30 p-5 shadow-xs">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-gray-100 pb-3">
          <div className="flex items-center gap-2">
            <Compass className="size-5 text-indigo-600" />
            <div>
              <h3 className="text-h4 font-bold text-ink">Sales Strategy Battle Card</h3>
              <p className="text-caption text-gray-500">
                Actionable pitch arguments and pricing ready for your outreach or sales call.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone="indigo">{frameworkInfo.label}</Badge>
            <Badge tone="green">Settled Price: ${strategy.settled_price}</Badge>
          </div>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-gray-200 bg-white p-3.5 shadow-2xs">
            <span className="text-2xs font-bold uppercase tracking-wider text-gray-400">Winning Angle</span>
            <p className="mt-1 text-small font-semibold text-gray-900 leading-snug">
              {strategy.outreach_angle}
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-3.5 shadow-2xs">
            <span className="text-2xs font-bold uppercase tracking-wider text-gray-400">Mockup Strategy</span>
            <p className="mt-1 text-small text-gray-800 leading-snug">
              {strategy.mockup_focus}
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-3.5 shadow-2xs">
            <span className="text-2xs font-bold uppercase tracking-wider text-gray-400">Framework Purpose</span>
            <p className="mt-1 text-caption text-gray-600 leading-snug">
              {frameworkInfo.description}
            </p>
          </div>
        </div>

        {/* Suggested Offer Quote Box */}
        {strategy.suggested_offer ? (
          <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="text-caption font-bold text-indigo-950 flex items-center gap-1.5">
                <Sparkles className="size-4 text-indigo-600" />
                Suggested Email Offer / Pitch Hook
              </span>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="h-7 px-2 text-caption font-semibold text-indigo-700 hover:text-indigo-900"
                  onClick={() => copyText(strategy.suggested_offer, "offer", "Suggested offer")}
                >
                  {copiedSection === "offer" ? (
                    <Check className="size-3.5 mr-1 text-emerald-600" />
                  ) : (
                    <Copy className="size-3.5 mr-1" />
                  )}
                  <span>{copiedSection === "offer" ? "Copied" : "Copy Offer"}</span>
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  className="h-7 px-2.5 text-caption font-semibold"
                  onClick={() => onSelectTab("outreach")}
                >
                  Use in Outreach
                  <ArrowRight className="size-3 ml-1" />
                </Button>
              </div>
            </div>
            <p className="text-small text-gray-800 italic leading-relaxed bg-white/90 p-3 rounded-lg border border-indigo-100/70 shadow-2xs">
              &ldquo;{strategy.suggested_offer}&rdquo;
            </p>
          </div>
        ) : null}
      </Card>

      {/* Scout Signals Section */}
      <div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-3">
          <div className="flex items-center gap-2">
            <Lightbulb className="size-4 text-amber-600" />
            <h3 className="text-h4 font-bold text-ink">Detected Signals ({signals.length})</h3>
            <span className="text-caption text-gray-500">Harvey Scout Agent</span>
          </div>

          {/* Category Filter Chips */}
          <div className="flex flex-wrap items-center gap-1.5">
            <FilterChip
              active={activeSignalFilter === "all"}
              onClick={() => setActiveSignalFilter("all")}
              label="All"
              count={signals.length}
            />
            <FilterChip
              active={activeSignalFilter === "website"}
              onClick={() => setActiveSignalFilter("website")}
              label="Website Friction"
              count={webSignals.length}
            />
            <FilterChip
              active={activeSignalFilter === "business"}
              onClick={() => setActiveSignalFilter("business")}
              label="Business Momentum"
              count={bizSignals.length}
            />
            <FilterChip
              active={activeSignalFilter === "sales"}
              onClick={() => setActiveSignalFilter("sales")}
              label="Sales Intent"
              count={salesSignals.length}
            />
          </div>
        </div>

        {filteredSignals.length === 0 ? (
          <Card className="p-6 text-center text-gray-500 text-small">
            No signals in this filter category for this lead.
          </Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filteredSignals.map((sig, idx) => (
              <SignalCard key={idx} signal={sig} />
            ))}
          </div>
        )}
      </div>

      {/* Actionable Opportunities Board */}
      <div>
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <Layers className="size-4 text-purple-600" />
            <h3 className="text-h4 font-bold text-ink">Actionable Opportunities ({opportunities.length})</h3>
            <span className="text-caption text-gray-500">Sales Arguments</span>
          </div>
        </div>

        {opportunities.length === 0 ? (
          <Card className="p-6 text-center text-gray-500 text-small">
            <p>No actionable opportunities detected yet. Run a Website Audit or Research to populate.</p>
            <div className="mt-3 flex justify-center gap-2">
              <Button variant="secondary" className="h-8" onClick={() => onSelectTab("audit")}>
                Run Audit
              </Button>
              <Button variant="secondary" className="h-8" onClick={() => onSelectTab("research")}>
                Run Research
              </Button>
            </div>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {opportunities.map((opp, idx) => (
              <OpportunityCard
                key={idx}
                opp={opp}
                onUseInOutreach={() => onSelectTab("outreach")}
                onUseInMockup={() => onSelectTab("mockups")}
                onCopy={(text) => copyText(text, `opp-${idx}`, "Opportunity solution")}
                isCopied={copiedSection === `opp-${idx}`}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-caption font-semibold transition-all",
        active
          ? "bg-ink text-white shadow-2xs"
          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
      )}
    >
      <span>{label}</span>
      <span className={cn("text-2xs rounded-full px-1.5 py-0.2", active ? "bg-white/20 text-white" : "bg-gray-200 text-gray-700")}>
        {count}
      </span>
    </button>
  );
}

function SignalCard({ signal }: { signal: SignalItem }) {
  const isWeb = signal.type === "website";
  const isBiz = signal.type === "business";
  const tip = getSignalSalesTip(signal.name);

  return (
    <div
      className={cn(
        "flex flex-col justify-between rounded-xl border p-3.5 shadow-2xs transition-all hover:shadow-xs",
        isWeb
          ? "border-amber-200 bg-amber-50/30 hover:border-amber-300"
          : isBiz
          ? "border-emerald-200 bg-emerald-50/30 hover:border-emerald-300"
          : "border-purple-200 bg-purple-50/30 hover:border-purple-300"
      )}
    >
      <div>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5">
            {isWeb ? (
              <AlertTriangle className="size-4 text-amber-600 shrink-0" />
            ) : isBiz ? (
              <TrendingUp className="size-4 text-emerald-600 shrink-0" />
            ) : (
              <Zap className="size-4 text-purple-600 shrink-0" />
            )}
            <h4 className="text-small font-bold text-ink leading-tight">
              {humanizeSignalName(signal.name)}
            </h4>
          </div>
          <span className="text-2xs font-bold text-gray-500 bg-white/80 border border-gray-200/80 px-1.5 py-0.5 rounded shadow-2xs">
            {Math.round(signal.confidence * 100)}%
          </span>
        </div>

        <p className="mt-2 text-caption text-gray-700 leading-snug">
          {signal.evidence}
        </p>

        {tip ? (
          <div className="mt-2.5 rounded-md bg-white/90 p-2 border border-gray-100 text-2xs text-gray-700">
            <span className="font-semibold text-gray-900">{tip}</span>
          </div>
        ) : null}
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-gray-100/80 pt-2 text-2xs text-gray-400">
        <span>Source: {signal.source}</span>
        <span className="uppercase font-semibold tracking-wider text-gray-500">{signal.type}</span>
      </div>
    </div>
  );
}

function OpportunityCard({
  opp,
  onUseInOutreach,
  onUseInMockup,
  onCopy,
  isCopied,
}: {
  opp: any;
  onUseInOutreach: () => void;
  onUseInMockup: () => void;
  onCopy: (text: string) => void;
  isCopied: boolean;
}) {
  return (
    <Card className="flex flex-col justify-between p-4.5 border-gray-200 shadow-2xs hover:shadow-xs transition-all">
      <div>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge tone={opp.impact === "high" ? "orange" : "blue"} className="font-bold">
              {opp.impact.toUpperCase()} IMPACT
            </Badge>
            <span className="text-2xs text-gray-400 font-medium">{opp.source}</span>
          </div>
          <span className="text-2xs font-semibold text-gray-500">
            {Math.round(opp.confidence * 100)}% confidence
          </span>
        </div>

        <h4 className="mt-2.5 text-body font-bold text-ink">{opp.problem}</h4>
        <p className="mt-1 text-caption text-gray-500 italic bg-gray-50/60 p-2 rounded border border-gray-100">
          &ldquo;{opp.evidence}&rdquo;
        </p>

        <div className="mt-3 rounded-lg bg-primary-50/40 p-3 border border-primary-100/70">
          <span className="text-2xs font-bold uppercase tracking-wider text-primary-900">
            Recommended Solution
          </span>
          <p className="mt-1 text-small text-gray-800 leading-relaxed font-medium">
            {opp.recommended_solution}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-3">
        <Button
          type="button"
          variant="ghost"
          className="h-7 px-2 text-caption text-gray-600 hover:text-ink"
          onClick={() => onCopy(opp.recommended_solution)}
        >
          {isCopied ? <Check className="size-3.5 mr-1 text-emerald-600" /> : <Copy className="size-3.5 mr-1" />}
          <span>{isCopied ? "Copied" : "Copy Solution"}</span>
        </Button>

        <div className="flex items-center gap-1.5">
          <Button
            type="button"
            variant="ghost"
            className="h-7 px-2 text-caption font-semibold text-purple-700 hover:text-purple-900"
            onClick={onUseInMockup}
          >
            Use in Mockup
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="h-7 px-2 text-caption font-semibold text-primary-700 hover:text-primary-900"
            onClick={onUseInOutreach}
          >
            Use in Outreach
            <ArrowRight className="size-3 ml-1" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

function getCategoryTone(category: string): "gray" | "indigo" | "blue" | "green" | "orange" {
  switch (category.toLowerCase()) {
    case "website":
      return "orange";
    case "business":
      return "green";
    case "intent":
      return "indigo";
    case "conversion":
      return "blue";
    default:
      return "gray";
  }
}

function humanizeSignalName(name: string): string {
  switch (name) {
    case "NO_WEBSITE":
      return "No Official Website";
    case "OUTDATED_WEBSITE":
      return "Outdated Website Design";
    case "SLOW_WEBSITE":
      return "Slow Mobile Loading";
    case "POOR_MOBILE_UX":
      return "Poor Mobile Usability";
    case "WEAK_CTA":
    case "NO_CLEAR_CTA":
      return "Weak Call to Action";
    case "MISSING_CONTACT_FORM":
      return "Missing Contact Form";
    case "MISSING_BOOKING":
      return "No Online Booking Mechanism";
    case "POOR_SEO":
    case "MISSING_META":
      return "SEO Optimization Gap";
    case "WEAK_SERVICE_PRESENTATION":
      return "Unclear Service Showcase";
    case "STRONG_REPUTATION":
      return "High Customer Reputation";
    case "WEAK_REPUTATION":
      return "Low / Unclaimed Reviews";
    case "ACTIVE_SOCIAL_MEDIA":
      return "Active Social Media Presence";
    case "EXPANDING":
      return "Business Expanding";
    case "HIRING":
      return "Actively Hiring";
    case "RUNNING_ADS":
      return "Running Paid Ads";
    case "HIGH_INTENT":
      return "High Conversion Intent";
    case "MEDIUM_INTENT":
      return "Moderate Conversion Intent";
    case "LOW_INTENT":
      return "Early Prospect Intent";
    default:
      return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

function getSignalSalesTip(name: string): string | null {
  switch (name) {
    case "SLOW_WEBSITE":
      return "Pitch Tip: Cite mobile load delay in your subject line to grab immediate attention.";
    case "POOR_MOBILE_UX":
      return "Pitch Tip: Highlight how viewport overflow frustrates smartphone visitors.";
    case "MISSING_CONTACT_FORM":
      return "Pitch Tip: Offer a frictionless 3-field quick estimate form above the fold.";
    case "MISSING_BOOKING":
      return "Pitch Tip: Propose an automated appointment booking widget to capture leads 24/7.";
    case "NO_WEBSITE":
      return "Pitch Tip: Emphasize lost inquiries from local customers searching Google.";
    case "ACTIVE_SOCIAL_MEDIA":
      return "Pitch Tip: Reference recent social posts in your opening line to establish rapport.";
    case "STRONG_REPUTATION":
      return "Pitch Tip: Suggest showcasing their 5-star Google review proof prominently on homepage.";
    case "EXPANDING":
    case "HIRING":
      return "Pitch Tip: Congratulate them on growth; frame the website as matching their expansion.";
    case "RUNNING_ADS":
      return "Pitch Tip: Emphasize how a faster landing page cuts wasted ad spend.";
    case "HIGH_INTENT":
      return "Pitch Tip: Skip intro chit-chat and offer a 5-minute visual walkthrough directly.";
    default:
      return null;
  }
}

function humanizeFramework(framework: string): { label: string; description: string } {
  switch (framework.toLowerCase()) {
    case "mockup_led":
      return {
        label: "Mockup-Led Framework",
        description: "Lead with a custom homepage concept preview specifically tailored for their business.",
      };
    case "audit_led":
      return {
        label: "Audit-Led Framework",
        description: "Focus on audited mobile load times and friction points observed during testing.",
      };
    case "research_led":
      return {
        label: "Research-Led Framework",
        description: "Leverage competitor booking standards and industry benchmark gaps.",
      };
    case "opportunity_led":
      return {
        label: "Opportunity-Led Framework",
        description: "Frame lost customer inquiries and offer a clean, complete digital storefront.",
      };
    case "problem_solution":
    default:
      return {
        label: "Problem + Solution Framework",
        description: "Highlight a direct clarity improvement with a quick, low-risk turnaround.",
      };
  }
}
