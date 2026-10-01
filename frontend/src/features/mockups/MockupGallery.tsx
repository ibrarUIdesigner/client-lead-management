import { useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/feedback/EmptyState";
import { QueryGate } from "../../components/feedback/QueryGate";
import { useToast } from "../../components/feedback/useToast";
import { StatusBadge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { useMockups } from "../../hooks/useWorkspace";
import { cn, focusRing } from "../../lib/cn";
import type { MockupItem } from "../../types/workspace";
import { CreateMockupDialog } from "./CreateMockupDialog";

type MockupGalleryProps = {
  leadId?: string;
};

export function MockupGallery({ leadId }: MockupGalleryProps) {
  const mockups = useMockups(leadId);

  return (
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
              ? "Homepage concepts for this lead will show up here."
              : "Homepage concepts for a prospect will show up here."
          }
        />
      ) : null}
      {mockups.data && mockups.data.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {mockups.data.map((item) => (
            <MockupCard key={item.id} item={item} />
          ))}
        </div>
      ) : null}
    </QueryGate>
  );
}

function MockupCard({ item }: { item: MockupItem }) {
  const color = swatch(item.primary_color);
  const preparing = item.status === "PENDING" || item.status === "GENERATING";
  const [open, setOpen] = useState(false);
  const { notify } = useToast();

  return (
    <article className="overflow-hidden rounded-card border border-gray-200 bg-white">
      {preparing ? (
        <div className="flex h-44 items-center justify-center bg-gray-50 px-4 text-center text-small text-gray-600">
          A homepage concept is being prepared.
        </div>
      ) : (
        <div className="bg-gray-100 p-4">
          <div className="rounded-control bg-white p-4 shadow-sm">
            <div className="h-2 w-16 rounded-full" style={{ backgroundColor: color }} />
            <p className="mt-4 text-h4 font-semibold text-ink">{item.business_name}</p>
            <p className="mt-1 text-small text-gray-600">A clearer homepage, with one next step.</p>
            <span
              className="mt-4 inline-flex rounded-control px-3 py-1.5 text-caption font-medium text-white"
              style={{ backgroundColor: color }}
            >
              Get in touch
            </span>
          </div>
        </div>
      )}
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
              {[item.city, item.title, `Version ${item.version}`].filter(Boolean).join(" · ")}
            </p>
          </div>
          <StatusBadge status={item.status} />
        </div>
        {item.design_guide_name ? (
          <p className="text-small text-gray-600">Design guide: {item.design_guide_name}</p>
        ) : null}
        {item.notes ? <p className="text-small text-gray-600">{item.notes}</p> : null}
        <Button
          variant="secondary"
          onClick={() => {
            setOpen(true);
          }}
        >
          Regenerate
        </Button>
        {open ? (
          <CreateMockupDialog
            open
            leadId={item.lead_id}
            sourceMockupId={item.id}
            savedGuideName={item.design_guide_name}
            onClose={() => {
              setOpen(false);
            }}
            onCreated={() => {
              notify("Mockup brief saved. No image was generated.", "success");
              setOpen(false);
            }}
          />
        ) : null}
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
