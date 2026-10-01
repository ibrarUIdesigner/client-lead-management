import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileText, Plus } from "lucide-react";

import { EmptyState } from "../components/feedback/EmptyState";
import { QueryGate } from "../components/feedback/QueryGate";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useDeleteDesignGuide, useDesignGuides } from "../hooks/useDesignGuides";
import { apiErrorMessage } from "../lib/apiError";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import { downloadDesignGuide } from "../services/designGuides";
import type { DesignGuideSummary } from "../types/designGuide";

export function DesignGuidesPage() {
  const navigate = useNavigate();
  const { notify } = useToast();
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState("");
  const guides = useDesignGuides(query, tag);
  const remove = useDeleteDesignGuide();

  async function onDelete(guide: DesignGuideSummary) {
    if (
      !window.confirm(
        "Delete this design guide? Mockups that already used it will keep their saved copy.",
      )
    ) {
      return;
    }
    try {
      await remove.mutateAsync(guide.id);
      notify("Design guide deleted.");
    } catch (caught) {
      notify(apiErrorMessage(caught, "That design guide could not be deleted."), "danger");
    }
  }

  return (
    <>
      <PageHeader
        title="Design MD"
        description="Reusable Markdown guides for homepage mockups. Business details stay on the lead."
        actions={
          <Button
            onClick={() => {
              navigate("/design-md/new");
            }}
          >
            <Plus size={18} aria-hidden="true" />
            Create
          </Button>
        }
      />
      <div className="mb-6 flex flex-col gap-3">
        <label className="text-small font-medium text-gray-700" htmlFor="guide-search">
          Search
        </label>
        <input
          id="guide-search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
          }}
          placeholder="Search by name, description, or content"
          className={cn(
            "h-11 w-full rounded-control border border-gray-300 bg-white px-3 text-body lg:h-10",
            focusRing,
          )}
        />
        {guides.data && guides.data.tags.length > 0 ? (
          <div className="flex flex-wrap gap-2" aria-label="Filter by tag">
            <Button
              variant={tag === "" ? "primary" : "secondary"}
              onClick={() => {
                setTag("");
              }}
            >
              All tags
            </Button>
            {guides.data.tags.map((item) => (
              <Button
                key={item}
                variant={tag === item ? "primary" : "secondary"}
                onClick={() => {
                  setTag(item);
                }}
              >
                {item}
              </Button>
            ))}
          </div>
        ) : null}
      </div>
      <QueryGate
        pending={guides.isPending}
        error={guides.error}
        fallback="Design guides could not be loaded."
        onRetry={() => {
          void guides.refetch();
        }}
      >
        {guides.data && guides.data.items.length === 0 ? (
          <EmptyState
            title={query || tag ? "No matching guides" : "No design guides yet"}
            description="Create a Markdown guide, or upload a .md file, then select it when you make a mockup."
            action={
              <Button
                onClick={() => {
                  navigate("/design-md/new");
                }}
              >
                Create
              </Button>
            }
          />
        ) : null}
        {guides.data && guides.data.items.length > 0 ? (
          <div className="grid gap-4">
            {guides.data.items.map((guide) => (
              <Card key={guide.id}>
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <FileText size={18} aria-hidden="true" className="text-primary-700" />
                      <h2 className="text-h4 font-semibold text-ink">{guide.name}</h2>
                    </div>
                    <p className="mt-2 max-w-3xl text-body text-gray-600">
                      {guide.description || "No description."}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {guide.tags.length > 0 ? (
                        guide.tags.map((item) => <Badge key={item}>{item}</Badge>)
                      ) : (
                        <span className="text-small text-gray-500">No tags</span>
                      )}
                    </div>
                    <p className="mt-3 text-small text-gray-600">
                      Updated {formatWhen(guide.updated_at)}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link
                      to={`/design-md/${guide.id}`}
                      className={cn(
                        "inline-flex h-10 items-center rounded-control border border-gray-300 px-4 text-body font-semibold",
                        focusRing,
                      )}
                    >
                      View
                    </Link>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        navigate(`/design-md/${guide.id}/edit`);
                      }}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        void downloadDesignGuide(guide.id, guide.name).catch((caught: unknown) => {
                          notify(apiErrorMessage(caught, "The file could not be downloaded."), "danger");
                        });
                      }}
                    >
                      Download
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        void onDelete(guide);
                      }}
                      isLoading={remove.isPending}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : null}
      </QueryGate>
    </>
  );
}
