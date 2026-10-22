import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  ImageIcon,
  Layers,
  MessageSquare,
  Phone,
  Sparkles,
  UploadCloud,
  Utensils,
  Wrench,
  X,
  Zap,
} from "lucide-react";

import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import { MarkdownView } from "../design-md/markdown";
import { useDesignGuide, useDesignGuides } from "../../hooks/useDesignGuides";
import { useProviders } from "../../hooks/useHealth";
import { useLead } from "../../hooks/useLeads";
import { apiErrorMessage } from "../../lib/apiError";
import { cn, focusRing } from "../../lib/cn";
import { createMockup, processMockup } from "../../services/mockups";
import type { GuideMode, MockupGoal, MockupProvider } from "../../types/mockup";

type CreateMockupDialogProps = {
  open: boolean;
  leadId: string;
  sourceMockupId?: string | null;
  savedGuideName?: string | null;
  defaultProvider?: MockupProvider;
  scenario?: "new_site" | "redesign" | null;
  onClose: () => void;
  onCreated: (mockupId: string) => void;
};

type GoalConfig = {
  value: MockupGoal;
  label: string;
  description: string;
  icon: typeof Phone;
  archetypes: string[];
};

const ALL_GOALS: GoalConfig[] = [
  {
    value: "bookings",
    label: "Book Appointment",
    description: "Featured booking calendar or scheduling widget CTA",
    icon: Calendar,
    archetypes: ["dental", "medical", "salon", "wellness", "fitness"],
  },
  {
    value: "reserve_table",
    label: "Reserve a Table",
    description: "Dinner/event reservation CTA with party size and date",
    icon: Utensils,
    archetypes: ["restaurant", "cafe", "bar", "hospitality"],
  },
  {
    value: "quotes",
    label: "Request a Quote",
    description: "Fast estimate request CTA with turnaround promise",
    icon: Wrench,
    archetypes: ["contractor", "trade", "plumbing", "roofing", "automotive"],
  },
  {
    value: "book_consultation",
    label: "Book Consultation",
    description: "Discovery session or strategy intake call",
    icon: MessageSquare,
    archetypes: ["agency", "consulting", "legal", "accounting"],
  },
  {
    value: "calls",
    label: "Direct Phone Call",
    description: "Prominent tap-to-call button with business hours",
    icon: Phone,
    archetypes: ["emergency", "locksmith", "towing"],
  },
  {
    value: "whatsapp",
    label: "WhatsApp Chat",
    description: "Direct instant messaging for quick customer enquiries",
    icon: Zap,
    archetypes: ["retail", "local"],
  },
  {
    value: "schedule_viewing",
    label: "Schedule Viewing",
    description: "Property tour or facility walkthrough booking",
    icon: Building2,
    archetypes: ["real estate", "coworking", "venue"],
  },
  {
    value: "request_demo",
    label: "Request Demo",
    description: "Interactive product demo or software walkthrough",
    icon: Sparkles,
    archetypes: ["saas", "tech", "platform"],
  },
  {
    value: "buy_product",
    label: "Shop Products / Menu",
    description: "Online catalog or specialty product ordering",
    icon: Layers,
    archetypes: ["ecommerce", "retail", "bakery"],
  },
  {
    value: "visit_location",
    label: "Visit Showroom / Store",
    description: "Physical location, directions, parking, and opening hours",
    icon: Building2,
    archetypes: ["store", "gallery", "showroom"],
  },
  {
    value: "get_started",
    label: "Get Started / Onboard",
    description: "Direct onboarding entry point",
    icon: Zap,
    archetypes: ["membership", "gym", "fitness"],
  },
  {
    value: "submit_inquiry",
    label: "Submit General Inquiry",
    description: "Direct message form with fast reply commitment",
    icon: MessageSquare,
    archetypes: ["general"],
  },
];

const ARCHETYPE_SECTIONS: Record<string, { label: string; sections: string[] }> = {
  dental: {
    label: "Dental & Healthcare Architecture",
    sections: [
      "Navigation & Emergency Contact",
      "Hero (16:9 Treatment Room)",
      "Trust & Clinical Credentials",
      "Core Treatments & Services",
      "Why Patients Choose Us",
      "Real Before & After Gallery",
      "Verified Patient Reviews",
      "Primary Booking CTA",
      "Clinic Hours & Map",
      "Professional Footer",
    ],
  },
  restaurant: {
    label: "Dining & Hospitality Architecture",
    sections: [
      "Atmospheric Header",
      "Hero (16:9 Signature Dish / Ambiance)",
      "Chef's Featured Menu",
      "Culinary Story & Philosophy",
      "Dining Experience Gallery",
      "Guest Accolades & Reviews",
      "Online Table Reservation",
      "Hours, Location & Parking",
      "Footer & Social Links",
    ],
  },
  contractor: {
    label: "Home Services & Contracting Architecture",
    sections: [
      "Direct Call-Out Header",
      "Hero (16:9 Job Site / Craftsmanship)",
      "Service Capabilities Grid",
      "Featured Project Gallery",
      "Licensed & Insured Proof",
      "Step-by-Step Working Process",
      "Verified Homeowner Reviews",
      "Service Areas Covered",
      "Quote Request Form / CTA",
      "Footer & License Numbers",
    ],
  },
  agency: {
    label: "Digital Agency & Tech Architecture",
    sections: [
      "Modern Minimalist Nav",
      "Hero (16:9 Studio / Modern Workplace)",
      "Core Capabilities & Tech Stack",
      "Featured Case Studies & Metrics",
      "Proven Delivery Process",
      "Client Testimonials",
      "Consultation Intake CTA",
      "Footer & Insights",
    ],
  },
  professional: {
    label: "Professional Services Architecture",
    sections: [
      "Credibility Header",
      "Hero (16:9 Executive Office / Advisory)",
      "Practice Areas & Advisory",
      "Why Work With Us",
      "Principal Bios & Accreditations",
      "Client Success Stories",
      "Confidential Consultation CTA",
      "Location & Contact Details",
      "Regulatory Footer",
    ],
  },
  general: {
    label: "Conversion-Focused Architecture",
    sections: [
      "Clear Header & Contact",
      "Hero (16:9 Contextual Photography)",
      "Trust & Value Proposition",
      "Core Offerings & Services",
      "Why Choose Us",
      "Customer Reviews & Proof",
      "Primary Action CTA",
      "Hours & Contact Location",
      "Footer",
    ],
  },
};

function inferArchetype(industry?: string | null, name?: string | null): string {
  const text = `${industry ?? ""} ${name ?? ""}`.toLowerCase();
  if (/dent|ortho|clinic|medical|health|doctor|physio|chiro/.test(text)) return "dental";
  if (/rest|cafe|bar|bistro|dining|grill|bakery|food|pizza|burger|sushi/.test(text)) return "restaurant";
  if (/plumb|roof|paint|electr|contract|construct|hvac|solar|remodel|build/.test(text)) return "contractor";
  if (/agency|design|market|softw|develop|creat|tech|studio|saas/.test(text)) return "agency";
  if (/law|legal|attorney|cpa|account|consult|advis|financ|insur/.test(text)) return "professional";
  return "general";
}

function recommendGoal(archetype: string): MockupGoal {
  switch (archetype) {
    case "dental":
      return "bookings";
    case "restaurant":
      return "reserve_table";
    case "contractor":
      return "quotes";
    case "agency":
    case "professional":
      return "book_consultation";
    default:
      return "calls";
  }
}

export function CreateMockupDialog({
  open,
  leadId,
  sourceMockupId,
  savedGuideName,
  defaultProvider,
  scenario,
  onClose,
  onCreated,
}: CreateMockupDialogProps) {
  const queryClient = useQueryClient();
  const providers = useProviders();
  const leadQuery = useLead(leadId);
  const lead = leadQuery.data;

  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<GuideMode>(savedGuideName ? "keep" : "none");
  const [guideId, setGuideId] = useState<string | null>(null);
  const [requirements, setRequirements] = useState("");
  const [provider, setProvider] = useState<MockupProvider>(defaultProvider ?? "stitch");
  const [goal, setGoal] = useState<MockupGoal>("bookings");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showSectionDetails, setShowSectionDetails] = useState(false);

  const guides = useDesignGuides(mode === "selected" ? search : "", "");
  const selected = useDesignGuide(mode === "selected" ? (guideId ?? undefined) : undefined);

  const archetype = useMemo(() => {
    return inferArchetype(lead?.industry, lead?.business_name);
  }, [lead?.industry, lead?.business_name]);

  const archetypePlan = ARCHETYPE_SECTIONS[archetype] ?? ARCHETYPE_SECTIONS.general;

  const providerOptions = useMemo(() => {
    const snapshots = providers.data?.providers ?? [];
    return [
      {
        value: "stitch",
        label: "Google Stitch · AI Design Engine (Primary)",
      },
      {
        value: "banani",
        label: "Banani AI · Interactive UI Copilot",
      },
      {
        value: "magicpath",
        label: "MagicPath · AI Visual Canvas",
      },
      {
        value: "gemini",
        label: providerLabel(snapshots.find((item) => item.id === "gemini"), "Gemini"),
      },
      {
        value: "groq",
        label: providerLabel(snapshots.find((item) => item.id === "groq"), "Groq"),
      },
    ];
  }, [providers.data]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const initialMode = savedGuideName ? "keep" : "none";
    setMode(initialMode);
    setGuideId(null);
    setRequirements("");
    const recommended = recommendGoal(archetype);
    setGoal(recommended);
    setFiles([]);
    setError(null);
    setSaving(false);
    setShowSectionDetails(false);
    setProvider(defaultProvider ?? "stitch");
  }, [open, savedGuideName, defaultProvider, archetype]);

  async function onSubmit() {
    if (saving) {
      return;
    }
    setError(null);
    if (mode === "selected" && !guideId) {
      setError("Please select a design guide from the list below.");
      return;
    }
    setSaving(true);
    try {
      const created = await createMockup(
        {
          lead_id: leadId,
          requirements: requirements.trim() || null,
          source_mockup_id: sourceMockupId ?? null,
          design_guide_id: mode === "selected" ? guideId : null,
          guide_mode: mode,
          provider,
          goal,
        },
        files,
      );
      // On Vercel, generation runs via /process
      void processMockup(created.id).then(() => {
        void queryClient.invalidateQueries({ queryKey: ["mockups"] });
        void queryClient.invalidateQueries({ queryKey: ["mockup", created.id] });
      });
      await queryClient.invalidateQueries({ queryKey: ["mockups"] });
      onCreated(created.id);
    } catch (caught) {
      setError(apiErrorMessage(caught, "The mockup could not be started."));
      setSaving(false);
    }
  }

  const locationStr = [lead?.city, lead?.country].filter(Boolean).join(", ");

  return (
    <Modal
      open={open}
      size="lg"
      title={sourceMockupId ? "Regenerate Bespoke Mockup" : "Design Bespoke Website Mockup"}
      description="Engineered specifically for this prospect using verified business data, technical audit findings, market research, and Unsplash/Pixabay photography curation."
      onClose={() => {
        if (!saving) {
          onClose();
        }
      }}
    >
      <div className="space-y-5">
        {/* Lead Intelligence Context Card */}
        {lead ? (
          <div className="rounded-xl border border-gray-200 bg-gradient-to-r from-gray-50 via-white to-gray-50 p-3.5 text-small">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-100 text-primary-700">
                  <Building2 size={16} />
                </span>
                <div>
                  <span className="font-semibold text-ink">{lead.business_name}</span>
                  {lead.industry ? (
                    <span className="ml-2 rounded-md bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700">
                      {lead.industry}
                    </span>
                  ) : null}
                  {locationStr ? (
                    <span className="ml-2 text-xs text-gray-500">· {locationStr}</span>
                  ) : null}
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-xs">
                {scenario === "redesign" ? (
                  <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-0.5 font-medium text-amber-700 border border-amber-200">
                    <Zap size={12} /> Redesign Concept · Audit Informed
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700 border border-emerald-200">
                    <Sparkles size={12} /> First Digital Presence
                  </span>
                )}
              </div>
            </div>
          </div>
        ) : null}

        {/* Engine & Conversion Goal Row */}
        <div className="grid gap-4 sm:grid-cols-2">
          {/* AI Design Engine */}
          <div>
            <Select
              label="Design Engine / Provider"
              value={provider}
              options={providerOptions}
              onChange={(event) => {
                setProvider(event.target.value as MockupProvider);
              }}
            />
            <p className="mt-1 text-xs text-gray-500">
              Conditioned on verified business facts & CRO principles.
            </p>
          </div>

          {/* Primary Conversion Goal */}
          <div>
            <label className="mb-1 block text-small font-medium text-gray-700" htmlFor="mockup-goal-select">
              Primary Conversion Goal
            </label>
            <select
              id="mockup-goal-select"
              value={goal}
              onChange={(e) => setGoal(e.target.value as MockupGoal)}
              className={cn(
                "h-10 w-full rounded-control border border-gray-300 bg-white px-3 text-body text-ink transition-colors",
                focusRing,
              )}
            >
              {ALL_GOALS.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label} {recommendGoal(archetype) === g.value ? "★ (Recommended for this Niche)" : ""}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">
              {ALL_GOALS.find((g) => g.value === goal)?.description}
            </p>
          </div>
        </div>

        {/* Evidence-Based Section Blueprint Accordion */}
        <div className="rounded-xl border border-gray-200 bg-white p-3.5 shadow-xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-blue-50 text-blue-600">
                <Layers size={14} />
              </span>
              <div>
                <span className="text-small font-medium text-ink">
                  {archetypePlan.label}
                </span>
                <span className="ml-2 text-xs text-gray-500">
                  ({archetypePlan.sections.length} evidence-based sections planned)
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setShowSectionDetails(!showSectionDetails)}
              className="flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-700"
            >
              {showSectionDetails ? (
                <>
                  Hide Architecture <ChevronUp size={14} />
                </>
              ) : (
                <>
                  Preview Architecture <ChevronDown size={14} />
                </>
              )}
            </button>
          </div>

          {/* Section Chips */}
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {archetypePlan.sections.slice(0, showSectionDetails ? undefined : 6).map((sec, idx) => (
              <span
                key={sec}
                className="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-700"
              >
                <span className="font-semibold text-gray-400">{idx + 1}.</span> {sec}
              </span>
            ))}
            {!showSectionDetails && archetypePlan.sections.length > 6 ? (
              <button
                type="button"
                onClick={() => setShowSectionDetails(true)}
                className="inline-flex items-center rounded-md bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700"
              >
                +{archetypePlan.sections.length - 6} more sections
              </button>
            ) : null}
          </div>

          {/* Automated Visual Curation Banner */}
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50/70 px-3 py-1.5 text-xs text-emerald-800">
            <ImageIcon size={14} className="shrink-0 text-emerald-600" />
            <span>
              <strong>Visual Curation:</strong> High-res photography automatically curated from Unsplash & Pixabay (Hero 16:9, Services, Atmosphere).
            </span>
          </div>
        </div>

        {/* Visual Design System (Design.md) */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-small font-medium text-gray-700">
              Visual Design Guide (Design.md)
            </label>
            <span className="text-xs text-gray-500">
              Defines typography, palette, card styling & spacing
            </span>
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            {savedGuideName ? (
              <button
                type="button"
                onClick={() => setMode("keep")}
                className={cn(
                  "flex flex-col rounded-lg border p-2.5 text-left transition-all",
                  mode === "keep"
                    ? "border-primary-500 bg-primary-50/50 ring-1 ring-primary-500"
                    : "border-gray-200 bg-white hover:border-gray-300",
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-ink">Keep Saved</span>
                  {mode === "keep" ? <CheckCircle2 size={14} className="text-primary-600" /> : null}
                </div>
                <span className="mt-1 line-clamp-1 text-xs text-gray-600">{savedGuideName}</span>
              </button>
            ) : null}

            <button
              type="button"
              onClick={() => setMode("selected")}
              className={cn(
                "flex flex-col rounded-lg border p-2.5 text-left transition-all",
                mode === "selected"
                  ? "border-primary-500 bg-primary-50/50 ring-1 ring-primary-500"
                  : "border-gray-200 bg-white hover:border-gray-300",
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-ink">Choose Guide</span>
                {mode === "selected" ? <CheckCircle2 size={14} className="text-primary-600" /> : null}
              </div>
              <span className="mt-1 text-xs text-gray-600">Select a curated Design.md</span>
            </button>

            <button
              type="button"
              onClick={() => setMode("none")}
              className={cn(
                "flex flex-col rounded-lg border p-2.5 text-left transition-all",
                mode === "none"
                  ? "border-primary-500 bg-primary-50/50 ring-1 ring-primary-500"
                  : "border-gray-200 bg-white hover:border-gray-300",
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-ink">Default System</span>
                {mode === "none" ? <CheckCircle2 size={14} className="text-primary-600" /> : null}
              </div>
              <span className="mt-1 text-xs text-gray-600">Clean agency local aesthetic</span>
            </button>
          </div>

          {/* Guide Selector Drawer */}
          {mode === "selected" ? (
            <div className="mt-3 space-y-3 rounded-xl border border-gray-200 bg-gray-50/50 p-3">
              <input
                id="guide-picker-search"
                placeholder="Search style guides by name or aesthetic (e.g. Modern, Minimal, Bold)..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className={cn(
                  "h-9 w-full rounded-control border border-gray-300 bg-white px-3 text-body font-normal text-ink",
                  focusRing,
                )}
              />
              <div className="grid max-h-40 gap-2 overflow-y-auto sm:grid-cols-2">
                {guides.data?.items.length ? (
                  guides.data.items.map((guide) => (
                    <button
                      key={guide.id}
                      type="button"
                      onClick={() => setGuideId(guide.id)}
                      className={cn(
                        "rounded-lg border p-2.5 text-left transition-all",
                        guideId === guide.id
                          ? "border-primary-500 bg-white shadow-xs ring-1 ring-primary-500"
                          : "border-gray-200 bg-white hover:border-gray-300",
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-ink">{guide.name}</span>
                        {guideId === guide.id ? (
                          <CheckCircle2 size={14} className="text-primary-600" />
                        ) : null}
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-gray-500">
                        {guide.description || "Design system specification."}
                      </p>
                    </button>
                  ))
                ) : (
                  <p className="col-span-2 py-2 text-center text-xs text-gray-500">
                    No design guides match your search.
                  </p>
                )}
              </div>

              {selected.data ? (
                <div className="max-h-36 overflow-y-auto rounded-lg border border-gray-200 bg-white p-3 text-xs">
                  <MarkdownView source={selected.data.content} />
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        {/* Custom Branding / Image Assets */}
        <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50/50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-small font-medium text-gray-700">
              Custom Logo or Photography (Optional)
            </span>
            <span className="text-xs text-gray-500">Up to 4 images · 1.5MB each</span>
          </div>

          <div className="mt-2 flex items-center gap-3">
            <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">
              <UploadCloud size={14} /> Upload Files
              <input
                type="file"
                className="hidden"
                accept="image/png,image/jpeg,image/webp,image/gif"
                multiple
                onChange={(event) => {
                  setFiles(Array.from(event.target.files ?? []).slice(0, 4));
                }}
              />
            </label>
            <span className="text-xs text-gray-500">
              Leave blank to automatically use Unsplash/Pixabay curated assets.
            </span>
          </div>

          {files.length > 0 ? (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {files.map((file, idx) => (
                <span
                  key={file.name + idx}
                  className="inline-flex items-center gap-1 rounded-md bg-white border border-gray-200 px-2 py-1 text-xs text-ink shadow-2xs"
                >
                  <FileText size={12} className="text-gray-400" />
                  <span className="max-w-[120px] truncate">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => setFiles(files.filter((_, i) => i !== idx))}
                    className="text-gray-400 hover:text-danger"
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
          ) : null}
        </div>

        {/* Additional Instructions */}
        <Textarea
          label="Custom Design & Strategy Directives (Optional)"
          hint="Any specific services to feature, color requests, or promotion copy. Verified business data is automatically included."
          value={requirements}
          onChange={(event) => setRequirements(event.target.value)}
          rows={2}
        />

        {error ? (
          <div className="rounded-lg bg-red-50 p-3 text-small text-danger border border-red-200" role="alert">
            {error}
          </div>
        ) : null}

        {/* Modal Actions */}
        <div className="flex items-center justify-between border-t border-gray-100 pt-3">
          <span className="text-xs text-gray-500">
            Generates responsive HTML5 + CSS · Zero external CDN dependencies
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={saving} onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={() => void onSubmit()} isLoading={saving}>
              <Sparkles size={16} className="mr-1.5" />
              Generate Bespoke Mockup
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

function providerLabel(
  snapshot: { configured: boolean; model: string; display_name: string | null } | undefined,
  name: string,
): string {
  if (!snapshot) {
    return name;
  }
  const model = snapshot.display_name || snapshot.model;
  if (!snapshot.configured) {
    return `${name} (not configured)`;
  }
  return model ? `${name} · ${model}` : name;
}
