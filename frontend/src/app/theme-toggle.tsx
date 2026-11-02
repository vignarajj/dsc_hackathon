"use client";

import { useSyncExternalStore } from "react";

type Choice = "system" | "light" | "dark";

const KEY = "theme";
const OPTIONS: readonly { id: Choice; label: string }[] = [
  { id: "system", label: "Auto" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
];

const listeners = new Set<() => void>();
// Kept in memory too, so the control still works when storage is blocked.
let current: Choice | null = null;

function readStored(): Choice {
  try {
    const value = window.localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

function snapshot(): Choice {
  return current ?? readStored();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

function choose(choice: Choice) {
  current = choice;
  const root = document.documentElement;
  if (choice === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", choice);
  }
  try {
    if (choice === "system") {
      window.localStorage.removeItem(KEY);
    } else {
      window.localStorage.setItem(KEY, choice);
    }
  } catch {
    // The choice still applies for this visit.
  }
  listeners.forEach((listener) => listener());
}

export function ThemeToggle() {
  const choice = useSyncExternalStore(subscribe, snapshot, () => "system" as Choice);
  return (
    <div
      role="group"
      aria-label="Colour theme"
      className="inline-flex rounded-full border border-line bg-paper p-0.5 text-xs"
    >
      {OPTIONS.map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={choice === option.id}
          onClick={() => choose(option.id)}
          className="rounded-full px-3 py-1 text-muted aria-pressed:bg-stamp aria-pressed:text-stamp-ink"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
