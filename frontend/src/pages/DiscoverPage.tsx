import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Globe2,
  KeyRound,
  MapPin,
  PauseCircle,
  Phone,
  Play,
  Plus,
  Radio,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "../components/feedback/EmptyState";
import { QueryGate } from "../components/feedback/QueryGate";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { Input } from "../components/ui/Input";
import {
  useCreateDiscoveryBatch,
  useDeleteDiscoverySearch,
  useDiscovery,
  useRunDiscovery,
  useUpdateDiscoverySearch,
} from "../hooks/useDiscovery";
import { useLeads } from "../hooks/useLeads";
import { apiErrorMessage } from "../lib/apiError";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import type { DiscoverySearch, DiscoveryStatus } from "../types/discovery";
import type { Lead } from "../types/lead";

const websiteLabels: Record<string, { label: string; tone: "green" | "orange" | "gray" | "indigo" }> =
  {
    missing: { label: "No website", tone: "green" },
    social_only: { label: "Social only", tone: "orange" },
    present: { label: "Has a website", tone: "gray" },
    pending: { label: "Audit pending", tone: "indigo" },
    analyzed: { label: "Audited", tone: "indigo" },
    failed: { label: "Audit failed", tone: "orange" },
  };

type SourceKey =
  | "use_apollo"
  | "use_serpapi"
  | "use_scrapingbee"
  | "use_openstreetmap"
  | "use_google"
  | "use_yelp"
  | "use_yell"
  | "use_businesslist"
  | "use_epages";

type SourceOption = {
  key: SourceKey;
  label: string;
  hint: string;
  needsKey?: "google" | "yelp" | "apollo" | "serpapi" | "scrapingbee";
};

const SOURCE_OPTIONS: SourceOption[] = [
  {
    key: "use_apollo",
    label: "Apollo.io",
    hint: "B2B organizations & contacts",
    needsKey: "apollo",
  },
  {
    key: "use_serpapi",
    label: "SerpApi (Google Maps)",
    hint: "Live Google Maps & Search",
    needsKey: "serpapi",
  },
  {
    key: "use_scrapingbee",
    label: "ScrapingBee",
    hint: "Google search & Web scraping",
    needsKey: "scrapingbee",
  },
  {
    key: "use_openstreetmap",
    label: "OpenStreetMap",
    hint: "Free · worldwide",
  },
  {
    key: "use_google",
    label: "Google Places",
    hint: "Needs API key",
    needsKey: "google",
  },
  {
    key: "use_yelp",
    label: "Yelp",
    hint: "Needs API key",
    needsKey: "yelp",
  },
  {
    key: "use_yell",
    label: "Yell",
    hint: "UK listings",
  },
  {
    key: "use_businesslist",
    label: "BusinessList.pk",
    hint: "Pakistan",
  },
  {
    key: "use_epages",
    label: "ePages.pk",
    hint: "Pakistan",
  },
];

export function DiscoverPage() {
  const discovery = useDiscovery();
  const found = useLeads({
    tag: "discovered",
    limit: 12,
    sort: "created_at",
    direction: "desc",
  });

  return (
    <>
      <PageHeader
        title="Discover leads"
        description="Find local businesses that need a website or redesign. Save searches, run them on demand, and pitch the strongest matches."
        actions={
          discovery.data && discovery.data.searches.some((search) => search.is_active) ? (
            <RunAllButton running={discovery.data.running} />
          ) : null
        }
      />
      <QueryGate
        pending={discovery.isPending}
        error={discovery.error}
        onRetry={() => {
          void discovery.refetch();
        }}
        fallback="Lead discovery could not be loaded."
      >
        {discovery.data ? (
          <DiscoverWorkspace
            status={discovery.data}
            leads={found.data?.items ?? []}
            leadsTotal={found.data?.total ?? found.data?.items.length ?? 0}
            leadsPending={found.isPending}
          />
        ) : null}
      </QueryGate>
    </>
  );
}

function DiscoverWorkspace({
  status,
  leads,
  leadsTotal,
  leadsPending,
}: {
  status: DiscoveryStatus;
  leads: Lead[];
  leadsTotal: number;
  leadsPending: boolean;
}) {
  const activeCount = status.searches.filter((search) => search.is_active).length;
  const totalCreated = status.searches.reduce(
    (sum, search) => sum + (search.last_created_count ?? 0),
    0,
  );
  const sourcesReady =
    1 +
    (status.google_configured ? 1 : 0) +
    (status.yelp_configured ? 1 : 0) +
    (status.apollo_configured ? 1 : 0) +
    (status.serpapi_configured ? 1 : 0) +
    (status.scrapingbee_configured ? 1 : 0) +
    3;

  return (
    <div className="space-y-6">
      <OverviewStats
        activeCount={activeCount}
        searchCount={status.searches.length}
        leadsTotal={leadsTotal}
        totalCreated={totalCreated}
        nextRunAt={status.next_run_at}
        running={status.running}
        sourcesReady={sourcesReady}
        sourcesTotal={9}
      />

      {status.running ? <RunningBanner message={status.latest_message} /> : null}

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(260px,340px)]">
        <div className="min-w-0 space-y-6">
          <SearchForm
            categories={status.categories}
            googleConfigured={status.google_configured}
            yelpConfigured={status.yelp_configured}
            apolloConfigured={status.apollo_configured}
            serpapiConfigured={status.serpapi_configured}
            scrapingbeeConfigured={status.scrapingbee_configured}
            running={status.running}
          />
          <SearchList searches={status.searches} running={status.running} />
          <FoundLeads leads={leads} total={leadsTotal} pending={leadsPending} />
        </div>

        <aside className="space-y-6 xl:sticky xl:top-6">
          <ScheduleCard
            schedule={status.schedule}
            nextRunAt={status.next_run_at}
            running={status.running}
            googleConfigured={status.google_configured}
            yelpConfigured={status.yelp_configured}
            apolloConfigured={status.apollo_configured}
            serpapiConfigured={status.serpapi_configured}
            scrapingbeeConfigured={status.scrapingbee_configured}
            latestMessage={status.latest_message}
          />
          <HowItWorksCard />
        </aside>
      </div>
    </div>
  );
}

function OverviewStats({
  activeCount,
  searchCount,
  leadsTotal,
  totalCreated,
  nextRunAt,
  running,
  sourcesReady,
  sourcesTotal,
}: {
  activeCount: number;
  searchCount: number;
  leadsTotal: number;
  totalCreated: number;
  nextRunAt: string | null;
  running: boolean;
  sourcesReady: number;
  sourcesTotal: number;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        icon={<Radio className="size-4" aria-hidden="true" />}
        label="Active searches"
        value={String(activeCount)}
        hint={
          searchCount === 0
            ? "Create your first search"
            : `${searchCount} saved · ${searchCount - activeCount} paused`
        }
      />
      <StatCard
        icon={<Building2 className="size-4" aria-hidden="true" />}
        label="Discovered leads"
        value={String(leadsTotal)}
        hint={totalCreated > 0 ? `${totalCreated} added in latest runs` : "Ready for outreach"}
      />
      <StatCard
        icon={<CalendarClock className="size-4" aria-hidden="true" />}
        label="Next daily run"
        value={running ? "Running now" : shortWhen(nextRunAt)}
        hint={running ? "Results appear when finished" : "While the API stays online"}
      />
      <StatCard
        icon={<Globe2 className="size-4" aria-hidden="true" />}
        label="Sources ready"
        value={`${sourcesReady}/${sourcesTotal}`}
        hint={
          sourcesReady < sourcesTotal
            ? "Add API keys for Google & Yelp"
            : "All listing sources available"
        }
      />
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-caption font-semibold uppercase tracking-wide text-gray-500">
            {label}
          </p>
          <p className="mt-2 text-h2 font-bold tabular-nums text-ink">{value}</p>
          <p className="mt-1 text-caption text-gray-500">{hint}</p>
        </div>
        <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-control bg-primary-50 text-primary-700">
          {icon}
        </span>
      </div>
    </Card>
  );
}

function RunningBanner({ message }: { message: string | null }) {
  return (
    <div
      className="flex items-start gap-3 rounded-card border border-primary-200 bg-primary-50 px-4 py-3"
      role="status"
      aria-live="polite"
    >
      <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-white text-primary-700 shadow-sm">
        <Search className="size-4 animate-pulse" aria-hidden="true" />
      </span>
      <div>
        <p className="text-body font-semibold text-primary-900">Searching listings…</p>
        <p className="mt-0.5 text-small text-primary-800">
          {message ?? "Scanning public directories. New leads will show up here when the run finishes."}
        </p>
      </div>
    </div>
  );
}

function RunAllButton({ running }: { running: boolean }) {
  const run = useRunDiscovery();
  const { notify } = useToast();

  return (
    <Button
      isLoading={run.isPending || running}
      onClick={() => {
        run.mutate(undefined, {
          onError: (error) => {
            notify(apiErrorMessage(error, "The search could not start."), "danger");
          },
        });
      }}
    >
      <Play className="size-4" aria-hidden="true" />
      {running ? "Searching…" : "Run active searches"}
    </Button>
  );
}

function SearchForm({
  categories,
  googleConfigured,
  yelpConfigured,
  apolloConfigured,
  serpapiConfigured,
  scrapingbeeConfigured,
  running,
}: {
  categories: { value: string; label: string }[];
  googleConfigured: boolean;
  yelpConfigured: boolean;
  apolloConfigured: boolean;
  serpapiConfigured: boolean;
  scrapingbeeConfigured: boolean;
  running: boolean;
}) {
  const createBatch = useCreateDiscoveryBatch();
  const run = useRunDiscovery();
  const { notify } = useToast();

  const [selectedCategories, setSelectedCategories] = useState<string[]>([
    categories[0]?.value ?? "dentist",
  ]);
  const [customInput, setCustomInput] = useState("");
  const [customCategories, setCustomCategories] = useState<string[]>([]);
  const [selectedCountry, setSelectedCountry] = useState("Worldwide");
  const [limitPlace, setLimitPlace] = useState(false);
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [sources, setSources] = useState<Record<SourceKey, boolean>>({
    use_apollo: true,
    use_serpapi: true,
    use_scrapingbee: true,
    use_openstreetmap: true,
    use_google: true,
    use_yelp: true,
    use_yell: true,
    use_businesslist: true,
    use_epages: true,
  });
  const [error, setError] = useState<string | null>(null);

  function toggleSource(key: SourceKey) {
    setSources((current) => ({ ...current, [key]: !current[key] }));
  }

  function toggleCategory(cat: string) {
    setSelectedCategories((current) =>
      current.includes(cat) ? current.filter((c) => c !== cat) : [...current, cat],
    );
    setError(null);
  }

  function selectCategoryGroup(group: string[]) {
    setSelectedCategories((current) => {
      const merged = new Set([...current, ...group]);
      return Array.from(merged);
    });
    setError(null);
  }

  function selectAllCategories() {
    setSelectedCategories(categories.map((c) => c.value));
    setError(null);
  }

  function addCustomNiche() {
    const trimmed = customInput.trim();
    if (trimmed.length < 2) return;
    if (!customCategories.includes(trimmed)) {
      setCustomCategories((curr) => [...curr, trimmed]);
    }
    if (!selectedCategories.includes(trimmed)) {
      setSelectedCategories((curr) => [...curr, trimmed]);
    }
    setCustomInput("");
    setError(null);
  }

  function save(searchNow: boolean) {
    if (selectedCategories.length === 0) {
      setError("Please select at least one niche / business category.");
      return;
    }
    const place = limitPlace ? city.trim() : "";
    const region = limitPlace ? country.trim() : selectedCountry;
    if (limitPlace && (place.length < 2 || region.length < 2)) {
      setError("Enter both a city and a country, or switch to Worldwide.");
      return;
    }
    if (!Object.values(sources).some(Boolean)) {
      setError("Choose at least one listing source.");
      return;
    }
    setError(null);

    createBatch.mutate(
      {
        categories: selectedCategories,
        city: place,
        country: region,
        ...sources,
        run_now: searchNow,
      },
      {
        onSuccess: (result) => {
          notify(
            searchNow
              ? `Saved ${result.created_count} search(es) and started discovery!`
              : `Saved ${result.created_count} search(es) for the daily run.`,
            "success",
          );
        },
        onError: (saveError) => {
          setError(apiErrorMessage(saveError, "The searches could not be saved."));
        },
      },
    );
  }

  return (
    <Card className="overflow-hidden p-0">
      <div className="border-b border-gray-100 px-4 py-4 sm:px-6 sm:py-5">
        <div className="flex items-start gap-3">
          <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-panel bg-primary text-white shadow-md">
            <Plus className="size-5" aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-h3 font-semibold text-ink">New multi-niche search</h2>
            <p className="mt-1 max-w-2xl text-body text-gray-600">
              Select one or multiple niches and target countries. The discovery engine fetches verified businesses with email addresses across Apollo.io, SerpApi, ScrapingBee, and OpenStreetMap.
            </p>
          </div>
        </div>
      </div>

      <form
        className="space-y-6 px-4 py-4 sm:px-6 sm:py-5"
        onSubmit={(event) => {
          event.preventDefault();
          save(true);
        }}
      >
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <SectionLabel>Who to find (Niches / Categories)</SectionLabel>
            <Badge tone={selectedCategories.length > 0 ? "indigo" : "gray"}>
              {selectedCategories.length === 0
                ? "No niche selected"
                : `${selectedCategories.length} selected`}
            </Badge>
          </div>

          {/* Quick industry group presets */}
          <div className="flex flex-wrap items-center gap-1.5 text-caption">
            <span className="text-gray-500 font-medium mr-1">Presets:</span>
            <button
              type="button"
              onClick={selectAllCategories}
              className="rounded-md border border-gray-200 bg-white px-2.5 py-1 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              ⚡ All ({categories.length})
            </button>
            <button
              type="button"
              onClick={() => selectCategoryGroup(["dentist", "clinic", "pharmacy", "veterinary"])}
              className="rounded-md border border-gray-200 bg-white px-2.5 py-1 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              🏥 Healthcare
            </button>
            <button
              type="button"
              onClick={() => selectCategoryGroup(["real_estate", "lawyer", "accountant"])}
              className="rounded-md border border-gray-200 bg-white px-2.5 py-1 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              💼 Professional
            </button>
            <button
              type="button"
              onClick={() => selectCategoryGroup(["restaurant", "cafe", "bakery", "hotel"])}
              className="rounded-md border border-gray-200 bg-white px-2.5 py-1 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              🍽️ Hospitality
            </button>
            <button
              type="button"
              onClick={() => selectCategoryGroup(["gym", "salon", "photographer"])}
              className="rounded-md border border-gray-200 bg-white px-2.5 py-1 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              ✂️ Care & Fitness
            </button>
            <button
              type="button"
              onClick={() => selectCategoryGroup(["plumber", "electrician", "car_repair"])}
              className="rounded-md border border-gray-200 bg-white px-2.5 py-1 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              🔧 Trade
            </button>
            {selectedCategories.length > 0 ? (
              <button
                type="button"
                onClick={() => setSelectedCategories([])}
                className="rounded-md border border-red-200 bg-red-50/50 px-2.5 py-1 text-red-600 hover:bg-red-50 transition-colors"
              >
                Clear
              </button>
            ) : null}
          </div>

          {/* Multi-niche toggleable pills */}
          <div className="flex flex-wrap gap-2 pt-1">
            {categories.map((cat) => {
              const isSelected = selectedCategories.includes(cat.value);
              return (
                <button
                  key={cat.value}
                  type="button"
                  onClick={() => toggleCategory(cat.value)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-small font-medium transition-all shadow-sm",
                    isSelected
                      ? "bg-primary-600 text-white shadow-primary-200 ring-2 ring-primary-600 ring-offset-1"
                      : "border border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50"
                  )}
                >
                  <span className="text-[13px] font-bold">
                    {isSelected ? "✓" : "+"}
                  </span>
                  <span>{cat.label}</span>
                </button>
              );
            })}
            {customCategories.map((custom) => {
              const isSelected = selectedCategories.includes(custom);
              return (
                <button
                  key={custom}
                  type="button"
                  onClick={() => toggleCategory(custom)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-small font-medium transition-all shadow-sm",
                    isSelected
                      ? "bg-primary-700 text-white ring-2 ring-primary-700 ring-offset-1"
                      : "border border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50"
                  )}
                >
                  <span className="text-[13px] font-bold">
                    {isSelected ? "✓" : "+"}
                  </span>
                  <span>{custom}</span>
                </button>
              );
            })}
          </div>

          {/* Add custom niche input */}
          <div className="flex items-center gap-2 pt-1 sm:max-w-md">
            <Input
              label=""
              aria-label="Add custom niche"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addCustomNiche();
                }
              }}
              placeholder="Add other niche (e.g. SaaS, Pet Grooming, Marketing)..."
            />
            <Button
              type="button"
              variant="secondary"
              onClick={addCustomNiche}
              disabled={!customInput.trim()}
            >
              Add
            </Button>
          </div>
        </section>

        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <SectionLabel>Where to look (Countries & Markets)</SectionLabel>
            <button
              type="button"
              className={cn("text-small font-semibold text-primary-700", focusRing)}
              onClick={() => {
                setLimitPlace((current) => !current);
                setError(null);
              }}
            >
              {limitPlace ? "Search Worldwide (Global hubs)" : "Limit to specific city / country"}
            </button>
          </div>

          {!limitPlace ? (
            <div className="space-y-2">
              <p className="text-body text-gray-600">
                Worldwide search automatically covers major international business hubs (New York, San Francisco, London, Toronto, Sydney, Chicago, Los Angeles, Miami, Berlin, Dublin, etc.).
              </p>
              <div className="flex flex-wrap items-center gap-1.5 text-caption">
                <span className="text-gray-500 font-medium mr-1">Target Country:</span>
                {[
                  { label: "🌐 Worldwide (All)", value: "Worldwide" },
                  { label: "🇺🇸 United States", value: "United States" },
                  { label: "🇬🇧 United Kingdom", value: "United Kingdom" },
                  { label: "🇨🇦 Canada", value: "Canada" },
                  { label: "🇦🇺 Australia", value: "Australia" },
                  { label: "🇩🇪 Germany", value: "Germany" },
                  { label: "🇦🇪 UAE", value: "United Arab Emirates" },
                  { label: "🇵🇰 Pakistan", value: "Pakistan" },
                ].map((c) => (
                  <button
                    key={c.value}
                    type="button"
                    onClick={() => setSelectedCountry(c.value)}
                    className={cn(
                      "rounded-full px-2.5 py-1 text-caption font-medium transition-colors",
                      selectedCountry === c.value
                        ? "bg-primary-600 text-white shadow-sm"
                        : "border border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                    )}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="City"
                value={city}
                onChange={(event) => setCity(event.target.value)}
                placeholder="e.g. New York, London, Toronto"
              />
              <Input
                label="Country"
                value={country}
                onChange={(event) => setCountry(event.target.value)}
                placeholder="e.g. United States, United Kingdom, Canada"
              />
            </div>
          )}
        </section>

        <section className="space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <SectionLabel>Listing sources</SectionLabel>
            <p className="text-caption text-gray-500">
              {Object.values(sources).filter(Boolean).length} selected
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {SOURCE_OPTIONS.map((option) => {
              const enabled = sources[option.key];
              const keyMissing =
                (option.needsKey === "google" && !googleConfigured) ||
                (option.needsKey === "yelp" && !yelpConfigured) ||
                (option.needsKey === "apollo" && !apolloConfigured) ||
                (option.needsKey === "serpapi" && !serpapiConfigured) ||
                (option.needsKey === "scrapingbee" && !scrapingbeeConfigured);

              return (
                <SourceToggle
                  key={option.key}
                  label={option.label}
                  hint={keyMissing ? "Key not set · skipped until configured" : option.hint}
                  checked={enabled}
                  warning={keyMissing && enabled}
                  onToggle={() => {
                    toggleSource(option.key);
                  }}
                />
              );
            })}
          </div>
        </section>

        {error ? (
          <p className="rounded-control bg-red-50 px-3 py-2 text-body text-danger" role="alert">
            {error}
          </p>
        ) : null}

        <div className="flex flex-col gap-3 border-t border-gray-100 pt-5 lg:flex-row lg:items-center lg:justify-between">
          <p className="text-small text-gray-600">
            Save for the daily schedule, or run immediately across all selected niches.
          </p>
          <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="secondary"
              className="w-full sm:w-auto"
              disabled={createBatch.isPending || running || selectedCategories.length === 0}
              onClick={() => {
                save(false);
              }}
            >
              Save for daily run ({selectedCategories.length})
            </Button>
            <Button
              type="submit"
              className="w-full sm:w-auto"
              isLoading={createBatch.isPending || run.isPending || running}
              disabled={selectedCategories.length === 0}
            >
              <Search className="size-4" aria-hidden="true" />
              {selectedCategories.length > 1
                ? `Save & search now (${selectedCategories.length} niches)`
                : "Save and search now"}
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <h3 className="text-caption font-semibold uppercase tracking-wide text-gray-500">{children}</h3>
  );
}

function SourceToggle({
  label,
  hint,
  checked,
  warning,
  onToggle,
}: {
  label: string;
  hint: string;
  checked: boolean;
  warning?: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={checked}
      className={cn(
        "rounded-card border px-3 py-3 text-left transition-colors duration-150",
        focusRing,
        checked
          ? warning
            ? "border-amber-300 bg-amber-50"
            : "border-primary-300 bg-primary-50"
          : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-body font-semibold text-ink">{label}</span>
        <span
          className={cn(
            "mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full border",
            checked
              ? warning
                ? "border-amber-500 bg-amber-500 text-white"
                : "border-primary bg-primary text-white"
              : "border-gray-300 bg-white",
          )}
          aria-hidden="true"
        >
          {checked ? <CheckCircle2 className="size-3" /> : null}
        </span>
      </div>
      <p className={cn("mt-1 text-caption", warning ? "text-amber-800" : "text-gray-500")}>
        {hint}
      </p>
    </button>
  );
}

function SearchList({ searches, running }: { searches: DiscoverySearch[]; running: boolean }) {
  if (searches.length === 0) {
    return (
      <EmptyState
        title="No saved searches yet"
        description="Add a category above. Active searches run once a day while the API is online, and you can run any search immediately."
      />
    );
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-h3 font-semibold text-ink">Saved searches</h2>
          <p className="mt-1 text-body text-gray-600">
            Pause, resume, or run a search anytime. Latest results stay on each search.
          </p>
        </div>
        <p className="text-caption font-medium text-gray-500">
          {searches.length} search{searches.length === 1 ? "" : "es"}
        </p>
      </div>
      <div className="space-y-3">
        {searches.map((search) => (
          <SearchRow key={search.id} search={search} running={running} />
        ))}
      </div>
    </section>
  );
}

function SearchRow({ search, running }: { search: DiscoverySearch; running: boolean }) {
  const update = useUpdateDiscoverySearch();
  const remove = useDeleteDiscoverySearch();
  const run = useRunDiscovery();
  const { notify } = useToast();
  const [confirming, setConfirming] = useState(false);
  const label = search.category.replaceAll("_", " ");
  const sourceChips = enabledSources(search);
  const failed = Boolean(
    search.last_message &&
      /could not|unavailable|stopped|rejected|skipped because|no map area/i.test(
        search.last_message,
      ),
  );

  return (
    <Card className="min-w-0 overflow-hidden p-0">
      <div className="flex min-w-0 flex-col gap-4 p-4 sm:flex-row sm:items-start sm:justify-between sm:p-5">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-h4 font-semibold break-words text-ink capitalize">
              {search.city.toLowerCase() === "anywhere" ? label : `${label} in ${search.city}`}
            </h3>
            <Badge tone={search.is_active ? "green" : "gray"}>
              {search.is_active ? "Daily" : "Paused"}
            </Badge>
            {search.last_status ? (
              <Badge tone={failed ? "orange" : "indigo"}>{statusLabel(search.last_status)}</Badge>
            ) : null}
          </div>

          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-body text-gray-600">
            <span className="inline-flex items-center gap-1.5">
              <MapPin className="size-3.5 shrink-0 text-gray-400" aria-hidden="true" />
              {search.city.toLowerCase() === "anywhere" ? "Multiple cities" : search.country}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Clock3 className="size-3.5 shrink-0 text-gray-400" aria-hidden="true" />
              {search.last_finished_at
                ? `Last run ${formatWhen(search.last_finished_at)}`
                : "Not run yet"}
            </span>
          </p>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {sourceChips.map((name) => (
              <span
                key={name}
                className="rounded-control bg-gray-100 px-2 py-0.5 text-caption font-medium text-gray-700"
              >
                {name}
              </span>
            ))}
          </div>

          {search.last_message ? (
            <SearchMessage failed={failed} message={search.last_message} />
          ) : null}
        </div>

        <div className="grid w-full shrink-0 grid-cols-2 gap-2 sm:w-auto sm:min-w-56">
          <Metric label="Found" value={search.last_found_count} />
          <Metric label="New" value={search.last_created_count} />
          <Metric label="Updated" value={search.last_updated_count} />
          <Metric label="Skipped" value={search.last_skipped_count} />
        </div>
      </div>

      <div className="flex flex-col gap-2 border-t border-gray-100 bg-gray-50/80 px-4 py-3 sm:flex-row sm:flex-wrap sm:px-5">
        <Button
          variant="secondary"
          className="w-full sm:w-auto"
          isLoading={run.isPending}
          disabled={running}
          onClick={() => {
            run.mutate(search.id, {
              onError: (error) => {
                notify(apiErrorMessage(error, "The search could not start."), "danger");
              },
            });
          }}
        >
          <Play className="size-4" aria-hidden="true" />
          Run now
        </Button>
        <Button
          variant="ghost"
          className="w-full sm:w-auto"
          disabled={update.isPending || running}
          onClick={() => {
            update.mutate(
              { id: search.id, isActive: !search.is_active },
              {
                onError: (error) => {
                  notify(apiErrorMessage(error, "The search could not be updated."), "danger");
                },
              },
            );
          }}
        >
          {search.is_active ? (
            <>
              <PauseCircle className="size-4" aria-hidden="true" />
              Pause daily
            </>
          ) : (
            <>
              <CalendarClock className="size-4" aria-hidden="true" />
              Resume daily
            </>
          )}
        </Button>
        <Button
          variant="ghost"
          className="w-full text-danger hover:bg-red-50 sm:w-auto"
          disabled={running}
          onClick={() => {
            setConfirming(true);
          }}
        >
          <Trash2 className="size-4" aria-hidden="true" />
          Remove
        </Button>
      </div>
      <ConfirmDialog
        open={confirming}
        title="Remove this search?"
        description="Leads already saved will stay."
        confirmLabel="Remove search"
        isLoading={remove.isPending}
        onConfirm={() => {
          remove.mutate(search.id, {
            onSuccess: () => {
              setConfirming(false);
            },
            onError: (error) => {
              notify(apiErrorMessage(error, "The search could not be removed."), "danger");
            },
          });
        }}
        onClose={() => {
          if (!remove.isPending) {
            setConfirming(false);
          }
        }}
      />
    </Card>
  );
}

function SearchMessage({ failed, message }: { failed: boolean; message: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = message.length > 160;
  const shown = !long || expanded ? message : `${message.slice(0, 157).trimEnd()}…`;

  return (
    <div
      className={cn(
        "mt-3 rounded-control px-3 py-2 text-small",
        failed ? "bg-amber-50 text-amber-900" : "bg-gray-50 text-gray-700",
      )}
    >
      <p>{shown}</p>
      {long ? (
        <button
          type="button"
          className={cn(
            "mt-1 font-semibold underline-offset-2 hover:underline",
            failed ? "text-amber-950" : "text-gray-800",
            focusRing,
          )}
          onClick={() => {
            setExpanded((current) => !current);
          }}
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-control border border-gray-200 bg-white px-3 py-2 text-center">
      <p className="text-caption font-medium text-gray-500">{label}</p>
      <p className="mt-0.5 text-h4 font-semibold tabular-nums text-ink">
        {value === null ? "—" : value}
      </p>
    </div>
  );
}

function FoundLeads({
  leads,
  total,
  pending,
}: {
  leads: Lead[];
  total: number;
  pending: boolean;
}) {
  if (pending && leads.length === 0) {
    return null;
  }

  if (leads.length === 0) {
    return (
      <section className="space-y-3">
        <h2 className="text-h3 font-semibold text-ink">Ready to pitch</h2>
        <EmptyState
          title="No discovered leads yet"
          description="Run a search to pull businesses from public listings. High-scoring leads without websites appear here first."
        />
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-h3 font-semibold text-ink">Ready to pitch</h2>
          <p className="mt-1 text-body text-gray-600">
            Newest discovered businesses. Open a lead to audit, mock up, or send outreach.
          </p>
        </div>
        <Link
          to="/leads"
          className={cn(
            "inline-flex h-10 items-center rounded-control px-3 text-body font-semibold text-primary-700 hover:bg-primary-50",
            focusRing,
          )}
        >
          View all {total > leads.length ? `(${total})` : ""}
        </Link>
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-3 md:grid-cols-2">
        {leads.map((lead) => (
          <FoundLead key={lead.id} lead={lead} />
        ))}
      </div>
    </section>
  );
}

function FoundLead({ lead }: { lead: Lead }) {
  const website = websiteLabels[lead.website_status ?? ""] ?? {
    label: "Website unknown",
    tone: "gray" as const,
  };
  const scoreTone = scoreBadgeTone(lead.lead_score);
  const location = [lead.industry, lead.city, lead.country].filter(Boolean).join(" · ");

  return (
    <Card className="flex h-full min-w-0 w-full flex-col overflow-hidden p-0 transition-shadow duration-150 hover:shadow-md">
      <div className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-h4 font-semibold text-ink">{lead.business_name}</h3>
            {location ? (
              <p className="mt-1 flex items-center gap-1.5 text-small text-gray-600">
                <MapPin className="size-3.5 shrink-0 text-gray-400" aria-hidden="true" />
                <span className="truncate">{location}</span>
              </p>
            ) : null}
          </div>
          <ScorePill score={lead.lead_score} tone={scoreTone} />
        </div>

        <div className="flex flex-wrap gap-1.5">
          <Badge tone={website.tone}>{website.label}</Badge>
          {lead.source ? <Badge tone="indigo">{prettySource(lead.source)}</Badge> : null}
        </div>

        {lead.description ? (
          <p className="line-clamp-3 min-w-0 text-small break-words text-gray-600">{lead.description}</p>
        ) : null}

        <div className="mt-auto space-y-1.5 border-t border-gray-100 pt-3 text-small text-gray-600">
          <p className="flex items-center gap-1.5">
            <Phone className="size-3.5 shrink-0 text-gray-400" aria-hidden="true" />
            {lead.phone ? (
              <a
                href={`tel:${lead.phone.replace(/\s+/g, "")}`}
                className={cn("hover:text-ink", focusRing)}
              >
                {lead.phone}
              </a>
            ) : (
              <span className="text-gray-400">No phone listed</span>
            )}
          </p>
          <p className="flex items-center gap-1.5">
            <Globe2 className="size-3.5 shrink-0 text-gray-400" aria-hidden="true" />
            {lead.website_url ? (
              <a
                href={lead.website_url}
                target="_blank"
                rel="noreferrer"
                className={cn("truncate hover:text-ink", focusRing)}
              >
                {hostname(lead.website_url)}
              </a>
            ) : (
              <span className="text-gray-400">No website URL</span>
            )}
          </p>
        </div>
      </div>

      <div className="border-t border-gray-100 bg-gray-50/80 px-5 py-3">
        <Link
          to={`/leads/${lead.id}`}
          className={cn(
            "inline-flex h-10 w-full items-center justify-center rounded-control bg-white text-body font-semibold text-primary-700 shadow-sm ring-1 ring-gray-200 transition-colors hover:bg-primary-50",
            focusRing,
          )}
        >
          Open lead
        </Link>
      </div>
    </Card>
  );
}

function ScorePill({
  score,
  tone,
}: {
  score: number | null;
  tone: "green" | "orange" | "gray" | "indigo";
}) {
  if (score === null) {
    return <Badge tone="gray">No score</Badge>;
  }

  return (
    <span
      className={cn(
        "inline-flex shrink-0 flex-col items-center rounded-control px-2.5 py-1",
        tone === "green" && "bg-emerald-50 text-emerald-800",
        tone === "orange" && "bg-amber-50 text-amber-800",
        tone === "indigo" && "bg-primary-50 text-primary-700",
        tone === "gray" && "bg-gray-100 text-gray-700",
      )}
      title="Lead score"
    >
      <span className="text-[10px] font-semibold uppercase tracking-wide opacity-70">Score</span>
      <span className="text-h4 font-bold tabular-nums leading-none">{score}</span>
    </span>
  );
}

function ScheduleCard({
  schedule,
  nextRunAt,
  running,
  googleConfigured,
  yelpConfigured,
  apolloConfigured,
  serpapiConfigured,
  scrapingbeeConfigured,
  latestMessage,
}: {
  schedule: string;
  nextRunAt: string | null;
  running: boolean;
  googleConfigured: boolean;
  yelpConfigured: boolean;
  apolloConfigured: boolean;
  serpapiConfigured: boolean;
  scrapingbeeConfigured: boolean;
  latestMessage: string | null;
}) {
  const { notify } = useToast();
  useRunCompletion(running, latestMessage, notify);

  return (
    <Card className="p-0">
      <div className="border-b border-gray-100 px-5 py-4">
        <h2 className="text-h4 font-semibold text-ink">Schedule & sources</h2>
        <p className="mt-1 text-small text-gray-600">
          Daily discovery runs while the API is online.
        </p>
      </div>

      <dl className="space-y-4 px-5 py-4">
        <div>
          <dt className="text-caption font-semibold uppercase tracking-wide text-gray-500">
            Automatic run
          </dt>
          <dd className="mt-1 text-body text-ink">{schedule}</dd>
        </div>
        <div>
          <dt className="text-caption font-semibold uppercase tracking-wide text-gray-500">
            Next run
          </dt>
          <dd className="mt-1 flex items-center gap-2 text-body text-ink">
            {running ? (
              <>
                <span className="size-2 animate-pulse rounded-full bg-primary" aria-hidden="true" />
                Running now
              </>
            ) : (
              formatWhen(nextRunAt)
            )}
          </dd>
        </div>
      </dl>

      <div className="space-y-2 border-t border-gray-100 px-5 py-4">
        <p className="text-caption font-semibold uppercase tracking-wide text-gray-500">
          API keys
        </p>
        <SourceStatus
          name="Apollo.io"
          ready={apolloConfigured}
          detail={apolloConfigured ? "Key configured" : "Set APOLLO_API_KEY"}
        />
        <SourceStatus
          name="SerpApi"
          ready={serpapiConfigured}
          detail={serpapiConfigured ? "Key configured" : "Set SERPAPI_API_KEY"}
        />
        <SourceStatus
          name="ScrapingBee"
          ready={scrapingbeeConfigured}
          detail={scrapingbeeConfigured ? "Key configured" : "Set SCRAPINGBEE_API_KEY"}
        />
        <SourceStatus
          name="Google Places"
          ready={googleConfigured}
          detail={googleConfigured ? "Key configured" : "Set GOOGLE_PLACES_API_KEY"}
        />
        <SourceStatus
          name="Yelp"
          ready={yelpConfigured}
          detail={yelpConfigured ? "Key configured" : "Set YELP_API_KEY"}
        />
        <SourceStatus name="OpenStreetMap" ready detail="No key required" />
        <SourceStatus name="Yell · BusinessList · ePages" ready detail="Public scrapers" />
      </div>

      <p className="border-t border-gray-100 px-5 py-4 text-caption text-gray-500">
        A run that already finished today is not repeated until the next day. You can still run any
        single search manually.
      </p>
    </Card>
  );
}

function SourceStatus({
  name,
  ready,
  detail,
}: {
  name: string;
  ready: boolean;
  detail: string;
}) {
  return (
    <div className="flex flex-wrap items-start gap-2.5 rounded-control bg-gray-50 px-3 py-2.5">
      {ready ? (
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden="true" />
      ) : (
        <KeyRound className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden="true" />
      )}
      <div className="min-w-0">
        <p className="text-small font-semibold text-ink">{name}</p>
        <p className="text-caption text-gray-500">{detail}</p>
      </div>
      <span className="sm:ml-auto">
        <Badge tone={ready ? "green" : "orange"}>{ready ? "Ready" : "Needs key"}</Badge>
      </span>
    </div>
  );
}

function HowItWorksCard() {
  const steps = [
    {
      title: "Pick a category",
      body: "Directories are checked across the cities they cover. Limit a search only when you want one place.",
    },
    {
      title: "Review matches",
      body: "Businesses without websites score higher. Open any lead for contact details.",
    },
    {
      title: "Pitch with context",
      body: "Run an audit or mockup from the lead page, then send outreach.",
    },
  ];

  return (
    <Card className="p-0">
      <div className="flex items-center gap-2 border-b border-gray-100 px-5 py-4">
        <Sparkles className="size-4 text-primary-600" aria-hidden="true" />
        <h2 className="text-h4 font-semibold text-ink">How discovery works</h2>
      </div>
      <ol className="space-y-4 px-5 py-4">
        {steps.map((step, index) => (
          <li key={step.title} className="flex gap-3">
            <span className="inline-flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-50 text-caption font-bold text-primary-700">
              {index + 1}
            </span>
            <div>
              <p className="text-body font-semibold text-ink">{step.title}</p>
              <p className="mt-0.5 text-small text-gray-600">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function enabledSources(search: DiscoverySearch): string[] {
  return SOURCE_OPTIONS.filter((option) => search[option.key]).map((option) => option.label);
}

function statusLabel(status: string): string {
  return status
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function scoreBadgeTone(score: number | null): "green" | "orange" | "gray" | "indigo" {
  if (score === null) {
    return "gray";
  }
  if (score >= 70) {
    return "green";
  }
  if (score >= 45) {
    return "indigo";
  }
  return "orange";
}

function prettySource(value: string): string {
  const labels: Record<string, string> = {
    openstreetmap: "OpenStreetMap",
    google_places: "Google Places",
    yelp: "Yelp",
    yell: "Yell",
    businesslist: "BusinessList",
    epages: "ePages",
  };
  return (
    labels[value] ??
    value
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
  );
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.replace(/^https?:\/\//, "");
  }
}

function shortWhen(value: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function useRunCompletion(
  running: boolean,
  latestMessage: string | null,
  notify: (message: string, tone?: "info" | "success" | "danger") => void,
) {
  const wasRunning = useRef(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (running) {
      wasRunning.current = true;
      return;
    }
    if (!wasRunning.current) {
      return;
    }
    wasRunning.current = false;
    void queryClient.invalidateQueries({ queryKey: ["leads"] });
    if (!latestMessage) {
      return;
    }
    const failed = /could not|unavailable|stopped|rejected|skipped because/i.test(latestMessage);
    const message = latestMessage.length > 240 ? `${latestMessage.slice(0, 237)}…` : latestMessage;
    notify(message, failed ? "danger" : "success");
  }, [latestMessage, notify, queryClient, running]);
}
