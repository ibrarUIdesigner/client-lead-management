import { Link, useNavigate, useParams } from "react-router-dom";

import { QueryGate } from "../components/feedback/QueryGate";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
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

  async function onDelete() {
    if (
      !window.confirm(
        "Delete this design guide? Mockups that already used it will keep their saved copy.",
      )
    ) {
      return;
    }
    try {
      await remove.mutateAsync(guideId);
      notify("Design guide deleted.");
      navigate("/design-md");
    } catch (caught) {
      notify(apiErrorMessage(caught, "That design guide could not be deleted."), "danger");
    }
  }

  return (
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
                    void downloadDesignGuide(guide.data.id, guide.data.name).catch((caught: unknown) => {
                      notify(apiErrorMessage(caught, "The file could not be downloaded."), "danger");
                    });
                  }}
                >
                  Download
                </Button>
                <Button variant="secondary" onClick={() => void onDelete()} isLoading={remove.isPending}>
                  Delete
                </Button>
              </>
            }
          />
          <Card>
            <div className="flex flex-wrap gap-2">
              {guide.data.tags.length > 0 ? (
                guide.data.tags.map((tag) => <Badge key={tag}>{tag}</Badge>)
              ) : (
                <span className="text-small text-gray-500">No tags</span>
              )}
            </div>
            <p className="mt-3 text-small text-gray-600">Updated {formatWhen(guide.data.updated_at)}</p>
            <div className="mt-6">
              <MarkdownView source={guide.data.content} />
            </div>
            <p className="mt-6 text-small text-gray-500">
              <Link to="/design-md" className="text-primary-700">
                All guides
              </Link>
            </p>
          </Card>
        </>
      ) : null}
    </QueryGate>
  );
}
