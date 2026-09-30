import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { QueryGate } from "../components/feedback/QueryGate";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Checkbox } from "../components/ui/Checkbox";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import {
  useCreateDiscoverySearch,
  useDeleteDiscoverySearch,
  useDiscovery,
  useRunDiscovery,
  useUpdateDiscoverySearch,
} from "../hooks/useDiscovery";
import { useLeads } from "../hooks/useLeads";
import { apiErrorMessage } from "../lib/apiError";
import { formatWhen } from "../lib/format";
import type { DiscoverySearch } from "../types/discovery";
import type { Lead } from "../types/lead";

const websiteLabels: Record<string, { label: string; tone: "green" | "orange" | "gray" }> = {
  missing: { label: "No website", tone: "green" },
  social_only: { label: "Social only", tone: "orange" },
  present: { label: "Has a website", tone: "gray" },
};

export function DiscoverPage() {
  const discovery = useDiscovery();
  const found = useLeads({
    tag: "discovered",
    limit: 8,
    sort: "created_at",
    direction: "desc",
  });

  return (
    <>
      <PageHeader
        title="Find leads"
        description="Search public business listings and save the details you need for a pitch. Active searches run once a day while the API is running."
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
        fallback="Lead search could not be loaded."
      >
        {discovery.data ? (
          <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="space-y-6">
              <SearchForm
                categories={discovery.data.categories}
                googleConfigured={discovery.data.google_configured}
                yelpConfigured={discovery.data.yelp_configured}
                running={discovery.data.running}
              />
              <SearchList searches={discovery.data.searches} running={discovery.data.running} />
              <FoundLeads leads={found.data?.items ?? []} />
            </div>
            <ScheduleCard
              schedule={discovery.data.schedule}
              nextRunAt={discovery.data.next_run_at}
              running={discovery.data.running}
              googleConfigured={discovery.data.google_configured}
              yelpConfigured={discovery.data.yelp_configured}
              latestMessage={discovery.data.latest_message}
            />
          </div>
        ) : null}
      </QueryGate>
    </>
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
      {running ? "Searching…" : "Run active searches"}
    </Button>
  );
}

function SearchForm({
  categories,
  googleConfigured,
  yelpConfigured,
  running,
}: {
  categories: { value: string; label: string }[];
  googleConfigured: boolean;
  yelpConfigured: boolean;
  running: boolean;
}) {
  const create = useCreateDiscoverySearch();
  const run = useRunDiscovery();
  const { notify } = useToast();
  const [category, setCategory] = useState(categories[0]?.value ?? "dentist");
  const [customCategory, setCustomCategory] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [useOsm, setUseOsm] = useState(true);
  const [useGoogle, setUseGoogle] = useState(true);
  const [useYelp, setUseYelp] = useState(true);
  const [useYell, setUseYell] = useState(true);
  const [useBusinessList, setUseBusinessList] = useState(true);
  const [useEpages, setUseEpages] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function save(searchNow: boolean) {
    const chosen = category === "other" ? customCategory.trim() : category;
    if (chosen.length < 2 || city.trim().length < 2 || country.trim().length < 2) {
      setError("Enter a category, city, and country.");
      return;
    }
    if (!useOsm && !useGoogle && !useYelp && !useYell && !useBusinessList && !useEpages) {
      setError("Choose at least one source.");
      return;
    }
    setError(null);
    create.mutate(
      {
        category: chosen,
        city: city.trim(),
        country: country.trim(),
        use_openstreetmap: useOsm,
        use_google: useGoogle,
        use_yelp: useYelp,
        use_yell: useYell,
        use_businesslist: useBusinessList,
        use_epages: useEpages,
      },
      {
        onSuccess: (search) => {
          setCity("");
          setCustomCategory("");
          notify("Search saved.", "success");
          if (!searchNow) {
            return;
          }
          run.mutate(search.id, {
            onError: (runError) => {
              notify(apiErrorMessage(runError, "The search could not start."), "danger");
            },
          });
        },
        onError: (saveError) => {
          setError(apiErrorMessage(saveError, "The search could not be saved."));
        },
      },
    );
  }

  return (
    <Card>
      <h2 className="text-h4 font-semibold text-ink">New search</h2>
      <p className="mt-2 text-body text-gray-600">
        Pick the kind of business and the city you want to pitch. Businesses with no website are
        scored higher.
      </p>
      <form
        className="mt-5 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          save(true);
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Select
            label="Category"
            value={category}
            options={[...categories, { value: "other", label: "Other" }]}
            onChange={(event) => {
              setCategory(event.target.value);
            }}
          />
          {category === "other" ? (
            <Input
              label="Custom category"
              value={customCategory}
              onChange={(event) => {
                setCustomCategory(event.target.value);
              }}
              placeholder="Pet grooming"
            />
          ) : (
            <span />
          )}
          <Input
            label="City"
            value={city}
            onChange={(event) => {
              setCity(event.target.value);
            }}
            placeholder="Austin"
          />
          <Input
            label="Country"
            value={country}
            onChange={(event) => {
              setCountry(event.target.value);
            }}
            placeholder="United States"
          />
        </div>
        <div className="flex flex-col gap-2">
          <Checkbox
            label="OpenStreetMap"
            checked={useOsm}
            onChange={(event) => {
              setUseOsm(event.target.checked);
            }}
          />
          <Checkbox
            label="Google Places"
            checked={useGoogle}
            onChange={(event) => {
              setUseGoogle(event.target.checked);
            }}
          />
          <Checkbox
            label="Yelp"
            checked={useYelp}
            onChange={(event) => {
              setUseYelp(event.target.checked);
            }}
          />
          <Checkbox
            label="Yell"
            checked={useYell}
            onChange={(event) => {
              setUseYell(event.target.checked);
            }}
          />
          <Checkbox
            label="BusinessList.pk"
            checked={useBusinessList}
            onChange={(event) => {
              setUseBusinessList(event.target.checked);
            }}
          />
          <Checkbox
            label="ePages.pk"
            checked={useEpages}
            onChange={(event) => {
              setUseEpages(event.target.checked);
            }}
          />
          {useGoogle && !googleConfigured ? (
            <p className="text-caption text-gray-500">
              Google Places runs after you set GOOGLE_PLACES_API_KEY.
            </p>
          ) : null}
          {useYelp && !yelpConfigured ? (
            <p className="text-caption text-gray-500">Yelp runs after you set YELP_API_KEY.</p>
          ) : null}
          <p className="text-caption text-gray-500">
            OpenStreetMap needs no key. BusinessList.pk and ePages.pk cover Pakistan. Yell covers
            the UK.
          </p>
        </div>
        {error ? (
          <p className="text-body text-danger" role="alert">
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" isLoading={create.isPending || run.isPending || running}>
            Save and search now
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={create.isPending || running}
            onClick={() => {
              save(false);
            }}
          >
            Save for the daily run
          </Button>
        </div>
      </form>
    </Card>
  );
}

function SearchList({ searches, running }: { searches: DiscoverySearch[]; running: boolean }) {
  if (searches.length === 0) {
    return (
      <Card>
        <h2 className="text-h4 font-semibold text-ink">Saved searches</h2>
        <p className="mt-2 text-body text-gray-600">
          No searches yet. Add a city and category to start collecting businesses.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <h2 className="text-h4 font-semibold text-ink">Saved searches</h2>
      {searches.map((search) => (
        <SearchRow key={search.id} search={search} running={running} />
      ))}
    </div>
  );
}

function SearchRow({ search, running }: { search: DiscoverySearch; running: boolean }) {
  const update = useUpdateDiscoverySearch();
  const remove = useDeleteDiscoverySearch();
  const run = useRunDiscovery();
  const { notify } = useToast();
  const label = search.category.replaceAll("_", " ");

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-h4 font-semibold capitalize text-ink">
            {label} in {search.city}
          </h3>
          <p className="mt-1 text-body text-gray-600">{search.country}</p>
        </div>
        <Badge tone={search.is_active ? "green" : "gray"}>
          {search.is_active ? "Daily" : "Paused"}
        </Badge>
      </div>
      <p className="mt-3 text-caption text-gray-500">
        {enabledSourceNames(search)}
        {search.last_finished_at
          ? ` · Last run ${formatWhen(search.last_finished_at)}`
          : " · Not run yet"}
      </p>
      {search.last_message ? (
        <p className="mt-2 text-body text-gray-700">{search.last_message}</p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          variant="secondary"
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
          Run now
        </Button>
        <Button
          variant="ghost"
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
          {search.is_active ? "Pause" : "Resume daily"}
        </Button>
        <Button
          variant="ghost"
          disabled={remove.isPending || running}
          onClick={() => {
            if (!window.confirm("Remove this search? Leads already saved will stay.")) {
              return;
            }
            remove.mutate(search.id, {
              onError: (error) => {
                notify(apiErrorMessage(error, "The search could not be removed."), "danger");
              },
            });
          }}
        >
          Remove
        </Button>
      </div>
    </Card>
  );
}

function FoundLeads({ leads }: { leads: Lead[] }) {
  if (leads.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-h4 font-semibold text-ink">Ready to pitch</h2>
        <Link to="/leads" className="text-body font-semibold text-primary-700">
          All leads
        </Link>
      </div>
      {leads.map((lead) => (
        <FoundLead key={lead.id} lead={lead} />
      ))}
    </div>
  );
}

function FoundLead({ lead }: { lead: Lead }) {
  const website = websiteLabels[lead.website_status ?? ""] ?? {
    label: "Website unknown",
    tone: "gray" as const,
  };

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-h4 font-semibold text-ink">{lead.business_name}</h3>
          <p className="mt-1 text-body text-gray-600">
            {[lead.industry, lead.city].filter(Boolean).join(" · ")}
          </p>
        </div>
        <Badge tone={website.tone}>{website.label}</Badge>
      </div>
      {lead.description ? <p className="mt-3 text-body text-gray-700">{lead.description}</p> : null}
      <p className="mt-3 text-caption text-gray-500">
        {lead.phone ? lead.phone : "No phone listed"}
        {lead.lead_score !== null ? ` · Score ${lead.lead_score}` : null}
      </p>
      <Link
        to={`/leads/${lead.id}`}
        className="mt-3 inline-flex text-body font-semibold text-primary-700"
      >
        Open lead
      </Link>
    </Card>
  );
}

function enabledSourceNames(search: DiscoverySearch): string {
  const names = [
    search.use_openstreetmap ? "OpenStreetMap" : null,
    search.use_google ? "Google Places" : null,
    search.use_yelp ? "Yelp" : null,
    search.use_yell ? "Yell" : null,
    search.use_businesslist ? "BusinessList.pk" : null,
    search.use_epages ? "ePages.pk" : null,
  ].filter((name) => name !== null);
  return names.join(", ");
}

function ScheduleCard({
  schedule,
  nextRunAt,
  running,
  googleConfigured,
  yelpConfigured,
  latestMessage,
}: {
  schedule: string;
  nextRunAt: string | null;
  running: boolean;
  googleConfigured: boolean;
  yelpConfigured: boolean;
  latestMessage: string | null;
}) {
  const { notify } = useToast();
  useRunCompletion(running, latestMessage, notify);

  return (
    <Card>
      <h2 className="text-h4 font-semibold text-ink">Schedule</h2>
      <dl className="mt-4 space-y-4">
        <div>
          <dt className="text-caption font-semibold text-gray-500">Automatic run</dt>
          <dd className="mt-1 text-body text-ink">{schedule}</dd>
        </div>
        <div>
          <dt className="text-caption font-semibold text-gray-500">Next run</dt>
          <dd className="mt-1 text-body text-ink">
            {running ? "Running now" : formatWhen(nextRunAt)}
          </dd>
        </div>
        <div>
          <dt className="text-caption font-semibold text-gray-500">Google Places</dt>
          <dd className="mt-2">
            <Badge tone={googleConfigured ? "green" : "orange"}>
              {googleConfigured ? "API key set" : "Key not set"}
            </Badge>
          </dd>
        </div>
        <div>
          <dt className="text-caption font-semibold text-gray-500">Yelp</dt>
          <dd className="mt-2">
            <Badge tone={yelpConfigured ? "green" : "orange"}>
              {yelpConfigured ? "API key set" : "Key not set"}
            </Badge>
          </dd>
        </div>
      </dl>
      <p className="mt-4 text-caption text-gray-500">
        Leave the API running so the daily search can start. A run that already finished today is
        not repeated until the next day.
      </p>
    </Card>
  );
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
