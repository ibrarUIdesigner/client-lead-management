import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Textarea } from "../../components/ui/Textarea";
import { MarkdownView } from "../design-md/markdown";
import { useDesignGuide, useDesignGuides } from "../../hooks/useDesignGuides";
import { apiErrorMessage } from "../../lib/apiError";
import { cn, focusRing } from "../../lib/cn";
import { createMockupBrief } from "../../services/designGuides";
import type { MockupCreateWrite } from "../../types/designGuide";

type GuideMode = MockupCreateWrite["guide_mode"];

type CreateMockupDialogProps = {
  open: boolean;
  leadId: string;
  sourceMockupId?: string | null;
  savedGuideName?: string | null;
  onClose: () => void;
  onCreated: () => void;
};

export function CreateMockupDialog({
  open,
  leadId,
  sourceMockupId,
  savedGuideName,
  onClose,
  onCreated,
}: CreateMockupDialogProps) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<GuideMode>(savedGuideName ? "keep" : "none");
  const [guideId, setGuideId] = useState<string | null>(null);
  const [requirements, setRequirements] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const guides = useDesignGuides(mode === "selected" ? search : "", "");
  const selected = useDesignGuide(mode === "selected" ? (guideId ?? undefined) : undefined);

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
      await createMockupBrief({
        lead_id: leadId,
        requirements: requirements.trim() || null,
        source_mockup_id: sourceMockupId ?? null,
        design_guide_id: mode === "selected" ? guideId : null,
        guide_mode: mode,
      });
      await queryClient.invalidateQueries({ queryKey: ["mockups"] });
      onCreated();
    } catch (caught) {
      setError(apiErrorMessage(caught, "The mockup could not be saved."));
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      title={sourceMockupId ? "Regenerate mockup" : "Create mockup"}
      description="The brief uses the lead, checked audit findings, and your notes. A design guide only describes the look."
      onClose={onClose}
    >
      <div className="space-y-4">
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
        <Textarea
          label="Mockup requirements"
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
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => void onSubmit()} isLoading={saving}>
            Save brief
          </Button>
        </div>
      </div>
    </Modal>
  );
}
