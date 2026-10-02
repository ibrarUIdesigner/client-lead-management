import { Link, useNavigate } from "react-router-dom";

import { LoadingState } from "../components/feedback/LoadingState";
import { OfflineState } from "../components/feedback/OfflineState";
import { QueryGate } from "../components/feedback/QueryGate";
import { EmptyState } from "../components/feedback/EmptyState";
import { PageHeader } from "../components/layout/PageHeader";
import { useSidebarCollapsed } from "../components/layout/useSidebarCollapsed";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Switch } from "../components/ui/Switch";
import { Tabs } from "../components/ui/Tabs";
import { GmailSettingsCard } from "../features/gmail/GmailSettingsCard";
import { useApify } from "../hooks/useApify";
import { useDiscovery } from "../hooks/useDiscovery";
import { useHealth, useProviders } from "../hooks/useHealth";
import { useOnline } from "../hooks/useOnline";
import { useOutreachTemplates } from "../hooks/useWorkspace";
import { sessionEmail, signOut } from "../lib/auth";
import { cn, focusRing } from "../lib/cn";
import type { HealthResponse, ProviderSnapshot } from "../types/health";
import type { OutreachTemplateItem } from "../types/workspace";

const areas = [
  {
    to: "/discover",
    title: "Find leads",
    body: "Saved searches, listing sources, and the daily run.",
  },
  {
    to: "/apify",
    title: "Apify",
    body: "Connected actors, run history, and imports.",
  },
  {
    to: "/outreach",
    title: "Outreach",
    body: "Drafts, templates, and Gmail replies.",
  },
  {
    to: "/follow-ups",
    title: "Follow-ups",
    body: "Today, overdue, and upcoming reminders.",
  },
];

export function SettingsPage() {
  return (
    <>
      <PageHeader
        title="Settings"
        description="Workspace status, connections, message templates, and this browser."
      />
      <Tabs
        label="Settings sections"
        tabs={[
          { id: "workspace", label: "Workspace", content: <WorkspaceSection /> },
          { id: "integrations", label: "Integrations", content: <IntegrationsSection /> },
          { id: "templates", label: "Templates", content: <TemplatesSection /> },
          { id: "account", label: "Account", content: <AccountSection /> },
        ]}
      />
    </>
  );
}

function WorkspaceSection() {
  const health = useHealth();
  const online = useOnline();

  if (!online || (health.isError && !health.data)) {
    if (!online) {
      return (
        <OfflineState
          onRetry={() => {
            void health.refetch();
          }}
        />
      );
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-h3 font-semibold text-ink">Client Acquisition</h2>
        <p className="mt-2 max-w-2xl text-body leading-relaxed text-gray-600">
          One workspace for finding local businesses, reviewing their sites, and keeping outreach
          in one place.
        </p>
        <ul className="mt-5 grid gap-3 sm:grid-cols-2">
          {areas.map((area) => (
            <li key={area.to}>
              <Link
                to={area.to}
                className={cn(
                  "block h-full rounded-card border border-gray-200 px-4 py-3 hover:border-primary-200 hover:bg-primary-50",
                  focusRing,
                )}
              >
                <p className="text-body font-semibold text-ink">{area.title}</p>
                <p className="mt-1 text-small leading-relaxed text-gray-600">{area.body}</p>
              </Link>
            </li>
          ))}
        </ul>
      </Card>

      {health.isPending ? <LoadingState label="Checking the workspace" /> : null}
      {health.isError ? (
        <div className="flex flex-col items-start gap-3 rounded-card border border-red-200 bg-red-50 px-4 py-6" role="alert">
          <h2 className="text-h4 font-semibold text-ink">Workspace status is unavailable</h2>
          <p className="text-body text-red-800">The API did not respond. Start the server, then try again.</p>
          <Button
            variant="secondary"
            onClick={() => {
              void health.refetch();
            }}
          >
            Try again
          </Button>
        </div>
      ) : null}
      {health.data ? <HealthCard health={health.data} /> : null}
    </div>
  );
}

function HealthCard({ health }: { health: HealthResponse }) {
  const rows = [
    { label: "Environment", value: health.environment },
    { label: "Service", value: health.service },
    {
      label: "Database",
      value: health.database === "ok" ? "Connected" : "Unavailable",
      tone: health.database === "ok" ? ("green" as const) : ("orange" as const),
    },
    {
      label: "Email drafts",
      value: emailDraftLabel(health.email_drafts),
      tone: health.email_drafts === "unconfigured" ? ("orange" as const) : ("green" as const),
      detail: emailDraftDetail(health.email_drafts),
    },
  ];

  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Status</h2>
      <p className="mt-1 text-small text-gray-600">Read from the API health check.</p>
      <dl className="mt-4 divide-y divide-gray-100">
        {rows.map((row) => (
          <div key={row.label} className="flex flex-col gap-1 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
            <dt className="text-caption font-semibold text-gray-500">{row.label}</dt>
            <dd className="min-w-0 sm:text-right">
              {row.tone ? <Badge tone={row.tone}>{row.value}</Badge> : <span className="text-body text-ink">{row.value}</span>}
              {row.detail ? <p className="mt-2 max-w-md text-small leading-relaxed text-gray-600 sm:ml-auto">{row.detail}</p> : null}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function IntegrationsSection() {
  const online = useOnline();
  const health = useHealth();

  if (!online) {
    return (
      <OfflineState
        onRetry={() => {
          void health.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <GmailSettingsCard />
      <ProvidersCard />
      <ApifyConnectionCard />
      <DiscoveryConnectionCard />
    </div>
  );
}

function ProvidersCard() {
  const providers = useProviders();
  const health = useHealth();
  const snapshots = providers.data?.providers ?? [];

  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Draft providers</h2>
      <p className="mt-1 max-w-2xl text-body leading-relaxed text-gray-600">
        Outreach drafts use whichever provider has an API key. Keys stay on the server.
      </p>
      {providers.isPending ? (
        <div className="mt-4">
          <LoadingState label="Loading providers" framed={false} />
        </div>
      ) : null}
      {providers.isError ? (
        <p className="mt-4 text-body text-danger" role="alert">
          Provider details could not be loaded.
        </p>
      ) : null}
      {snapshots.length > 0 ? (
        <ul className="mt-4 grid gap-3 lg:grid-cols-2">
          {snapshots.map((snapshot) => (
            <li key={snapshot.id}>
              <ProviderRow snapshot={snapshot} health={health.data} />
            </li>
          ))}
        </ul>
      ) : null}
      {!providers.isPending && snapshots.length === 0 && !providers.isError ? (
        <p className="mt-4 text-body text-gray-600">No providers were returned.</p>
      ) : null}
    </Card>
  );
}

function ProviderRow({
  snapshot,
  health,
}: {
  snapshot: ProviderSnapshot;
  health: HealthResponse | undefined;
}) {
  const active = snapshot.active || health?.email_drafts === snapshot.id;
  const name = snapshot.id === "gemini" ? "Gemini" : "Groq";

  return (
    <div className={cn("h-full rounded-card border border-gray-200 p-4", active && "border-primary-200 bg-primary-50")}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-h4 font-semibold text-ink">{name}</h3>
        <Badge tone={snapshot.configured ? (active ? "green" : "indigo") : "orange"}>
          {snapshot.configured ? (active ? "Active" : "Ready") : "Not configured"}
        </Badge>
      </div>
      <dl className="mt-3 space-y-2">
        <div>
          <dt className="text-caption font-semibold text-gray-500">Model</dt>
          <dd className="mt-0.5 text-body break-words text-ink">{snapshot.display_name ?? snapshot.model}</dd>
        </div>
        <div>
          <dt className="text-caption font-semibold text-gray-500">Credits</dt>
          <dd className="mt-0.5 text-small leading-relaxed text-gray-700">{snapshot.credits}</dd>
        </div>
      </dl>
    </div>
  );
}

function ApifyConnectionCard() {
  const apify = useApify();

  return (
    <Card>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-h3 font-semibold text-ink">Apify</h2>
          <p className="mt-1 text-body leading-relaxed text-gray-600">
            The token stays on the server. Actors and run history live on the Apify page.
          </p>
        </div>
        {apify.data ? (
          <Badge tone={apify.data.token_configured ? "green" : "orange"}>
            {apify.data.token_configured ? "Token set" : "Token missing"}
          </Badge>
        ) : null}
      </div>
      {apify.isPending ? (
        <div className="mt-4">
          <LoadingState label="Checking Apify" framed={false} />
        </div>
      ) : null}
      {apify.isError ? (
        <p className="mt-4 text-body text-danger" role="alert">
          Apify status could not be loaded.
        </p>
      ) : null}
      {apify.data ? (
        <dl className="mt-4 space-y-3">
          <div>
            <dt className="text-caption font-semibold text-gray-500">Connectors</dt>
            <dd className="mt-1 text-body text-ink">
              {apify.data.connectors.length === 0
                ? "None yet"
                : `${apify.data.connectors.length} connected`}
            </dd>
          </div>
          <div>
            <dt className="text-caption font-semibold text-gray-500">Runs</dt>
            <dd className="mt-1 text-body text-ink">{apify.data.runs.length} in history</dd>
          </div>
          {apify.data.token_error ? (
            <p className="text-small text-danger" role="alert">
              {apify.data.token_error}
            </p>
          ) : null}
        </dl>
      ) : null}
      <Link
        to="/apify"
        className={cn(
          "mt-4 inline-flex h-11 items-center text-body font-semibold text-primary-700 sm:h-10",
          focusRing,
        )}
      >
        Open Apify
      </Link>
    </Card>
  );
}

function DiscoveryConnectionCard() {
  const discovery = useDiscovery();
  const status = discovery.data;

  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Lead discovery</h2>
      <p className="mt-1 text-body leading-relaxed text-gray-600">
        Directory keys and the daily search schedule.
      </p>
      {discovery.isPending ? (
        <div className="mt-4">
          <LoadingState label="Checking discovery" framed={false} />
        </div>
      ) : null}
      {discovery.isError ? (
        <p className="mt-4 text-body text-danger" role="alert">
          Discovery status could not be loaded.
        </p>
      ) : null}
      {status ? (
        <>
          <dl className="mt-4 space-y-3">
            <div>
              <dt className="text-caption font-semibold text-gray-500">Schedule</dt>
              <dd className="mt-1 text-body text-ink">{status.schedule}</dd>
            </div>
            <div>
              <dt className="text-caption font-semibold text-gray-500">Saved searches</dt>
              <dd className="mt-1 text-body text-ink">
                {status.searches.length === 0
                  ? "None yet"
                  : `${status.searches.filter((search) => search.is_active).length} active of ${status.searches.length}`}
              </dd>
            </div>
          </dl>
          <ul className="mt-4 space-y-2">
            <SourceLine name="OpenStreetMap" ready detail="No key required" />
            <SourceLine
              name="Google Places"
              ready={status.google_configured}
              detail={status.google_configured ? "Key configured" : "Set GOOGLE_PLACES_API_KEY"}
            />
            <SourceLine
              name="Yelp"
              ready={status.yelp_configured}
              detail={status.yelp_configured ? "Key configured" : "Set YELP_API_KEY"}
            />
            <SourceLine name="Yell, BusinessList, ePages" ready detail="Public listings" />
          </ul>
        </>
      ) : null}
      <Link
        to="/discover"
        className={cn(
          "mt-4 inline-flex h-11 items-center text-body font-semibold text-primary-700 sm:h-10",
          focusRing,
        )}
      >
        Open Find leads
      </Link>
    </Card>
  );
}

function SourceLine({ name, ready, detail }: { name: string; ready: boolean; detail: string }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-control bg-gray-50 px-3 py-2.5">
      <div className="min-w-0">
        <p className="text-small font-semibold text-ink">{name}</p>
        <p className="text-caption text-gray-500">{detail}</p>
      </div>
      <Badge tone={ready ? "green" : "orange"}>{ready ? "Ready" : "Needs key"}</Badge>
    </li>
  );
}

function TemplatesSection() {
  const templates = useOutreachTemplates();

  return (
    <QueryGate
      pending={templates.isPending}
      error={templates.error}
      loadingLabel="Loading templates"
      onRetry={() => {
        void templates.refetch();
      }}
      fallback="Templates could not be loaded."
    >
      {templates.data ? <TemplateList items={templates.data} /> : null}
    </QueryGate>
  );
}

function AccountSection() {
  const navigate = useNavigate();
  const { collapsed, setCollapsed } = useSidebarCollapsed();

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-h3 font-semibold text-ink">Signed in</h2>
        <dl className="mt-4 space-y-4">
          <div>
            <dt className="text-caption font-semibold text-gray-500">Email</dt>
            <dd className="mt-1 text-body break-all text-ink">{sessionEmail()}</dd>
          </div>
          <div>
            <dt className="text-caption font-semibold text-gray-500">Session</dt>
            <dd className="mt-1 text-body leading-relaxed text-gray-700">
              This browser keeps the session until you sign out.
            </dd>
          </div>
        </dl>
        <Button
          className="mt-5"
          variant="secondary"
          onClick={() => {
            signOut();
            navigate("/login", { replace: true });
          }}
        >
          Sign out
        </Button>
      </Card>
      <Card>
        <h2 className="text-h3 font-semibold text-ink">This browser</h2>
        <p className="mt-1 text-body leading-relaxed text-gray-600">
          Layout choices stay on this device.
        </p>
        <div className="mt-4">
          <Switch
            label="Collapse the sidebar"
            checked={collapsed}
            onCheckedChange={setCollapsed}
          />
        </div>
      </Card>
    </div>
  );
}

function emailDraftLabel(provider: HealthResponse["email_drafts"]): string {
  if (provider === "gemini") {
    return "Gemini API";
  }
  if (provider === "groq") {
    return "Groq API";
  }
  return "Add an API key";
}

function emailDraftDetail(provider: HealthResponse["email_drafts"]): string {
  if (provider === "gemini") {
    return "Drafts use the Gemini free tier. Google can use that content to improve its products, so drafts send public business details and audit findings.";
  }
  if (provider === "groq") {
    return "Drafts use the Groq API with the public business details and verified audit findings.";
  }
  return "Set GEMINI_API_KEY or GROQ_API_KEY in the server environment and restart the API.";
}

function TemplateList({ items }: { items: OutreachTemplateItem[] }) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No templates yet"
        description="Message templates will show up here after they are added to the workspace."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-h3 font-semibold text-ink">Message templates</h2>
        <p className="mt-1 text-body text-gray-600">
          {items.length} {items.length === 1 ? "template" : "templates"} available when you write outreach.
        </p>
      </div>
      {items.map((item) => (
        <Card key={item.id}>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-h4 font-semibold text-ink">{item.name}</h3>
            {item.channel ? <Badge>{item.channel}</Badge> : null}
            {item.template_type ? <Badge tone="indigo">{item.template_type}</Badge> : null}
            <Badge tone={item.is_active ? "green" : "gray"}>{item.is_active ? "Active" : "Inactive"}</Badge>
          </div>
          {item.subject ? <p className="mt-3 text-body font-medium text-ink">{item.subject}</p> : null}
          {item.body ? (
            <p className="mt-3 text-body leading-relaxed whitespace-pre-wrap text-gray-700">{item.body}</p>
          ) : (
            <p className="mt-3 text-small text-gray-500">No body saved for this template.</p>
          )}
        </Card>
      ))}
    </div>
  );
}
