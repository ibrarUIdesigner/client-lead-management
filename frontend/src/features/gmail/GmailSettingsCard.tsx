import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useToast } from "../../components/feedback/useToast";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import {
  useConnectGmail,
  useDisconnectGmail,
  useGmailStatus,
  useSyncGmail,
} from "../../hooks/useGmail";
import { apiErrorMessage } from "../../lib/apiError";
import { formatWhen } from "../../lib/format";

export function GmailSettingsCard() {
  const { notify } = useToast();
  const [params, setParams] = useSearchParams();
  const status = useGmailStatus();
  const connect = useConnectGmail();
  const disconnect = useDisconnectGmail();
  const sync = useSyncGmail();
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    const result = params.get("gmail");
    if (!result) {
      return;
    }
    const messages: Record<string, { text: string; tone: "success" | "danger" }> = {
      connected: { text: "Gmail connected.", tone: "success" },
      denied: { text: "Gmail connection was cancelled.", tone: "danger" },
      invalid: { text: "Gmail connection returned an incomplete response.", tone: "danger" },
      invalid_state: { text: "Gmail connection expired. Try Connect again.", tone: "danger" },
      error: { text: "Gmail connection failed. Check the OAuth client settings.", tone: "danger" },
      missing_refresh: {
        text: "Google did not return a refresh token. Revoke access in Google Account and reconnect.",
        tone: "danger",
      },
    };
    const message = messages[result];
    if (message) {
      notify(message.text, message.tone);
    }
    const next = new URLSearchParams(params);
    next.delete("gmail");
    setParams(next, { replace: true });
    void status.refetch();
  }, [notify, params, setParams, status]);

  const data = status.data;

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-h4 font-semibold text-ink">Gmail</h2>
          <p className="mt-1 text-body text-gray-600">
            Send outreach from this workspace and sync replies into lead records.
          </p>
        </div>
        {data ? <ConnectionBadge data={data} /> : null}
      </div>

      <dl className="mt-4 space-y-3">
        <div>
          <dt className="text-caption font-semibold text-gray-500">OAuth client</dt>
          <dd className="mt-1 text-body text-ink">
            {data?.configured ? "Configured on the API" : "Add Google OAuth env vars and restart"}
          </dd>
        </div>
        <div>
          <dt className="text-caption font-semibold text-gray-500">Account</dt>
          <dd className="mt-1 text-body text-ink">{data?.email ?? "Not connected"}</dd>
        </div>
        <div>
          <dt className="text-caption font-semibold text-gray-500">Last sync</dt>
          <dd className="mt-1 text-body text-ink">
            {data?.last_synced_at ? formatWhen(data.last_synced_at) : "Never"}
          </dd>
        </div>
        {data?.last_error ? (
          <div>
            <dt className="text-caption font-semibold text-gray-500">Last error</dt>
            <dd className="mt-1 text-body text-gray-700">{data.last_error}</dd>
          </div>
        ) : null}
      </dl>

      <div className="mt-5 flex flex-wrap gap-2">
        {!data?.connected || data.needs_reauth ? (
          <Button
            disabled={!data?.configured || connect.isPending}
            isLoading={connect.isPending}
            onClick={() => {
              connect.mutate(undefined, {
                onSuccess: ({ authorization_url }) => {
                  window.location.href = authorization_url;
                },
                onError: (error) => {
                  notify(apiErrorMessage(error, "Could not start Gmail connection."), "danger");
                },
              });
            }}
          >
            {data?.needs_reauth ? "Reconnect Gmail" : "Connect Gmail"}
          </Button>
        ) : null}
        {data?.connected && !data.needs_reauth ? (
          <>
            <Button
              variant="secondary"
              isLoading={sync.isPending}
              onClick={() => {
                sync.mutate(undefined, {
                  onSuccess: (result) => {
                    notify(
                      `Synced ${result.processed} message${result.processed === 1 ? "" : "s"}.`,
                      "success",
                    );
                  },
                  onError: (error) => {
                    notify(apiErrorMessage(error, "Gmail sync failed."), "danger");
                  },
                });
              }}
            >
              Sync now
            </Button>
            {!confirming ? (
              <Button
                variant="secondary"
                onClick={() => {
                  setConfirming(true);
                }}
              >
                Disconnect
              </Button>
            ) : (
              <>
                <Button
                  isLoading={disconnect.isPending}
                  onClick={() => {
                    disconnect.mutate(undefined, {
                      onSuccess: () => {
                        notify("Gmail disconnected.", "success");
                        setConfirming(false);
                      },
                      onError: (error) => {
                        notify(apiErrorMessage(error, "Could not disconnect Gmail."), "danger");
                      },
                    });
                  }}
                >
                  Confirm disconnect
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setConfirming(false);
                  }}
                >
                  Cancel
                </Button>
              </>
            )}
          </>
        ) : null}
      </div>
      <p className="mt-3 text-small text-gray-600">
        Setup notes are in docs/GMAIL.md. Redirect URI must match
        GOOGLE_OAUTH_REDIRECT_URI on the API.
      </p>
    </Card>
  );
}

function ConnectionBadge({
  data,
}: {
  data: {
    configured: boolean;
    connected: boolean;
    needs_reauth: boolean;
  };
}) {
  if (!data.configured) {
    return <Badge tone="orange">Not configured</Badge>;
  }
  if (data.needs_reauth) {
    return <Badge tone="orange">Needs reauthorization</Badge>;
  }
  if (data.connected) {
    return <Badge tone="green">Connected</Badge>;
  }
  return <Badge>Not connected</Badge>;
}
