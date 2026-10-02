import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import { MarkdownView } from "../design-md/markdown";
import { useDesignGuide, useDesignGuides } from "../../hooks/useDesignGuides";
import { useProviders } from "../../hooks/useHealth";
import { apiErrorMessage } from "../../lib/apiError";
import { cn, focusRing } from "../../lib/cn";
import { createMockup } from "../../services/mockups";
import type { GuideMode, MockupGoal, MockupProvider } from "../../types/mockup";

type CreateMockupDialogProps = {
  open: boolean;
  leadId: string;
  sourceMockupId?: string | null;
  savedGuideName?: string | null;
  defaultProvider?: MockupProvider;
  scenario?: "new_site" | "redesign" | null;
  onClose: () => void;
  onCreated: (mockupId: string) => void;
};

const GOAL_OPTIONS = [
  { value: "calls", label: "Phone calls" },
  { value: "whatsapp", label: "WhatsApp enquiries" },
  { value: "bookings", label: "Bookings" },
  { value: "quotes", label: "Quote requests" },
];

export function CreateMockupDialog({
  open,
  leadId,
  sourceMockupId,
  savedGuideName,
  defaultProvider,
  scenario,
  onClose,
  onCreated,
}: CreateMockupDialogProps) {
  const queryClient = useQueryClient();
  const providers = useProviders();
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<GuideMode>(savedGuideName ? "keep" : "none");
  const [guideId, setGuideId] = useState<string | null>(null);
  const [requirements, setRequirements] = useState("");
  const [provider, setProvider] = useState<MockupProvider>(defaultProvider ?? "gemini");
  const [goal, setGoal] = useState<MockupGoal>("calls");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const guides = useDesignGuides(mode === "selected" ? search : "", "");
  const selected = useDesignGuide(mode === "selected" ? (guideId ?? undefined) : undefined);

  const providerOptions = useMemo(() => {
    const snapshots = providers.data?.providers ?? [];
    return [
      {
        value: "gemini",
        label: providerLabel(snapshots.find((item) => item.id === "gemini"), "Gemini"),
      },
      {
        value: "groq",
        label: providerLabel(snapshots.find((item) => item.id === "groq"), "Groq"),
      },
    ];
  }, [providers.data]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setMode(savedGuideName ? "keep" : "none");
    setGuideId(null);
    setRequirements("");
    setGoal("calls");
    setFiles([]);
    setError(null);
    setSaving(false);
    const ready = providers.data?.providers.find((item) => item.configured);
    if (defaultProvider) {
      setProvider(defaultProvider);
    } else if (ready?.id === "groq" || ready?.id === "gemini") {
      setProvider(ready.id);
    }
  }, [open, savedGuideName, defaultProvider, providers.data]);

  async function onSubmit() {
    if (saving) {
      return;
    }
    setError(null);
    if (mode === "selected" && !guideId) {
      setError("Select a design guide.");
      return;
    }
    setSaving(true);
    try {
      const created = await createMockup(
        {
          lead_id: leadId,
          requirements: requirements.trim() || null,
          source_mockup_id: sourceMockupId ?? null,
          design_guide_id: mode === "selected" ? guideId : null,
          guide_mode: mode,
          provider,
          goal,
        },
        files,
      );
      await queryClient.invalidateQueries({ queryKey: ["mockups"] });
      onCreated(created.id);
    } catch (caught) {
      setError(apiErrorMessage(caught, "The mockup could not be started."));
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      title={sourceMockupId ? "Regenerate mockup" : "Create mockup"}
      description={
        scenario === "redesign"
          ? "Design score is below 50. Uses verified lead details, audit findings, and an optional Design MD guide."
          : scenario === "new_site"
            ? "No website on file. Uses the full verified business profile and an optional Design MD guide."
            : "Uses the lead, verified audit findings, optional Design MD guide, and your instructions. Generation stays on the server until you review it."
      }
      onClose={() => {
        if (!saving) {
          onClose();
        }
      }}
    >
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Select
            label="Provider"
            value={provider}
            options={providerOptions}
            onChange={(event) => {
              setProvider(event.target.value as MockupProvider);
            }}
          />
          <Select
            label="Main goal"
            value={goal}
            options={GOAL_OPTIONS}
            onChange={(event) => {
              setGoal(event.target.value as MockupGoal);
            }}
          />
        </div>
        <fieldset className="space-y-2">
          <legend className="text-small font-medium text-gray-700">Design guide</legend>
          {savedGuideName ? (
            <label className="flex items-start gap-2 text-body">
              <input
                type="radio"
                name="guide-mode"
                checked={mode === "keep"}
                onChange={() => setMode("keep")}
              />
              <span>Keep the saved copy of {savedGuideName}</span>
            </label>
          ) : null}
          <label className="flex items-start gap-2 text-body">
            <input
              type="radio"
              name="guide-mode"
              checked={mode === "selected"}
              onChange={() => setMode("selected")}
            />
            <span>{sourceMockupId ? "Use the current version of a guide" : "Select a guide"}</span>
          </label>
          <label className="flex items-start gap-2 text-body">
            <input
              type="radio"
              name="guide-mode"
              checked={mode === "none"}
              onChange={() => setMode("none")}
            />
            <span>No design guide</span>
          </label>
        </fieldset>
        {mode === "selected" ? (
          <div className="space-y-3">
            <label className="flex flex-col gap-2 text-small font-medium text-gray-700" htmlFor="guide-picker-search">
              Search guides
              <input
                id="guide-picker-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className={cn(
                  "h-10 rounded-control border border-gray-300 px-3 text-body font-normal",
                  focusRing,
                )}
              />
            </label>
            <div className="max-h-40 space-y-2 overflow-y-auto">
              {guides.data?.items.length ? (
                guides.data.items.map((guide) => (
                  <button
                    key={guide.id}
                    type="button"
                    onClick={() => setGuideId(guide.id)}
                    className={cn(
                      "block w-full rounded-control border px-3 py-2 text-left",
                      guideId === guide.id ? "border-primary-500 bg-primary-50" : "border-gray-200",
                    )}
                  >
                    <span className="font-medium text-ink">{guide.name}</span>
                    <span className="mt-1 block text-small text-gray-600">
                      {guide.description || "No description."}
                    </span>
                  </button>
                ))
              ) : (
                <p className="text-small text-gray-600">No guides match that search.</p>
              )}
            </div>
            {selected.data ? (
              <div className="max-h-48 overflow-y-auto rounded-control border border-gray-200 p-3">
                <MarkdownView source={selected.data.content} />
              </div>
            ) : null}
          </div>
        ) : null}
        <label className="flex flex-col gap-2 text-small font-medium text-gray-700">
          Logo or images
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            multiple
            onChange={(event) => {
              setFiles(Array.from(event.target.files ?? []).slice(0, 4));
            }}
          />
          <span className="font-normal text-gray-600">
            Optional. Up to 4 images, 1.5 MB each. Remote images are blocked in the preview.
          </span>
          {files.length > 0 ? (
            <span className="font-normal text-gray-700">
              {files.map((file) => file.name).join(", ")}
            </span>
          ) : null}
        </label>
        <Textarea
          label="Additional instructions"
          hint="Optional notes for this homepage. Business facts stay on the lead."
          value={requirements}
          onChange={(event) => setRequirements(event.target.value)}
        />
        {error ? (
          <p className="text-small text-danger" role="alert">
            {error}
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" disabled={saving} onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => void onSubmit()} isLoading={saving}>
            Generate mockup
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function providerLabel(
  snapshot: { configured: boolean; model: string; display_name: string | null } | undefined,
  name: string,
): string {
  if (!snapshot) {
    return name;
  }
  const model = snapshot.display_name || snapshot.model;
  if (!snapshot.configured) {
    return `${name} (not configured)`;
  }
  return model ? `${name} · ${model}` : name;
}
