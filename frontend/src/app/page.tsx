import { Cleaner } from "@/app/cleaner";

export default function Home() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  return <Cleaner apiBase={apiBase} />;
}
