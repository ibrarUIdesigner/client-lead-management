import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { DataTable, type DataColumn } from "../components/data/DataTable";
import { Badge, StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { leadStatusOptions } from "../features/leads/statuses";
import { useBulkUpdateLeads, useLeads } from "../hooks/useLeads";
import { apiErrorMessage } from "../lib/apiError";
import { cn, focusRing } from "../lib/cn";
import type { Lead, LeadListParams } from "../types/lead";

type Filters = {
  q: string;
  lead_status: string;
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
  industry: "",
  city: "",
  country: "",
  source: "",
  tag: "",
  website_status: "",
  min_score: "",
  sort: "created_at:desc",
};

const sortOptions = [
  { value: "created_at:desc", label: "Newest" },
  { value: "created_at:asc", label: "Oldest" },
  { value: "business_name:asc", label: "Name" },
  { value: "lead_score:desc", label: "Score" },
  { value: "updated_at:desc", label: "Recently updated" },
];

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

export function LeadListPage() {
  const navigate = useNavigate();
  const { notify } = useToast();
  const [draft, setDraft] = useState(defaultFilters);
  const [applied, setApplied] = useState(defaultFilters);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkStatus, setBulkStatus] = useState("");
  const [bulkTag, setBulkTag] = useState("");
  const leads = useLeads(toParams(applied, page));
  const bulkUpdate = useBulkUpdateLeads();
  const rows = leads.data?.items ?? [];
  const pageCount = leads.data ? Math.max(1, Math.ceil(leads.data.total / leads.data.limit)) : 1;
  const hasFilters = filtersAreActive(applied);
  const pageSelected = rows.length > 0 && rows.every((row) => selected.has(row.id));

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
    setPage(1);
    setSelected(new Set());
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
        rows.forEach((row) => next.delete(row.id));
      } else {
        rows.forEach((row) => next.add(row.id));
      }
      return next;
    });
  };

  const applyBulk = () => {
    const tags = bulkTag
      .split(",")
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);
    bulkUpdate.mutate(
      {
        ids: [...selected],
        lead_status: bulkStatus || null,
        add_tags: tags,
      },
      {
        onSuccess: () => {
          notify("Leads updated.", "success");
          setSelected(new Set());
          setBulkStatus("");
          setBulkTag("");
        },
        onError: (error) => {
          notify(apiErrorMessage(error, "Could not update those leads."), "danger");
        },
      },
    );
  };

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
        <Link
          to={`/leads/${row.id}`}
          className={cn("font-medium text-ink hover:text-primary-700", focusRing)}
        >
          {row.business_name}
        </Link>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusBadge status={row.lead_status} />,
    },
    {
      id: "location",
      header: "Location",
      cell: (row) => [row.city, row.country].filter(Boolean).join(", ") || "—",
    },
    {
      id: "industry",
      header: "Industry",
      cell: (row) => row.industry || "—",
    },
    {
      id: "tags",
      header: "Tags",
      cell: (row) =>
        row.tags.length > 0 ? (
          <span className="flex flex-wrap gap-1">
            {row.tags.slice(0, 3).map((tag) => (
              <Badge key={tag}>{tag}</Badge>
            ))}
          </span>
        ) : (
          "—"
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Leads"
        description="Businesses you want to contact."
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                navigate("/leads/import");
              }}
            >
              Import CSV
            </Button>
            <Button
              onClick={() => {
                navigate("/leads/new");
              }}
            >
              Add lead
            </Button>
          </>
        }
      />
      <form className="mb-6 grid gap-4 md:grid-cols-3" onSubmit={applyFilters}>
        <div className="md:col-span-2">
          <Input
            label="Search"
            value={draft.q}
            onChange={(event) => {
              updateDraft("q", event.target.value);
            }}
          />
        </div>
        <Select
          label="Sort"
          options={sortOptions}
          value={draft.sort}
          onChange={(event) => {
            updateDraft("sort", event.target.value);
          }}
        />
        <Select
          label="Status"
          placeholder="Any status"
          options={leadStatusOptions}
          value={draft.lead_status}
          onChange={(event) => {
            updateDraft("lead_status", event.target.value);
          }}
        />
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
        <Input
          label="Website status"
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
        <div className="flex flex-wrap items-end gap-2 md:col-span-2">
          <Button type="submit">Apply filters</Button>
          <Button variant="secondary" onClick={clearFilters}>
            Clear
          </Button>
        </div>
      </form>

      {selected.size > 0 ? (
        <div className="mb-6 grid items-end gap-4 rounded-card border border-gray-200 bg-white p-4 md:grid-cols-[1fr_1fr_auto]">
          <Select
            label="Set status"
            placeholder="Keep current status"
            options={leadStatusOptions}
            value={bulkStatus}
            onChange={(event) => {
              setBulkStatus(event.target.value);
            }}
          />
          <Input
            label="Add tag"
            value={bulkTag}
            onChange={(event) => {
              setBulkTag(event.target.value);
            }}
          />
          <Button
            onClick={applyBulk}
            isLoading={bulkUpdate.isPending}
            disabled={!bulkStatus && bulkTag.trim() === ""}
          >
            Apply to {selected.size}
          </Button>
        </div>
      ) : null}

      {rows.length > 0 ? (
        <div className="mb-3">
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
              {leads.data.total} {leads.data.total === 1 ? "lead" : "leads"}
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
            <Button variant="secondary" onClick={clearFilters}>
              Clear filters
            </Button>
          ) : (
            <Button
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
      />
    </>
  );
}
