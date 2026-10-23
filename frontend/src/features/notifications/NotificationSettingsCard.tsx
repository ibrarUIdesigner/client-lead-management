import {
  Bell,
  BellOff,
  CheckCircle2,
  AlertCircle,
  Send,
} from "lucide-react";

import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { Switch } from "../../components/ui/Switch";
import { LoadingState } from "../../components/feedback/LoadingState";
import { useToast } from "../../components/feedback/useToast";
import {
  useBrowserPush,
  useNotificationActions,
  useNotificationPreferences,
} from "../../hooks/useNotifications";

export function NotificationSettingsCard() {
  const { notify } = useToast();
  const {
    isPushSupported,
    permission,
    isSubscribed,
    isLoading: isPushLoading,
    error: pushError,
    enablePush,
    disablePush,
  } = useBrowserPush();

  const preferencesQuery = useNotificationPreferences();
  const { updatePreferences, triggerTestPush } = useNotificationActions();

  const prefs = preferencesQuery.data?.preferences ?? {};

  const handleTogglePush = async () => {
    if (isSubscribed) {
      const ok = await disablePush();
      if (ok) {
        notify("Browser notifications disabled on this device.", "info");
      }
    } else {
      const ok = await enablePush();
      if (ok) {
        notify("Browser push notifications successfully enabled!", "success");
      }
    }
  };

  const handleSendTest = () => {
    triggerTestPush.mutate(undefined, {
      onSuccess: () => {
        notify("Test notification dispatched! Check your desktop notifications.", "success");
      },
      onError: (err: any) => {
        notify(err?.message || "Failed to trigger test push.", "danger");
      },
    });
  };

  const handlePreferenceChange = (key: string, enabled: boolean) => {
    updatePreferences.mutate(
      {
        preferences: {
          ...prefs,
          [key]: enabled,
        },
      },
      {
        onSuccess: () => {
          notify("Notification preferences updated.", "success");
        },
        onError: () => {
          notify("Failed to update preferences.", "danger");
        },
      },
    );
  };

  return (
    <div className="space-y-6">
      {/* Browser Push Connection Card */}
      <Card>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-h3 font-semibold text-ink">Browser Notifications</h2>
              {isSubscribed ? (
                <Badge tone="green">● Enabled</Badge>
              ) : permission === "denied" ? (
                <Badge tone="red">Blocked in browser</Badge>
              ) : (
                <Badge tone="gray">○ Disabled</Badge>
              )}
            </div>
            <p className="mt-1.5 text-body leading-relaxed text-gray-600 max-w-2xl">
              Receive instant desktop/browser notifications when a prospect replies to an outreach
              email, requests a meeting, or raises an objection — even if this tab is closed.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {isSubscribed ? (
              <Button
                variant="secondary"
                onClick={handleSendTest}
                isLoading={triggerTestPush.isPending}
                className="gap-1.5 h-9 text-small px-3"
                title="Send a sample push to this browser"
              >
                <Send className="size-3.5" />
                <span>Test Notification</span>
              </Button>
            ) : null}

            <Button
              variant={isSubscribed ? "secondary" : "primary"}
              onClick={handleTogglePush}
              isLoading={isPushLoading}
              disabled={!isPushSupported || permission === "denied"}
              className="gap-1.5 h-9 text-small px-3"
            >
              {isSubscribed ? (
                <>
                  <BellOff className="size-4" />
                  <span>Disable Notifications</span>
                </>
              ) : (
                <>
                  <Bell className="size-4" />
                  <span>Enable Notifications</span>
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Error / Warning states */}
        {!isPushSupported ? (
          <div className="mt-4 flex items-center gap-2 rounded-control bg-amber-50 p-3 text-small text-amber-800">
            <AlertCircle className="size-4 shrink-0" />
            <span>
              Web Push is not supported in this browser. Please use Chrome, Edge, Brave, or Firefox.
            </span>
          </div>
        ) : permission === "denied" ? (
          <div className="mt-4 flex items-center gap-2 rounded-control bg-red-50 p-3 text-small text-red-800">
            <AlertCircle className="size-4 shrink-0" />
            <span>
              Notification permission was blocked in this browser. Click the site settings lock icon
              in your URL address bar to reset permissions to &ldquo;Allow&rdquo;.
            </span>
          </div>
        ) : pushError ? (
          <div className="mt-4 flex items-center gap-2 rounded-control bg-red-50 p-3 text-small text-red-800">
            <AlertCircle className="size-4 shrink-0" />
            <span>{pushError}</span>
          </div>
        ) : isSubscribed ? (
          <div className="mt-4 flex items-center gap-2 rounded-control bg-emerald-50 p-3 text-small text-emerald-800">
            <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />
            <span>
              Active Web Push subscription registered with Service Worker. You will receive real-time
              prospect reply notifications.
            </span>
          </div>
        ) : null}
      </Card>

      {/* Notification Preferences Card */}
      <Card>
        <div>
          <h2 className="text-h3 font-semibold text-ink">Notification Preferences</h2>
          <p className="mt-1 text-body leading-relaxed text-gray-600">
            Choose which sales activities generate in-app alerts and browser notifications.
          </p>
        </div>

        {preferencesQuery.isLoading ? (
          <div className="mt-4">
            <LoadingState label="Loading preferences" framed={false} />
          </div>
        ) : (
          <div className="mt-5 divide-y divide-gray-100">
            <PreferenceRow
              title="Email Replies"
              description="Inbound emails received from prospective leads."
              checked={prefs.email_replies ?? true}
              onChange={(val) => handlePreferenceChange("email_replies", val)}
            />
            <PreferenceRow
              title="Interested Replies"
              description="AI classified replies showing positive interest or asking to see mockups."
              checked={prefs.interested_replies ?? true}
              badge="🔥 High Priority"
              onChange={(val) => handlePreferenceChange("interested_replies", val)}
            />
            <PreferenceRow
              title="Meeting Requests"
              description="Prospects requesting a phone call, Zoom meeting, or calendar appointment."
              checked={prefs.meeting_requests ?? true}
              badge="📅 Urgent"
              onChange={(val) => handlePreferenceChange("meeting_requests", val)}
            />
            <PreferenceRow
              title="Objections & Pricing"
              description="Prospects asking about rates, costs, or expressing initial objections."
              checked={prefs.objections ?? true}
              onChange={(val) => handlePreferenceChange("objections", val)}
            />
            <PreferenceRow
              title="Follow-ups Due"
              description="Scheduled follow-up reminders that become due today."
              checked={prefs.followups_due ?? true}
              onChange={(val) => handlePreferenceChange("followups_due", val)}
            />
            <PreferenceRow
              title="Mockup Complete"
              description="When an AI redesign website concept finishes generating."
              checked={prefs.mockups_ready ?? true}
              onChange={(val) => handlePreferenceChange("mockups_ready", val)}
            />
            <PreferenceRow
              title="Research Complete"
              description="Tavily and Exa background company research completions."
              checked={prefs.research_complete ?? false}
              onChange={(val) => handlePreferenceChange("research_complete", val)}
            />
            <PreferenceRow
              title="Audit Complete"
              description="Website crawler and PageSpeed Lighthouse audits."
              checked={prefs.audit_complete ?? false}
              onChange={(val) => handlePreferenceChange("audit_complete", val)}
            />
            <PreferenceRow
              title="Apify Complete"
              description="Apify dataset actor imports and runs."
              checked={prefs.apify_complete ?? false}
              onChange={(val) => handlePreferenceChange("apify_complete", val)}
            />
          </div>
        )}
      </Card>
    </div>
  );
}

function PreferenceRow({
  title,
  description,
  checked,
  badge,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  badge?: string;
  onChange: (val: boolean) => void;
}) {
  return (
    <div className="py-2.5">
      <Switch label={title} checked={checked} onCheckedChange={onChange} />
      <div className="flex items-center gap-2 -mt-2">
        <p className="text-caption text-gray-500">{description}</p>
        {badge ? (
          <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-semibold text-gray-700">
            {badge}
          </span>
        ) : null}
      </div>
    </div>
  );
}

