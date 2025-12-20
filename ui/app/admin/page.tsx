"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import AgentsManager from "@/components/admin/AgentsManager";
import PromptsManager from "@/components/admin/PromptsManager";

export default function AdminPage() {
  const enable = (process.env.NEXT_PUBLIC_ENABLE_ADMIN === "true") && (process.env.NEXT_PUBLIC_ENV_NAME !== "prod");
  const [tab, setTab] = useState<"agents" | "prompts">("prompts");
  const banner = useMemo(() => enable ? "Dev Mode – no authentication enabled" : "Admin disabled in this environment", [enable]);
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Admin</h1>
        <Link 
          href="/admin/overview" 
          className="px-4 py-2 bg-black text-white rounded-lg text-sm hover:bg-gray-800 transition-colors"
        >
          View AI Components Overview →
        </Link>
      </div>
      <div className={`rounded border p-2 text-sm ${enable ? "border-yellow-200 bg-yellow-50 text-yellow-800" : "border-gray-200 bg-gray-50 text-gray-700"}`}>{banner}</div>
      {enable ? (
        <>
          <div className="flex gap-2">
            <button onClick={() => setTab("prompts")} className={`rounded px-3 py-1 text-sm ${tab === "prompts" ? "bg-black text-white" : "border border-gray-300"}`}>Prompts</button>
            <button onClick={() => setTab("agents")} className={`rounded px-3 py-1 text-sm ${tab === "agents" ? "bg-black text-white" : "border border-gray-300"}`}>Agents</button>
          </div>
          <div>
            {tab === "prompts" ? <PromptsManager /> : <AgentsManager />}
          </div>
        </>
      ) : (
        <div className="text-sm text-gray-600">Set NEXT_PUBLIC_ENABLE_ADMIN=true and NEXT_PUBLIC_ENV_NAME!=prod to enable in dev.</div>
      )}
    </div>
  );
}
