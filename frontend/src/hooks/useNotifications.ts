import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteNotification,
  fetchNotificationPreferences,
  fetchNotifications,
  fetchPushPublicKey,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
  sendTestPush,
  subscribeToPush,
  unsubscribeFromPush,
  updateNotificationPreferences,
} from "../services/notifications";
import type { NotificationPreferencesUpdate } from "../types/notification";

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function useNotifications(params?: {
  is_read?: boolean;
  type?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ["notifications", params],
    queryFn: () => fetchNotifications(params),
    refetchInterval: 15_000,
  });
}

export function useUnreadNotificationsCount() {
  return useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: fetchUnreadCount,
    refetchInterval: 12_000,
  });
}

export function useNotificationPreferences() {
  return useQuery({
    queryKey: ["notifications", "preferences"],
    queryFn: fetchNotificationPreferences,
  });
}

export function useNotificationActions() {
  const queryClient = useQueryClient();

  const markRead = useMutation({
    mutationFn: (id: string) => markNotificationRead(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const removeNotification = useMutation({
    mutationFn: (id: string) => deleteNotification(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const updatePreferences = useMutation({
    mutationFn: (data: NotificationPreferencesUpdate) => updateNotificationPreferences(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications", "preferences"] });
    },
  });

  const triggerTestPush = useMutation({
    mutationFn: sendTestPush,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  return {
    markRead,
    markAllRead,
    removeNotification,
    updatePreferences,
    triggerTestPush,
  };
}

export function useBrowserPush() {
  const queryClient = useQueryClient();
  const [permission, setPermission] = useState<NotificationPermission>(
    typeof Notification !== "undefined" ? Notification.permission : "default",
  );
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPushSupported =
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window;

  // Check current subscription on mount
  useEffect(() => {
    if (!isPushSupported) return;

    let mounted = true;
    navigator.serviceWorker.ready
      .then((registration) => registration.pushManager.getSubscription())
      .then((subscription) => {
        if (mounted) {
          setIsSubscribed(Boolean(subscription));
        }
      })
      .catch((err) => {
        console.warn("Failed to check push subscription:", err);
      });

    return () => {
      mounted = false;
    };
  }, [isPushSupported]);

  const enablePush = async (): Promise<boolean> => {
    if (!isPushSupported) {
      setError("Push notifications are not supported in this browser.");
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      // 1. Request user permission
      const result = await Notification.requestPermission();
      setPermission(result);

      if (result !== "granted") {
        setError(
          result === "denied"
            ? "Notification permission was blocked in browser settings."
            : "Notification permission was dismissed.",
        );
        setIsLoading(false);
        return false;
      }

      // 2. Fetch VAPID public key
      const keyData = await fetchPushPublicKey();
      if (!keyData.configured || !keyData.public_key) {
        setError("Push service is not configured on the server (VAPID key missing).");
        setIsLoading(false);
        return false;
      }

      // 3. Register service worker if needed
      await navigator.serviceWorker.register("/sw.js");
      const registration = await navigator.serviceWorker.ready;

      // 4. Create push subscription
      const applicationServerKey = urlBase64ToUint8Array(keyData.public_key);
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey as unknown as BufferSource,
      });

      const subJson = subscription.toJSON();
      const p256dh = subJson.keys?.p256dh || "";
      const auth = subJson.keys?.auth || "";

      if (!p256dh || !auth) {
        throw new Error("Push subscription did not provide client encryption keys.");
      }

      // 5. Send subscription to backend
      const deviceName = `${navigator.platform || "Desktop"} (${navigator.userAgent.includes("Chrome") ? "Chrome" : "Browser"})`;
      await subscribeToPush({
        endpoint: subscription.endpoint,
        keys: { p256dh, auth },
        device_name: deviceName,
      });

      setIsSubscribed(true);
      void queryClient.invalidateQueries({ queryKey: ["notifications", "preferences"] });
      setIsLoading(false);
      return true;
    } catch (err: any) {
      console.error("Push subscription error:", err);
      setError(err?.message || "Could not complete push subscription.");
      setIsLoading(false);
      return false;
    }
  };

  const disablePush = async (): Promise<boolean> => {
    if (!isPushSupported) return false;

    setIsLoading(true);
    setError(null);

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        await unsubscribeFromPush(subscription.endpoint);
        await subscription.unsubscribe();
      }

      setIsSubscribed(false);
      void queryClient.invalidateQueries({ queryKey: ["notifications", "preferences"] });
      setIsLoading(false);
      return true;
    } catch (err: any) {
      console.error("Push unsubscription error:", err);
      setError(err?.message || "Could not unsubscribe from push.");
      setIsLoading(false);
      return false;
    }
  };

  return {
    isPushSupported,
    permission,
    isSubscribed,
    isLoading,
    error,
    enablePush,
    disablePush,
  };
}
