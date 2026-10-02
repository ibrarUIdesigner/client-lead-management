import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import { useToast } from "../../components/feedback/useToast";
import { apiErrorMessage } from "../../lib/apiError";
import { cn } from "../../lib/cn";
import {
  downloadMockupHtml,
  downloadMockupScreenshot,
  getMockup,
  mockupScreenshotUrl,
  refineMockup,
  retryMockup,
  retryMockupScreenshots,
} from "../../services/mockups";
import type { MockupProvider } from "../../types/mockup";

type MockupDetailDialogProps = {
  open: boolean;
  mockupId: string | null;
  onClose: () => void;
  onOpenCreate?: (provider?: MockupProvider) => void;
};

export function MockupDetailDialog({
  open,
  mockupId,
  onClose,
  onOpenCreate,
}: MockupDetailDialogProps) {
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const [viewport, setViewport] = useState<"desktop" | "mobile">("desktop");
  const [instructions, setInstructions] = useState("");
  const [provider, setProvider] = useState<MockupProvider>("gemini");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const detail = useQuery({
    queryKey: ["mockup", mockupId],
    queryFn: () => getMockup(mockupId!),
    enabled: open && Boolean(mockupId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const shots = query.state.data?.screenshot_status;
      if (status === "GENERATING" || status === "PENDING" || shots === "PENDING") {
        return 2000;
      }
      return false;
    },
  });

  useEffect(() => {
    if (detail.data?.provider === "groq" || detail.data?.provider === "gemini") {
      setProvider(detail.data.provider);
    }
  }, [detail.data?.provider]);

  useEffect(() => {
    if (detail.data?.status === "READY" || detail.data?.status === "FAILED") {
      void queryClient.invalidateQueries({ queryKey: ["mockups"] });
    }
  }, [detail.data?.status, detail.data?.screenshot_status, queryClient]);

  const item = detail.data;
  const preparing = item?.status === "GENERATING" || item?.status === "PENDING";
  const failed = item?.status === "FAILED";

  async function onRefine() {
    if (!mockupId || busy || !instructions.trim()) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await refineMockup(mockupId, {
        instructions: instructions.trim(),
        provider,
      });
      setInstructions("");
      notify("Refinement started. A new version will appear when ready.", "success");
      await queryClient.invalidateQueries({ queryKey: ["mockups"] });
      await queryClient.invalidateQueries({ queryKey: ["mockup", created.id] });
      onClose();
    } catch (caught) {
      setError(apiErrorMessage(caught, "Refinement could not be started."));
    } finally {
      setBusy(false);
    }
  }

  async function onRetry(nextProvider: MockupProvider) {
    if (!mockupId || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await retryMockup(mockupId, { provider: nextProvider });
      notify(
        nextProvider === item?.provider
          ? "Retry started."
          : `Retry started with ${nextProvider === "gemini" ? "Gemini" : "Groq"}.`,
        "success",
      );
      await detail.refetch();
      await queryClient.invalidateQueries({ queryKey: ["mockups"] });
    } catch (caught) {
      setError(apiErrorMessage(caught, "Retry could not be started."));
    } finally {
      setBusy(false);
    }
  }

  async function onRetryShots() {
    if (!mockupId || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await retryMockupScreenshots(mockupId);
      notify("Screenshot capture restarted.", "success");
      await detail.refetch();
    } catch (caught) {
      setError(apiErrorMessage(caught, "Screenshot retry could not be started."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      size="xl"
      title={item ? `${item.title || "Homepage concept"} · v${item.version}` : "Mockup"}
      description="Review the generated homepage before using it in outreach. Nothing is emailed or published automatically."
      onClose={onClose}
    >
      <div className="space-y-4">
        {detail.isPending ? <p className="text-body text-gray-600">Loading mockup…</p> : null}
        {detail.isError ? (
          <p className="text-small text-danger" role="alert">
            {apiErrorMessage(detail.error, "This mockup could not be loaded.")}
          </p>
        ) : null}
        {item ? (
          <>
            <div className="flex flex-wrap gap-2 text-small text-gray-600">
              <span>Status: {item.status}</span>
              {item.provider ? <span>· {item.provider}</span> : null}
              {item.model_name ? <span>· {item.model_name}</span> : null}
              {item.goal ? <span>· Goal: {item.goal}</span> : null}
              {item.design_guide_name ? <span>· Guide: {item.design_guide_name}</span> : null}
            </div>
            {item.notes ? <p className="text-small text-gray-600">{item.notes}</p> : null}
            {preparing ? (
              <div className="rounded-control border border-gray-200 bg-gray-50 px-4 py-8 text-center text-body text-gray-600">
                Generating homepage and capturing screenshots…
              </div>
            ) : null}
            {failed ? (
              <div className="space-y-3 rounded-control border border-danger/30 bg-red-50 px-4 py-4">
                <p className="text-body text-danger">{item.notes || "Generation failed."}</p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    disabled={busy}
                    onClick={() => void onRetry((item.provider as MockupProvider) || "gemini")}
                  >
                    Retry
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() =>
                      void onRetry(item.provider === "gemini" ? "groq" : "gemini")
                    }
                  >
                    Switch provider
                  </Button>
                  {onOpenCreate ? (
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={() => onOpenCreate(item.provider === "groq" ? "groq" : "gemini")}
                    >
                      New mockup
                    </Button>
                  ) : null}
                </div>
              </div>
            ) : null}
            {item.has_html && !preparing ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant={viewport === "desktop" ? "primary" : "secondary"}
                    onClick={() => setViewport("desktop")}
                  >
                    Desktop
                  </Button>
                  <Button
                    variant={viewport === "mobile" ? "primary" : "secondary"}
                    onClick={() => setViewport("mobile")}
                  >
                    Mobile
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => void downloadMockupHtml(item.id)}
                  >
                    Download HTML
                  </Button>
                  {item.has_desktop_screenshot ? (
                    <Button
                      variant="secondary"
                      onClick={() => void downloadMockupScreenshot(item.id, "desktop")}
                    >
                      Desktop PNG
                    </Button>
                  ) : null}
                  {item.has_mobile_screenshot ? (
                    <Button
                      variant="secondary"
                      onClick={() => void downloadMockupScreenshot(item.id, "mobile")}
                    >
                      Mobile PNG
                    </Button>
                  ) : null}
                </div>
                <div className="overflow-hidden rounded-control border border-gray-200 bg-gray-100">
                  {item.has_desktop_screenshot || item.has_mobile_screenshot ? (
                    <img
                      src={mockupScreenshotUrl(
                        item.id,
                        viewport === "mobile" ? "mobile" : "desktop",
                      )}
                      alt={`${viewport} mockup screenshot`}
                      className={cn(
                        "mx-auto bg-white",
                        viewport === "mobile" ? "max-w-[390px]" : "w-full",
                      )}
                    />
                  ) : null}
                  <div
                    className={cn(
                      "mx-auto bg-white",
                      viewport === "mobile" ? "max-w-[390px]" : "w-full",
                    )}
                  >
                    <iframe
                      title="Mockup preview"
                      sandbox=""
                      referrerPolicy="no-referrer"
                      srcDoc={item.preview_html || item.html_content || ""}
                      className={cn(
                        "w-full border-0 bg-white",
                        viewport === "mobile" ? "h-[640px]" : "h-[720px]",
                      )}
                    />
                  </div>
                </div>
                {item.screenshot_status === "FAILED" ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-small text-gray-600">
                      Screenshots failed. The HTML mockup was kept.
                    </p>
                    <Button variant="secondary" disabled={busy} onClick={() => void onRetryShots()}>
                      Retry screenshots
                    </Button>
                  </div>
                ) : null}
                {item.status === "READY" ? (
                  <div className="space-y-3 border-t border-gray-100 pt-4">
                    <Select
                      label="Provider for refinement"
                      value={provider}
                      options={[
                        { value: "gemini", label: "Gemini" },
                        { value: "groq", label: "Groq" },
                      ]}
                      onChange={(event) => {
                        setProvider(event.target.value as MockupProvider);
                      }}
                    />
                    <Textarea
                      label="Refinement"
                      hint='Example: "improve hero spacing" or "make the contact button more visible." Saves a new version.'
                      value={instructions}
                      onChange={(event) => setInstructions(event.target.value)}
                    />
                    <Button
                      disabled={busy || !instructions.trim()}
                      isLoading={busy}
                      onClick={() => void onRefine()}
                    >
                      Save refinement as new version
                    </Button>
                  </div>
                ) : null}
              </>
            ) : null}
          </>
        ) : null}
        {error ? (
          <p className="text-small text-danger" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}
