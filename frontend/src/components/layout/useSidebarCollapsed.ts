import { useSyncExternalStore } from "react";

const STORAGE_KEY = "clm.sidebar-collapsed";

const listeners = new Set<() => void>();

function readCollapsed() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

let collapsed = typeof window === "undefined" ? false : readCollapsed();

function emit() {
  listeners.forEach((listener) => {
    listener();
  });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setSidebarCollapsed(next: boolean) {
  collapsed = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
  } catch {
    // Private browsing can block storage. The in-memory value still applies.
  }
  emit();
}

export function useSidebarCollapsed() {
  const value = useSyncExternalStore(
    subscribe,
    () => collapsed,
    () => false,
  );

  return {
    collapsed: value,
    setCollapsed: setSidebarCollapsed,
    toggle() {
      setSidebarCollapsed(!collapsed);
    },
  };
}
