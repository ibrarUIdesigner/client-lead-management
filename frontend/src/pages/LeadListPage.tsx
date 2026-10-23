import { ChevronDown, Compass, ExternalLink, Flame, Globe, Images, Mail, MapPin, Sparkles, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { DataTable, type DataColumn } from "../components/data/DataTable";
import { StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { leadStatusOptions } from "../features/leads/statuses";
import { useBulkDeleteLeads, useBulkUpdateLeads, useDeleteLead, useLeads } from "../hooks/useLeads";
import { apiErrorMessage } from "../lib/apiError";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import { getNextBestAction } from "../lib/leadWorkflow";
import type { Lead, LeadListParams } from "../types/lead";

type Filters = {
  q: string;
  lead_status: string;
  has_email: string;
  industry: string;
  city: string;
  country: string;
  source: string;
  tag: string;
  website_status: string;
  min_score: string;
  sort: string;
};

const defaultFilters: Filters = {
  q: "",
  lead_status: "",
  has_email: "true",
  industry: "",
  city: "",
  country: "",
  source: "",
  tag: "",
  website_status: "",
  min_score: "",
  sort: "lead_score:desc",
};

const emailStatusOptions = [
  { value: "true", label: "Has email" },
  { value: "", label: "Any (all leads)" },
  { value: "false", label: "No email" },
];

const sortOptions = [
  { value: "lead_score:desc", label: "Highest score" },
  { value: "created_at:desc", label: "Newest" },
  { value: "created_at:asc", label: "Oldest" },
  { value: "business_name:asc", label: "Name" },
  { value: "updated_at:desc", label: "Recently updated" },
];

const websiteStatusOptions = [
  { value: "present", label: "Has a website" },
  { value: "missing", label: "No website" },
  { value: "social_only", label: "Social only" },
  { value: "pending", label: "Audit pending" },
  { value: "analyzed", label: "Audited" },
  { value: "failed", label: "Audit failed" },
];

const extraFilterKeys = [
  "industry",
  "city",
  "country",
  "source",
  "tag",
  "website_status",
  "min_score",
] as const satisfies readonly (keyof Filters)[];

function extraFilterCount(filters: Filters): number {
  return extraFilterKeys.filter((key) => filters[key] !== "").length;
}

function websiteLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.replace(/^https?:\/\//, "");
  }
}

function filtersAreActive(filters: Filters): boolean {
  return (Object.keys(defaultFilters) as (keyof Filters)[]).some(
    (key) => key !== "sort" && filters[key] !== defaultFilters[key],
  );
}

function toParams(filters: Filters, page: number): LeadListParams {
  const [sort, direction] = filters.sort.split(":");
  const score = Number(filters.min_score);
  return {
    page,
    limit: 25,
    q: filters.q,
    lead_status: filters.lead_status,
    has_email: filters.has_email === "true" ? true : filters.has_email === "false" ? false : undefined,
    industry: filters.industry,
    city: filters.city,
    country: filters.country,
    source: filters.source,
    tag: filters.tag,
    website_status: filters.website_status,
    min_score: filters.min_score !== "" && Number.isFinite(score) ? score : undefined,
    sort,
    direction: direction === "asc" ? "asc" : "desc",
  };
}

// Filter pill definitions
type QuickFilterPill = {
  id: string;
  label: string;
  statusMatch?: string;
  minScoreMatch?: string;
  icon?: any;
};

const filterPills: QuickFilterPill[] = [
  { id: "all", label: "All" },
  { id: "hot", label: "Hot", minScoreMatch: "70", icon: Flame },
  { id: "new", label: "New", statusMatch: "NEW" },
  { id: "audited", label: "Audited", statusMatch: "AUDIT_COMPLETE" },
  { id: "mockup_ready", label: "Mockup Ready", statusMatch: "MOCKUP_READY" },
  { id: "contacted", label: "Contacted", statusMatch: "CONTACTED" },
  { id: "replied", label: "Replied", statusMatch: "REPLIED" },
  { id: "won", label: "Won", statusMatch: "WON" },
  { id: "lost", label: "Lost", statusMatch: "LOST" },
];

export function LeadListPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { notify } = useToast();

  const [draft, setDraft] = useState<Filters>(() => {
    const statusParam = searchParams.get("lead_status");
    const minScoreParam = searchParams.get("min_score");
    return {
      ...defaultFilters,
      lead_status: statusParam || defaultFilters.lead_status,
      min_score: minScoreParam || defaultFilters.min_score,
    };
  });

  const [applied, setApplied] = useState<Filters>(draft);
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkStatus, setBulkStatus] = useState("");
  const [bulkTag, setBulkTag] = useState("");
  const leads = useLeads(toParams(applied, page));
  const bulkUpdate = useBulkUpdateLeads();
  const bulkDelete = useBulkDeleteLeads();
  const deleteLead = useDeleteLead();
  const [leadToDelete, setLeadToDelete] = useState<{ id: string; name: string } | null>(null);
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);

  const handleDeleteLead = () => {
    if (!leadToDelete) return;
    deleteLead.mutate(leadToDelete.id, {
      onSuccess: () => {
        notify("Lead deleted successfully.", "success");
        setLeadToDelete(null);
        setSelected((curr) => {
          const next = new Set(curr);
          next.delete(leadToDelete.id);
          return next;
        });
      },
      onError: (err) => {
        notify(apiErrorMessage(err, "Failed to delete lead."), "danger");
      },
    });
  };

  const handleBulkDelete = () => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    bulkDelete.mutate(ids, {
      onSuccess: (deletedCount) => {
        notify(`Deleted ${deletedCount} leads.`, "success");
        setSelected(new Set());
        setConfirmBulkDelete(false);
      },
      onError: (err) => {
        notify(apiErrorMessage(err, "Failed to delete leads."), "danger");
      },
    });
  };
  const rows = leads.data?.items ?? [];
  const pageCount = leads.data ? Math.max(1, Math.ceil(leads.data.total / leads.data.limit)) : 1;
  const hasFilters = filtersAreActive(applied);
  const pageSelected = rows.length > 0 && rows.every((row) => selected.has(row.id));

  // Sync when URL query params change
  const [prevParamsString, setPrevParamsString] = useState(() => searchParams.toString());
  const currentParamsString = searchParams.toString();
  if (currentParamsString !== prevParamsString) {
    setPrevParamsString(currentParamsString);
    const statusParam = searchParams.get("lead_status") || "";
    const minScoreParam = searchParams.get("min_score") || "";
    if (searchParams.has("lead_status") || searchParams.has("min_score")) {
      setDraft((prev) => ({ ...prev, lead_status: statusParam, min_score: minScoreParam }));
      setApplied((prev) => ({ ...prev, lead_status: statusParam, min_score: minScoreParam }));
      setPage(1);
    }
  }

  const updateDraft = (key: keyof Filters, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const applyFilters = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
    setSelected(new Set());
    setApplied(draft);
  };

  const clearFilters = () => {
    setDraft(defaultFilters);
    setApplied(defaultFilters);
    setShowMoreFilters(false);
    setPage(1);
    setSelected(new Set());
  };

  const handleSelectPill = (pill: QuickFilterPill) => {
    const next: Filters = {
      ...draft,
      lead_status: pill.statusMatch ?? "",
      min_score: pill.minScoreMatch ?? "",
    };
    setDraft(next);
    setApplied(next);
    setPage(1);
    setSelected(new Set());
  };

  const isPillActive = (pill: QuickFilterPill) => {
    if (pill.id === "all") {
      return !applied.lead_status && !applied.min_score;
    }
    if (pill.minScoreMatch) {
      return applied.min_score === pill.minScoreMatch && !applied.lead_status;
    }
    return applied.lead_status === pill.statusMatch;
  };

  const toggle = (id: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const togglePage = () => {
    setSelected((current) => {
      const next = new Set(current);
      if (pageSelected) {
        for (const row of rows) {
          next.delete(row.id);
        }
      } else {
        for (const row of rows) {
          next.add(row.id);
        }
      }
      return next;
    });
  };

  const applyBulk = () => {
    const ids = Array.from(selected);
    if (ids.length === 0) {
      return;
    }
    const tags = bulkTag.trim() ? [bulkTag.trim()] : undefined;
    bulkUpdate.mutate(
      {
        ids,
        lead_status: bulkStatus || undefined,
        add_tags: tags,
      },
      {
        onSuccess: (result) => {
          notify(`Updated ${result.items.length} ${result.items.length === 1 ? "lead" : "leads"}.`, "success");
          setSelected(new Set());
          setBulkStatus("");
          setBulkTag("");
        },
        onError: (error) => {
          notify(apiErrorMessage(error, "Could not update the selected leads."), "danger");
        },
      },
    );
  };

  const extraCount = extraFilterCount(draft);

  const columns: DataColumn<Lead>[] = [
    {
      id: "select",
      header: "Select",
      cell: (row) => (
        <label className="inline-flex size-11 items-center justify-center">
          <input
            type="checkbox"
            className={cn("size-4 accent-primary", focusRing)}
            aria-label={`Select ${row.business_name}`}
            checked={selected.has(row.id)}
            onChange={() => {
              toggle(row.id);
            }}
          />
        </label>
      ),
    },
    {
      id: "business",
      header: "Business",
      cell: (row) => (
        <div className="flex max-w-72 flex-col gap-1 py-1">
          <div className="flex items-center gap-1.5">
            <Link
              to={`/leads/${row.id}`}
              className={cn("font-bold text-ink hover:text-primary-700", focusRing)}
            >
              {row.business_name}
            </Link>
            {row.email_unread ? (
              <span className="size-2 rounded-full bg-orange-500 shrink-0" title="Unread reply" />
            ) : null}
          </div>
          {row.city || row.country ? (
            <span className="text-caption text-gray-500 flex items-center gap-1">
              <MapPin className="size-3" />
              {[row.city, row.country].filter(Boolean).join(", ")}
            </span>
          ) : null}
          {row.tags.length > 0 ? (
            <span className="flex flex-wrap gap-1 mt-0.5">
              {row.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center rounded bg-gray-100 px-1.5 py-0.2 text-[10px] font-medium text-gray-600"
                >
                  {tag}
                </span>
              ))}
            </span>
          ) : null}
        </div>
      ),
    },
    {
      id: "industry",
      header: "Industry",
      cell: (row) => <span className="text-small text-gray-700">{row.industry || "—"}</span>,
    },
    {
      id: "opportunity",
      header: "Opportunity",
      cell: (row) => {
        const score = row.lead_score;
        if (score === null || score === undefined) {
          return <span className="text-caption text-gray-400">Pending</span>;
        }
        const isHot = score >= 70;
        const isMedium = score >= 45;

        return (
          <div className="flex flex-col gap-0.5" title="AI / heuristic opportunity score">
            <span
              className={cn(
                "inline-flex w-fit items-center gap-1 rounded-full px-2 py-0.5 text-caption font-bold tabular-nums",
                isHot
                  ? "bg-orange-50 text-orange-700 ring-1 ring-orange-200"
                  : isMedium
                  ? "bg-blue-50 text-blue-700"
                  : "bg-gray-100 text-gray-600",
              )}
            >
              {isHot ? <Flame className="size-3 text-orange-600" /> : null}
              {score} / 100
            </span>
            <span className="text-[10px] text-gray-400">
              {row.website_url ? (row.website_quality_score ? `Quality ${row.website_quality_score}` : "Poor Web") : "No Website"}
            </span>
          </div>
        );
      },
    },
    {
      id: "website",
      header: "Website",
      cell: (row) =>
        row.website_url ? (
          <div className="flex items-center gap-1.5 max-w-44">
            <a
              href={row.website_url}
              target="_blank"
              rel="noreferrer"
              title={row.website_url}
              className={cn("truncate text-small text-primary-700 hover:underline", focusRing)}
            >
              {websiteLabel(row.website_url)}
            </a>
            <ExternalLink className="size-3 text-gray-400 shrink-0" />
          </div>
        ) : (
          <span className="inline-flex items-center rounded bg-amber-50 px-2 py-0.5 text-caption font-medium text-amber-800">
            No Website
          </span>
        ),
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusBadge status={row.lead_status} />,
    },
    {
      id: "activity",
      header: "Last Activity",
      cell: (row) => {
        const time = row.last_replied_at || row.last_contacted_at || row.updated_at || row.created_at;
        return (
          <div className="text-caption text-gray-500 whitespace-nowrap">
            {row.last_replied_at ? "Replied " : row.last_contacted_at ? "Contacted " : "Updated "}
            {formatWhen(time)}
          </div>
        );
      },
    },
    {
      id: "nextAction",
      header: "Next Best Action",
      cell: (row) => {
        const nba = getNextBestAction(row);
        return (
          <Button
            variant={nba.priority === "critical" || nba.priority === "high" ? "primary" : "secondary"}
            className="h-7 px-2.5 text-caption font-medium whitespace-nowrap shadow-2xs"
            onClick={() => navigate(`/leads/${row.id}?tab=${nba.targetTab}`)}
          >
            {nba.action} →
          </Button>
        );
      },
    },
    {
      id: "quickActions",
      header: "Actions",
      cell: (row) => (
        <div className="flex items-center gap-1">
          <button
            type="button"
            title="Website Audit"
            aria-label="Website Audit"
            onClick={() => navigate(`/leads/${row.id}?tab=audit`)}
            className="flex size-7.5 items-center justify-center rounded-md border border-transparent text-gray-400 hover:border-gray-200 hover:bg-gray-50 hover:text-primary-700 transition-all cursor-pointer"
          >
            <Globe className="size-3.5" />
          </button>
          <button
            type="button"
            title="Lead Research"
            aria-label="Lead Research"
            onClick={() => navigate(`/leads/${row.id}?tab=research`)}
            className="flex size-7.5 items-center justify-center rounded-md border border-transparent text-gray-400 hover:border-gray-200 hover:bg-gray-50 hover:text-primary-700 transition-all cursor-pointer"
          >
            <Sparkles className="size-3.5" />
          </button>
          <button
            type="button"
            title="Homepage Mockup"
            aria-label="Homepage Mockup"
            onClick={() => navigate(`/leads/${row.id}?tab=mockups`)}
            className="flex size-7.5 items-center justify-center rounded-md border border-transparent text-gray-400 hover:border-gray-200 hover:bg-gray-50 hover:text-primary-700 transition-all cursor-pointer"
          >
            <Images className="size-3.5" />
          </button>
          <button
            type="button"
            title="Outreach Draft"
            aria-label="Outreach Draft"
            onClick={() => navigate(`/leads/${row.id}?tab=outreach`)}
            className="flex size-7.5 items-center justify-center rounded-md border border-transparent text-gray-400 hover:border-gray-200 hover:bg-gray-50 hover:text-primary-700 transition-all cursor-pointer"
          >
            <Mail className="size-3.5" />
          </button>
          <button
            type="button"
            title="Delete Lead"
            aria-label="Delete Lead"
            onClick={() => setLeadToDelete({ id: row.id, name: row.business_name })}
            className="flex size-7.5 items-center justify-center rounded-md border border-transparent text-gray-400 hover:border-red-200 hover:bg-red-50 hover:text-danger transition-all cursor-pointer"
          >
            <Trash2 className="size-3.5" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Leads"
        description="Prospects and businesses you want to qualify, audit, pitch, and convert."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                navigate("/discover");
              }}
            >
              <Compass className="size-4" />
              <span>Find Leads</span>
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                navigate("/leads/import");
              }}
            >
              Import CSV
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                navigate("/leads/new");
              }}
            >
              Add Lead
            </Button>
          </div>
        }
      />

      {/* Quick Filter Pills Row (Section 8) */}
      <div className="mb-4 flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
        {filterPills.map((pill) => {
          const active = isPillActive(pill);
          const Icon = pill.icon;
          return (
            <button
              key={pill.id}
              type="button"
              onClick={() => handleSelectPill(pill)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-3.5 py-1 text-caption font-semibold transition-all shrink-0 cursor-pointer shadow-2xs",
                focusRing,
                active
                  ? "bg-primary text-white"
                  : "bg-white border border-gray-200/90 text-gray-600 hover:bg-gray-50 hover:text-ink",
              )}
            >
              {Icon ? <Icon className={cn("size-3.5", active ? "text-white" : "text-orange-500")} /> : null}
              <span>{pill.label}</span>
            </button>
          );
        })}
      </div>

      {/* Search and Secondary Filter Bar */}
      <form
        className="mb-4 rounded-card border border-gray-200/85 bg-white p-4 shadow-2xs"
        onSubmit={applyFilters}
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="min-w-0 lg:w-80 lg:shrink-0">
            <Input
              label="Search leads"
              placeholder="Search business, website, city..."
              value={draft.q}
              onChange={(event) => {
                updateDraft("q", event.target.value);
              }}
            />
          </div>
          <div className="grid flex-1 grid-cols-1 gap-3 min-[480px]:grid-cols-3 sm:max-w-xl">
            <Select
              label="Status"
              placeholder="Any status"
              options={leadStatusOptions}
              value={draft.lead_status}
              onChange={(event) => {
                updateDraft("lead_status", event.target.value);
              }}
            />
            <Select
              label="Email"
              options={emailStatusOptions}
              value={draft.has_email}
              onChange={(event) => {
                updateDraft("has_email", event.target.value);
              }}
            />
            <Select
              label="Sort"
              options={sortOptions}
              value={draft.sort}
              onChange={(event) => {
                updateDraft("sort", event.target.value);
              }}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" size="default" className="px-5">
              Apply
            </Button>
            {hasFilters || filtersAreActive(draft) ? (
              <Button variant="secondary" size="default" onClick={clearFilters}>
                Clear
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="default"
              aria-expanded={showMoreFilters}
              aria-controls="lead-extra-filters"
              onClick={() => {
                setShowMoreFilters((open) => !open);
              }}
            >
              {extraCount > 0 ? `More filters (${extraCount})` : "More filters"}
              <ChevronDown
                className={cn("size-4 transition-transform", showMoreFilters && "rotate-180")}
                aria-hidden="true"
              />
            </Button>
          </div>
        </div>
        {showMoreFilters ? (
          <div id="lead-extra-filters" className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Input
              label="Industry"
              value={draft.industry}
              onChange={(event) => {
                updateDraft("industry", event.target.value);
              }}
            />
            <Input
              label="City"
              value={draft.city}
              onChange={(event) => {
                updateDraft("city", event.target.value);
              }}
            />
            <Input
              label="Country"
              value={draft.country}
              onChange={(event) => {
                updateDraft("country", event.target.value);
              }}
            />
            <Input
              label="Source"
              value={draft.source}
              onChange={(event) => {
                updateDraft("source", event.target.value);
              }}
            />
            <Input
              label="Tag"
              value={draft.tag}
              onChange={(event) => {
                updateDraft("tag", event.target.value);
              }}
            />
            <Select
              label="Website"
              placeholder="Any website"
              options={websiteStatusOptions}
              value={draft.website_status}
              onChange={(event) => {
                updateDraft("website_status", event.target.value);
              }}
            />
            <Input
              label="Minimum score"
              type="number"
              min={0}
              max={100}
              value={draft.min_score}
              onChange={(event) => {
                updateDraft("min_score", event.target.value);
              }}
            />
          </div>
        ) : null}
      </form>

      {selected.size > 0 ? (
        <div className="mb-6 flex flex-col md:flex-row md:items-end gap-3 rounded-card border border-primary-200 bg-primary-50/30 p-4 shadow-sm ring-1 ring-primary-500/10">
          <div className="flex-1">
            <Select
              label="Set status"
              placeholder="Keep current status"
              options={leadStatusOptions}
              value={bulkStatus}
              onChange={(event) => {
                setBulkStatus(event.target.value);
              }}
            />
          </div>
          <div className="flex-1">
            <Input
              label="Add tag"
              value={bulkTag}
              onChange={(event) => {
                setBulkTag(event.target.value);
              }}
            />
          </div>
          <Button
            size="default"
            className="whitespace-nowrap"
            onClick={applyBulk}
            isLoading={bulkUpdate.isPending}
            disabled={!bulkStatus && bulkTag.trim() === ""}
          >
            Apply to {selected.size} leads
          </Button>
          <Button
            variant="danger"
            size="default"
            className="whitespace-nowrap gap-1.5"
            onClick={() => setConfirmBulkDelete(true)}
            isLoading={bulkDelete.isPending}
          >
            <Trash2 className="size-4" />
            Delete ({selected.size})
          </Button>
        </div>
      ) : null}

      {rows.length > 0 ? (
        <div className="mb-3 flex items-center justify-between">
          <label className="inline-flex min-h-11 items-center gap-3 text-body text-ink">
            <input
              type="checkbox"
              className={cn("size-4 accent-primary", focusRing)}
              checked={pageSelected}
              onChange={togglePage}
            />
            {selected.size > 0 ? `${selected.size} selected` : "Select page"}
          </label>
          {leads.data ? (
            <p className="text-small text-gray-500">
              Showing {rows.length} of {leads.data.total} {leads.data.total === 1 ? "lead" : "leads"}
            </p>
          ) : null}
        </div>
      ) : null}

      <DataTable
        columns={columns}
        rows={rows}
        getRowId={(row) => row.id}
        isLoading={leads.isPending}
        error={leads.isError ? apiErrorMessage(leads.error, "Leads could not be loaded.") : null}
        onRetry={() => {
          void leads.refetch();
        }}
        emptyTitle={hasFilters ? "No matching leads" : "No leads yet"}
        emptyDescription={
          hasFilters
            ? "Try a different search or clear the filters."
            : "Add a business you want to contact."
        }
        emptyAction={
          hasFilters ? (
            <Button variant="secondary" className="h-9 px-3 text-small" onClick={clearFilters}>
              Clear filters
            </Button>
          ) : (
            <Button
              className="h-9 px-3 text-small"
              onClick={() => {
                navigate("/leads/new");
              }}
            >
              Add lead
            </Button>
          )
        }
        page={page}
        pageCount={pageCount}
        onPageChange={(nextPage) => {
          setPage(nextPage);
          setSelected(new Set());
        }}
        renderCard={(row) => {
          const nba = getNextBestAction(row);
          return (
            <article className="flex gap-3">
              <label className="inline-flex size-11 shrink-0 items-start justify-center pt-0.5">
                <input
                  type="checkbox"
                  className={cn("size-4 accent-primary", focusRing)}
                  aria-label={`Select ${row.business_name}`}
                  checked={selected.has(row.id)}
                  onChange={() => {
                    toggle(row.id);
                  }}
                />
              </label>
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-3">
                  <Link
                    to={`/leads/${row.id}`}
                    className={cn(
                      "text-h4 font-bold break-words text-ink hover:text-primary-700",
                      focusRing,
                    )}
                  >
                    {row.business_name}
                  </Link>
                  {row.lead_score ? (
                    <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-orange-50 px-2 py-0.5 text-caption font-bold text-orange-700">
                      <Flame className="size-3" />
                      {row.lead_score}
                    </span>
                  ) : null}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <StatusBadge status={row.lead_status} />
                  {row.industry ? <span className="text-small text-gray-600">{row.industry}</span> : null}
                  {row.city ? <span className="text-caption text-gray-500">• {row.city}</span> : null}
                </div>

                <div className="mt-3 flex items-center justify-between border-t border-gray-100 pt-3">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      title="Delete Lead"
                      onClick={() => setLeadToDelete({ id: row.id, name: row.business_name })}
                      className="inline-flex size-7 items-center justify-center rounded border border-gray-200 text-gray-400 hover:border-red-300 hover:bg-red-50 hover:text-danger transition-colors"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                    <span className="text-caption text-gray-500">
                      Next: <strong className="text-ink">{nba.action}</strong>
                    </span>
                  </div>
                  <Button
                    variant="primary"
                    className="h-7 px-2.5 text-caption font-medium"
                    onClick={() => navigate(`/leads/${row.id}?tab=${nba.targetTab}`)}
                  >
                    {nba.ctaLabel}
                  </Button>
                </div>
              </div>
            </article>
          );
        }}
      />

      <ConfirmDialog
        open={Boolean(leadToDelete)}
        title="Delete lead?"
        description={
          leadToDelete
            ? `Are you sure you want to delete "${leadToDelete.name}"? All associated audits, mockups, outreach drafts, and notes will be permanently removed.`
            : "This lead will be deleted."
        }
        confirmLabel="Delete lead"
        isLoading={deleteLead.isPending}
        onConfirm={handleDeleteLead}
        onClose={() => {
          if (!deleteLead.isPending) {
            setLeadToDelete(null);
          }
        }}
      />

      <ConfirmDialog
        open={confirmBulkDelete}
        title={`Delete ${selected.size} selected leads?`}
        description="All associated audits, mockups, outreach drafts, and notes for the selected leads will be permanently deleted."
        confirmLabel={`Delete ${selected.size} leads`}
        isLoading={bulkDelete.isPending}
        onConfirm={handleBulkDelete}
        onClose={() => {
          if (!bulkDelete.isPending) {
            setConfirmBulkDelete(false);
          }
        }}
      />
    </>
  );
}
