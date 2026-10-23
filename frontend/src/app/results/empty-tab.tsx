import type { ReactNode } from "react";

export function EmptyTab({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2 rounded-3xl border border-line bg-paper p-5">
      <h2 className="font-display text-2xl font-normal">{title}</h2>
      <p className="max-w-prose text-sm text-muted">{children}</p>
    </section>
  );
}
