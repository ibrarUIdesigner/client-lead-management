// Service Worker for Client Acquisition Tool Web Push Notifications
/* eslint-disable no-restricted-globals */

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      data = { title: "Notification", body: event.data.text() };
    }
  }

  const title = data.title || "Client Acquisition Tool";
  const body = data.body || "You have a new update.";
  const url = data.url || "/notifications";
  const icon = "/favicon.svg";

  const options = {
    body,
    icon,
    badge: icon,
    tag: data.id || `notif-${data.leadId || Date.now()}`,
    renotify: true,
    data: {
      url,
      leadId: data.leadId,
      id: data.id,
      type: data.type,
    },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const targetUrl = (event.notification.data && event.notification.data.url) || "/notifications";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      // If there is an open window/tab, focus it and navigate
      for (const client of clientList) {
        if ("focus" in client) {
          if ("navigate" in client) {
            client.navigate(targetUrl);
          }
          return client.focus();
        }
      }
      // If no window is currently open, open a new one
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })
  );
});
