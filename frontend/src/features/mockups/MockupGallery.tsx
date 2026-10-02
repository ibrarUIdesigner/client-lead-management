import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "../../components/feedback/EmptyState";
import { QueryGate } from "../../components/feedback/QueryGate";
import { useToast } from "../../components/feedback/useToast";
import { StatusBadge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { useMockups } from "../../hooks/useWorkspace";
import { cn, focusRing } from "../../lib/cn";
import { getMockupEligibility, mockupScreenshotUrl } from "../../services/mockups";
import type { MockupProvider } from "../../types/mockup";
import type { MockupItem } from "../../types/workspace";
import { CreateMockupDialog } from "./CreateMockupDialog";
import { MockupDetailDialog } from "./MockupDetailDialog";

type MockupGalleryProps = {
  leadId?: string;
};

export function MockupGallery({ leadId }: MockupGalleryProps) {
  const mockups = useMockups(leadId);
  const eligibility = useQuery({
    queryKey: ["mockup-eligibility", leadId],
    queryFn: () => getMockupEligibility(leadId!),
    enabled: Boolean(leadId),
  });
  const { notify } = useToast();
  const [creating, setCreating] = useState(false);
  const [createProvider, setCreateProvider] = useState<MockupProvider | undefined>();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [regenerateFrom, setRegenerateFrom] = useState<MockupItem | null>(null);

  const canCreate = Boolean(leadId && eligibility.data?.allowed);
  const eligibilityMessage = eligibility.data?.message;

  return (
    <div className="space-y-4">
      {leadId ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-2xl text-small text-gray-600">
            {eligibility.isPending ? (
              <p>Checking whether a mockup can be created…</p>
            ) : eligibilityMessage ? (
              <p>{eligibilityMessage}</p>
            ) : null}
            <p className="mt-1">
              Mockups are for businesses with no website, or websites with a design score below 50.
            </p>
          </div>
          <Button
            disabled={!canCreate}
            onClick={() => {
              setCreateProvider(undefined);
              setCreating(true);
            }}
          >
            Create mockup
          </Button>
        </div>
      ) : null}
      <QueryGate
        pending={mockups.isPending}
        error={mockups.error}
        onRetry={() => {
          void mockups.refetch();
        }}
        fallback="Mockups could not be loaded."
      >
        {mockups.data && mockups.data.length === 0 ? (
          <EmptyState
            title="No mockups yet"
            description={
              leadId
                ? canCreate
                  ? "Generate a homepage from verified business details and an optional Design MD guide."
                  : eligibilityMessage ||
                    "This lead is not eligible for a mockup yet."
                : "Homepage concepts for a prospect will show up here."
            }
            action={
              leadId && canCreate ? (
                <Button
                  onClick={() => {
                    setCreating(true);
                  }}
                >
                  Create mockup
                </Button>
              ) : undefined
            }
          />
        ) : null}
        {mockups.data && mockups.data.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {mockups.data.map((item) => (
              <MockupCard
                key={item.id}
                item={item}
                onOpen={() => setActiveId(item.id)}
                onRegenerate={
                  canCreate
                    ? () => setRegenerateFrom(item)
                    : undefined
                }
              />
            ))}
          </div>
        ) : null}
      </QueryGate>
      {leadId && creating ? (
        <CreateMockupDialog
          open
          leadId={leadId}
          scenario={eligibility.data?.scenario ?? undefined}
          defaultProvider={createProvider}
          onClose={() => setCreating(false)}
          onCreated={(id) => {
            notify("Mockup generation started.", "success");
            setCreating(false);
            setActiveId(id);
            void mockups.refetch();
            void eligibility.refetch();
          }}
        />
      ) : null}
      {regenerateFrom && canCreate ? (
        <CreateMockupDialog
          open
          leadId={regenerateFrom.lead_id}
          sourceMockupId={regenerateFrom.id}
          savedGuideName={regenerateFrom.design_guide_name}
          scenario={eligibility.data?.scenario ?? undefined}
          defaultProvider={
            regenerateFrom.provider === "groq" || regenerateFrom.provider === "gemini"
              ? regenerateFrom.provider
              : undefined
          }
          onClose={() => setRegenerateFrom(null)}
          onCreated={(id) => {
            notify("New mockup version started.", "success");
            setRegenerateFrom(null);
            setActiveId(id);
            void mockups.refetch();
          }}
        />
      ) : null}
      <MockupDetailDialog
        open={Boolean(activeId)}
        mockupId={activeId}
        onClose={() => setActiveId(null)}
        onOpenCreate={
          canCreate
            ? (provider) => {
                setActiveId(null);
                setCreateProvider(provider);
                setCreating(true);
              }
            : undefined
        }
      />
    </div>
  );
}

function MockupCard({
  item,
  onOpen,
  onRegenerate,
}: {
  item: MockupItem;
  onOpen: () => void;
  onRegenerate?: () => void;
}) {
  const preparing = item.status === "PENDING" || item.status === "GENERATING";
  const failed = item.status === "FAILED";
  const color = swatch(item.primary_color);

  return (
    <article className="overflow-hidden rounded-card border border-gray-200 bg-white">
      <button type="button" onClick={onOpen} className={cn("block w-full text-left", focusRing)}>
        {preparing ? (
          <div className="flex h-44 items-center justify-center bg-gray-50 px-4 text-center text-small text-gray-600">
            Generating homepage…
          </div>
        ) : failed ? (
          <div className="flex h-44 items-center justify-center bg-red-50 px-4 text-center text-small text-danger">
            Generation failed. Open to retry or switch provider.
          </div>
        ) : item.has_desktop_screenshot ? (
          <img
            src={mockupScreenshotUrl(item.id, "desktop")}
            alt=""
            className="h-44 w-full object-cover object-top bg-gray-100"
          />
        ) : (
          <div className="bg-gray-100 p-4">
            <div className="rounded-control bg-white p-4 shadow-sm">
              <div className="h-2 w-16 rounded-full" style={{ backgroundColor: color }} />
              <p className="mt-4 text-h4 font-semibold text-ink">{item.business_name}</p>
              <p className="mt-1 text-small text-gray-600">
                {item.has_html ? "HTML ready · screenshots pending or failed" : "Homepage concept"}
              </p>
            </div>
          </div>
        )}
      </button>
      <div className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Link
              to={`/leads/${item.lead_id}`}
              className={cn("font-semibold text-ink hover:text-primary-700", focusRing)}
            >
              {item.business_name}
            </Link>
            <p className="text-small text-gray-600">
              {[item.city, item.title, `Version ${item.version}`, item.provider]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <StatusBadge status={item.status} />
        </div>
        {item.design_guide_name ? (
          <p className="text-small text-gray-600">Design guide: {item.design_guide_name}</p>
        ) : null}
        {item.notes ? <p className="line-clamp-2 text-small text-gray-600">{item.notes}</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={onOpen}>
            Open
          </Button>
          {onRegenerate ? (
            <Button variant="secondary" onClick={onRegenerate}>
              Regenerate
            </Button>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function swatch(color: string | null): string {
  if (color && /^#[0-9a-f]{6}$/i.test(color)) {
    return color;
  }
  return "#4f46e5";
}
