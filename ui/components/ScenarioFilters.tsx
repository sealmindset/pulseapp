"use client";

import { useEffect, useState } from "react";
import { useSession } from "@/components/SessionContext";

// PULSE Selling steps (P – Probe, U – Understand, L – Link, S – Simplify, E – Earn)
const STEPS = [
  "1: Probe",
  "2: Understand",
  "3: Link",
  "4: Simplify",
  "5: Earn",
];

const OBJECTIONS = ["Price (C2)", "Comfort", "Absent Partner"];
const FRAMEWORKS = ["CECAP", "LERA", "3T's"];

export default function ScenarioFilters() {
  const { filters, setFilters } = useSession();
  const [step, setStep] = useState<string>(filters.step ?? "");
  const [objection, setObjection] = useState<string>(filters.objection ?? "");
  const [framework, setFramework] = useState<string>(filters.framework ?? "");

  useEffect(() => {
    setFilters({ step, objection, framework });
  }, [step, objection, framework, setFilters]);

  return (
    <div className="space-y-3 rounded border border-gray-200 p-4">
      <div className="font-medium">Scenario Filters</div>
      <label className="block text-sm">
        <span className="text-gray-700">PULSE Step</span>
        <select
          className="mt-1 w-full rounded border border-gray-300 p-2"
          value={step}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setStep(e.target.value)}
        >
          <option value="">All</option>
          {STEPS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>

      <label className="block text-sm">
        <span className="text-gray-700">Objection Type</span>
        <select
          className="mt-1 w-full rounded border border-gray-300 p-2"
          value={objection}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setObjection(e.target.value)}
        >
          <option value="">All</option>
          {OBJECTIONS.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      </label>

      <label className="block text-sm">
        <span className="text-gray-700">Framework</span>
        <select
          className="mt-1 w-full rounded border border-gray-300 p-2"
          value={framework}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setFramework(e.target.value)}
        >
          <option value="">All</option>
          {FRAMEWORKS.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
      </label>
    </div>
  );
}
