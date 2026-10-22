import { Sparkles, X } from "lucide-react";
import { Button } from "../ui/Button";

type HelpModalProps = {
  open: boolean;
  onClose: () => void;
};

const acquisitionSteps = [
  { step: "1. Find Businesses", detail: "Search Google Places, OpenStreetMap, Yelp, ePages, or run Apify actors to discover local business leads." },
  { step: "2. Qualify Leads", detail: "Examine lead score, contactability (email & phone), website status, and digital footprint." },
  { step: "3. Audit Website", detail: "Analyze performance (PageSpeed), mobile responsiveness, SEO, usability, and technical tags." },
  { step: "4. Research Business", detail: "Deep search using Tavily & Exa to discover positioning, competitors, gaps, and business signals." },
  { step: "5. Identify Opportunities", detail: "Pinpoint high-value service opportunities: website redesign, online booking, local SEO, mobile UX." },
  { step: "6. Generate Mockup", detail: "Create a modern, high-converting homepage mockup based on the prospect's brand and Design MD specs." },
  { step: "7. Prepare Outreach", detail: "Synthesize audit gaps, research intelligence, and mockup previews into a compelling Gemini-powered draft." },
  { step: "8. Manually Review & Send", detail: "Review and refine the draft in your acquisition workspace, then send directly via your connected Gmail account." },
  { step: "9. Follow Up & Convert", detail: "Manage structured follow-ups (overdue, today, upcoming) and track replies to close paying clients." },
];

export function HelpModal({ open, onClose }: HelpModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-100 bg-gradient-to-r from-primary-50/70 to-white px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary-600 text-white">
              <Sparkles className="size-4" />
            </div>
            <div>
              <h3 className="text-h4 font-bold text-ink">Client Acquisition Workflow</h3>
              <p className="text-caption text-gray-500">How to find, pitch, and win high-value clients</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto p-5 space-y-3">
          <p className="text-small text-gray-600">
            This tool is your personal <strong>Client Acquisition Operating System</strong>. Follow this structured process for every high-value prospect:
          </p>

          <div className="space-y-2 mt-3">
            {acquisitionSteps.map((item, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 rounded-xl border border-gray-100 bg-gray-50/70 p-3"
              >
                <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-caption font-bold text-primary-700">
                  {idx + 1}
                </div>
                <div>
                  <h4 className="text-small font-semibold text-ink">{item.step}</h4>
                  <p className="mt-0.5 text-caption text-gray-600 leading-relaxed">{item.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-gray-100 bg-gray-50 px-5 py-3">
          <span className="text-caption text-gray-500">Keyboard shortcut: Press Ctrl+K anytime</span>
          <Button variant="primary" className="h-8 px-3 text-small" onClick={onClose}>
            Got it
          </Button>
        </div>
      </div>
    </div>
  );
}
