"use client";

import { useState } from "react";
import { api } from "@/lib/api";

const PURPOSES = ["public_health", "policy", "statistics", "education", "research", "innovation"];
const ALL_DOMAINS = ["Condition", "Drug", "Measurement", "Visit"];

type Step = 1 | 2 | 3;

interface FormState {
  accessType: "request" | "permit";
  purpose: string;
  domains: string[];
  conceptIds: string;
  timeFrom: string;
  timeUntil: string;
  format: "anonymized" | "pseudonymized";
  pseudoJustification: string;
  namedUsers: string;
  username: string;
}

const initialForm: FormState = {
  accessType: "request",
  purpose: "research",
  domains: ["Condition"],
  conceptIds: "",
  timeFrom: "2000-01-01",
  timeUntil: "2026-01-01",
  format: "anonymized",
  pseudoJustification: "",
  namedUsers: "",
  username: "",
};

export default function ApplyPage() {
  const [step, setStep] = useState<Step>(1);
  const [form, setForm] = useState<FormState>(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [successId, setSuccessId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function toggleDomain(d: string) {
    setForm((f) => ({
      ...f,
      domains: f.domains.includes(d) ? f.domains.filter((x) => x !== d) : [...f.domains, d],
    }));
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const conceptIds = form.conceptIds
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map(Number)
        .filter((n) => !isNaN(n));

      const permit = await api.permits.create({
        type: form.accessType,
        holder: form.username,
        named_users: form.namedUsers
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        purpose: form.purpose,
        data_scope: {
          domains: form.domains,
          concept_ids: conceptIds,
          time_window_from: form.timeFrom,
          time_window_until: form.timeUntil,
        },
        format: form.format,
        pseudonymization_justification:
          form.format === "pseudonymized" ? form.pseudoJustification || null : null,
      });

      await api.permits.submit(permit.permit_id, form.username);
      setSuccessId(permit.permit_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (successId) {
    return (
      <div className="max-w-4xl">
        <h1 className="text-2xl font-semibold mb-4">Application Submitted</h1>
        <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm">
          <p className="text-sm text-gray-600 mb-2">Your application has been submitted for review.</p>
          <p className="text-sm text-gray-500">
            Permit ID: <span className="font-mono text-gray-900">{successId}</span>
          </p>
        </div>
        <button
          onClick={() => { setSuccessId(null); setForm(initialForm); setStep(1); }}
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          Submit another
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl">
      <div className="bg-blue-700 rounded-xl px-6 py-5 mb-8 text-white"><h1 className="text-2xl font-bold">Apply for Data Access</h1><p className="text-blue-200 text-sm mt-1">EHDS Article 67 - data access application.</p></div>

      <div className="flex gap-2 mb-8">
        {([1, 2, 3] as Step[]).map((s) => (
          <div key={s} className="flex items-center gap-2">
            <span
              className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${s === step
                ? "bg-blue-600 text-white"
                : s < step
                  ? "bg-blue-100 text-blue-700"
                  : "border border-gray-300 text-gray-400"
                }`}
            >
              {s}
            </span>
            <span className="text-xs text-gray-500">
              {s === 1 ? "Purpose" : s === 2 ? "Data scope" : "Format & users"}
            </span>
            {s < 3 && <span className="text-gray-300 text-xs">-</span>}
          </div>
        ))}
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5 shadow-sm space-y-4">
        {step === 1 && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Access type</label>
              <div className="flex gap-4">
                {(["request", "permit"] as const).map((t) => (
                  <label key={t} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input
                      type="radio"
                      value={t}
                      checked={form.accessType === t}
                      onChange={() => setForm((f) => ({ ...f, accessType: t }))}
                    />
                    {t === "request" ? "Request (aggregated counts only)" : "Permit (SPE access)"}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Purpose (EHDS Article 53)
              </label>
              <select
                value={form.purpose}
                onChange={(e) => setForm((f) => ({ ...f, purpose: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              >
                {PURPOSES.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <button
              onClick={() => setStep(2)}
              className="w-full bg-blue-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-blue-700"
            >
              Next
            </button>
          </>
        )}

        {step === 2 && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Data domains</label>
              <div className="flex flex-wrap gap-2">
                {ALL_DOMAINS.map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => toggleDomain(d)}
                    className={`px-3 py-1 rounded-full text-xs border ${form.domains.includes(d)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "border-gray-300 text-gray-600 hover:border-blue-400"
                      }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Concept IDs (comma-separated)
              </label>
              <input
                type="text"
                value={form.conceptIds}
                onChange={(e) => setForm((f) => ({ ...f, conceptIds: e.target.value }))}
                placeholder="e.g. 201826 (Type 2 Diabetes), 316866 (Hypertension)"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">Time from</label>
                <input
                  type="date"
                  value={form.timeFrom}
                  onChange={(e) => setForm((f) => ({ ...f, timeFrom: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                />
              </div>
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">Time until</label>
                <input
                  type="date"
                  value={form.timeUntil}
                  onChange={(e) => setForm((f) => ({ ...f, timeUntil: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setStep(1)}
                className="flex-1 border border-gray-300 text-gray-700 rounded-lg px-4 py-2 text-sm hover:bg-gray-50"
              >
                Back
              </button>
              <button
                onClick={() => setStep(3)}
                disabled={form.domains.length === 0}
                className="flex-1 bg-blue-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Data format</label>
              <div className="flex gap-4">
                {(["anonymized", "pseudonymized"] as const).map((f) => (
                  <label key={f} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input
                      type="radio"
                      value={f}
                      checked={form.format === f}
                      onChange={() => setForm((prev) => ({ ...prev, format: f }))}
                    />
                    {f}
                  </label>
                ))}
              </div>
            </div>
            {form.format === "pseudonymized" && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Justification for pseudonymization
                </label>
                <textarea
                  value={form.pseudoJustification}
                  onChange={(e) => setForm((f) => ({ ...f, pseudoJustification: e.target.value }))}
                  rows={3}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                />
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Named users (comma-separated)
              </label>
              <input
                type="text"
                value={form.namedUsers}
                onChange={(e) => setForm((f) => ({ ...f, namedUsers: e.target.value }))}
                placeholder="researcher1, researcher2"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Your username</label>
              <input
                type="text"
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                placeholder="your username"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </div>
            {error && <p className="text-red-600 text-sm">{error}</p>}
            <div className="flex gap-2">
              <button
                onClick={() => setStep(2)}
                className="flex-1 border border-gray-300 text-gray-700 rounded-lg px-4 py-2 text-sm hover:bg-gray-50"
              >
                Back
              </button>
              <button
                onClick={submit}
                disabled={submitting || !form.username.trim()}
                className="flex-1 bg-blue-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? "Submitting..." : "Submit Application"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
