import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { QueryGate } from "../components/feedback/QueryGate";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { DesignTokenRail } from "../features/design-md/DesignTokenRail";
import { MarkdownView } from "../features/design-md/markdown";
import { useDeleteDesignGuide, useDesignGuide } from "../hooks/useDesignGuides";
import { apiErrorMessage } from "../lib/apiError";
import { formatWhen } from "../lib/format";
import { downloadDesignGuide } from "../services/designGuides";

export function DesignGuideViewPage() {
  const { guideId = "" } = useParams();
  const guide = useDesignGuide(guideId);
  const remove = useDeleteDesignGuide();
  const navigate = useNavigate();
  const { notify } = useToast();
  const [confirming, setConfirming] = useState(false);

  async function onDelete() {
    try {
      await remove.mutateAsync(guideId);
      notify("Design guide deleted.");
      navigate("/design-md");
    } catch (caught) {
      notify(apiErrorMessage(caught, "That design guide could not be deleted."), "danger");
    }
  }

  return (
    <>
      <Button
        variant="ghost"
        className="-ml-3 mb-4"
        onClick={() => {
          navigate("/design-md");
        }}
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to guides
      </Button>
      <QueryGate
        pending={guide.isPending}
        error={guide.error}
        fallback="The design guide could not be loaded."
        onRetry={() => {
          void guide.refetch();
        }}
      >
        {guide.data ? (
          <>
            <PageHeader
              title={guide.data.name}
              description={guide.data.description || "No description."}
              actions={
                <>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      navigate(`/design-md/${guide.data?.id}/edit`);
                    }}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      if (!guide.data) {
                        return;
                      }
                      void downloadDesignGuide(guide.data.id, guide.data.name).catch(
                        (caught: unknown) => {
                          notify(
                            apiErrorMessage(caught, "The file could not be downloaded."),
                            "danger",
                          );
                        },
                      );
                    }}
                  >
                    Download
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setConfirming(true);
                    }}
                  >
                    Delete
                  </Button>
                </>
              }
            />
            <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
              <Card className="min-w-0">
                <div className="flex flex-wrap gap-2">
                  {guide.data.tags.length > 0 ? (
                    guide.data.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)
                  ) : (
                    <span className="text-small text-gray-500">No tags</span>
                  )}
                </div>
                <p className="mt-3 text-small text-gray-600">
                  Updated {formatWhen(guide.data.updated_at)}
                </p>
                <div className="mt-6">
                  <MarkdownView source={guide.data.content} />
                </div>
                <p className="mt-6 text-small text-gray-500">
                  <Link to="/design-md" className="text-primary-700">
                    All guides
                  </Link>
                </p>
              </Card>
              <DesignTokenRail
                name={guide.data.name}
                description={guide.data.description}
                source={guide.data.content}
              />
            </div>
            <ConfirmDialog
              open={confirming}
              title="Delete this design guide?"
              description="Mockups that already used it will keep their saved copy."
              confirmLabel="Delete guide"
              isLoading={remove.isPending}
              onConfirm={() => {
                void onDelete();
              }}
              onClose={() => {
                if (!remove.isPending) {
                  setConfirming(false);
                }
              }}
            />
          </>
        ) : null}
      </QueryGate>
    </>
  );
}
