"use client";

import { type KeyboardEvent, type ReactNode, useRef, useState } from "react";

export type Tab = { id: string; label: string; panel: ReactNode };

/** WAI-ARIA tabs: arrow keys move between tabs, Home and End jump to the ends. */
export function ResultTabs({ tabs, label }: { tabs: readonly Tab[]; label: string }) {
  const [selected, setSelected] = useState(tabs[0]?.id ?? "");
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({});

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const last = tabs.length - 1;
    const next =
      event.key === "ArrowRight"
        ? (index + 1) % tabs.length
        : event.key === "ArrowLeft"
          ? (index - 1 + tabs.length) % tabs.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : null;
    if (next === null) {
      return;
    }
    event.preventDefault();
    const id = tabs[next].id;
    setSelected(id);
    buttons.current[id]?.focus();
  }

  return (
    <div className="flex flex-col gap-4">
      <div
        role="tablist"
        aria-label={label}
        className="flex gap-1 overflow-x-auto rounded-full border border-line bg-paper p-1"
      >
        {tabs.map((tab, index) => {
          const isSelected = tab.id === selected;
          return (
            <button
              key={tab.id}
              ref={(element) => {
                buttons.current[tab.id] = element;
              }}
              type="button"
              role="tab"
              id={`tab-${tab.id}`}
              aria-selected={isSelected}
              aria-controls={`panel-${tab.id}`}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => setSelected(tab.id)}
              onKeyDown={(event) => onKeyDown(event, index)}
              className={`shrink-0 rounded-full px-4 py-1.5 text-sm transition-colors ${
                isSelected ? "bg-stamp text-stamp-ink" : "text-muted hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`panel-${tab.id}`}
          aria-labelledby={`tab-${tab.id}`}
          hidden={tab.id !== selected}
          tabIndex={0}
        >
          {tab.panel}
        </div>
      ))}
    </div>
  );
}
