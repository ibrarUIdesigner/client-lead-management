import { QueryGate } from "../components/feedback/QueryGate";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { useHealth } from "../hooks/useHealth";
import { useOutreachTemplates } from "../hooks/useWorkspace";
import type { OutreachTemplateItem } from "../types/workspace";

export function SettingsPage() {
  const health = useHealth();
  const templates = useOutreachTemplates();
  const databaseLabel =
    health.data?.database === "ok" ? "Database connected" : "Database unavailable";

  return (
    <>
      <PageHeader
        title="Settings"
        description="Workspace details and the message templates used for outreach."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Card>
          <h2 className="text-h4 font-semibold text-ink">Workspace</h2>
          <dl className="mt-4 space-y-4">
            <div>
              <dt className="text-caption font-semibold text-gray-500">Name</dt>
              <dd className="mt-1 text-body text-ink">Client Acquisition</dd>
            </div>
            <div>
              <dt className="text-caption font-semibold text-gray-500">Environment</dt>
              <dd className="mt-1 text-body text-ink">
                {health.isPending ? "Checking…" : (health.data?.environment ?? "Unavailable")}
              </dd>
            </div>
            <div>
              <dt className="text-caption font-semibold text-gray-500">Database</dt>
              <dd className="mt-2">
                {health.data ? (
                  <Badge tone={health.data.database === "ok" ? "green" : "orange"}>
                    {databaseLabel}
                  </Badge>
                ) : (
                  <span className="text-body text-gray-600">Checking the connection.</span>
                )}
              </dd>
            </div>
          </dl>
        </Card>
        <QueryGate
          pending={templates.isPending}
          error={templates.error}
          onRetry={() => {
            void templates.refetch();
          }}
          fallback="Templates could not be loaded."
        >
          {templates.data ? <TemplateList items={templates.data} /> : null}
        </QueryGate>
      </div>
    </>
  );
}

function TemplateList({ items }: { items: OutreachTemplateItem[] }) {
  return (
    <div className="space-y-4">
      <h2 className="text-h4 font-semibold text-ink">Message templates</h2>
      {items.length === 0 ? (
        <Card>
          <p className="text-body text-gray-600">No templates yet.</p>
        </Card>
      ) : null}
      {items.map((item) => (
        <Card key={item.id}>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-h4 font-semibold text-ink">{item.name}</h3>
            {item.channel ? <Badge>{item.channel}</Badge> : null}
            <Badge tone={item.is_active ? "green" : "gray"}>
              {item.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
          {item.subject ? <p className="mt-3 text-body text-ink">{item.subject}</p> : null}
          {item.body ? (
            <p className="mt-3 whitespace-pre-wrap text-body text-gray-700">{item.body}</p>
          ) : null}
        </Card>
      ))}
    </div>
  );
}
