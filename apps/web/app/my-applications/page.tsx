"use client";

import { useState } from "react";
import { api, Permit } from "@/lib/api";

const STATE_STYLES: Record<string, string> = {
  granted: "bg-green-100 text-green-800",
  refused: "bg-red-100 text-red-800",
  submitted: "bg-yellow-100 text-yellow-800",
  under_review: "bg-blue-100 text-blue-800",
  draft: "bg-gray-100 text-gray-600",
  expired: "bg-gray-200 text-gray-500",
};

export default function MyApplicationsPage() {
  const [username, setUsername] = useState("");
  const [permits, setPermits] = useState<Permit[] | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.permits.listByHolder(username.trim());
      setPermits(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-5xl">
      <div className="bg-blue-700 rounded-xl px-6 py-5 mb-8 text-white"><h1 className="text-2xl font-bold">My Applications</h1><p className="text-blue-200 text-sm mt-1">Track your data access permit applications.</p></div>
      <form onSubmit={load} className="flex gap-3 mb-6 max-w-sm">
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Your username"
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
        />
        <button
          type="submit"
          className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-blue-700"
        >
          Load
        </button>
      </form>

      {loading && <p className="text-gray-500 text-sm">Loading...</p>}
      {error && <p className="text-red-600 text-sm">Error: {error}</p>}

      {permits !== null && permits.length === 0 && (
        <p className="text-gray-500 text-sm">No applications found for &quot;{username}&quot;.</p>
      )}

      {permits && permits.length > 0 && (
        <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-blue-600 border-b border-blue-700">
              <tr>
                <th className="text-left px-4 py-2 text-white font-medium">ID</th>
                <th className="text-left px-4 py-2 text-white font-medium">Purpose</th>
                <th className="text-left px-4 py-2 text-white font-medium">Type</th>
                <th className="text-left px-4 py-2 text-white font-medium">State</th>
                <th className="text-left px-4 py-2 text-white font-medium">Submitted</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {permits.map((p, i) => (
                <>
                  <tr
                    key={p.permit_id}
                    className={`${i % 2 === 0 ? "bg-white" : "bg-gray-50"} border-b border-gray-100`}
                  >
                    <td className="px-4 py-2 font-mono text-gray-500">{p.permit_id.slice(0, 8)}…</td>
                    <td className="px-4 py-2 text-gray-900">{p.purpose}</td>
                    <td className="px-4 py-2 text-gray-500">{p.type}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATE_STYLES[p.state] ?? "bg-gray-100 text-gray-600"
                          }`}
                      >
                        {p.state}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500">{p.created_at.slice(0, 10)}</td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => setExpanded(expanded === p.permit_id ? null : p.permit_id)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        {expanded === p.permit_id ? "hide" : "details"}
                      </button>
                    </td>
                  </tr>
                  {expanded === p.permit_id && (
                    <tr key={`${p.permit_id}-detail`} className="bg-gray-50 border-b border-gray-100">
                      <td colSpan={6} className="px-4 py-4">
                        <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm max-w-2xl">
                          <div className="text-gray-500">Permit ID</div>
                          <div className="font-mono text-gray-800">{p.permit_id}</div>

                          <div className="text-gray-500">Holder</div>
                          <div className="text-gray-800">{p.holder}</div>

                          {p.named_users.length > 0 && <>
                            <div className="text-gray-500">Named users</div>
                            <div className="text-gray-800">{p.named_users.join(", ")}</div>
                          </>}

                          <div className="text-gray-500">Access type</div>
                          <div className="text-gray-800">{p.type}</div>

                          <div className="text-gray-500">Purpose</div>
                          <div className="text-gray-800">{p.purpose}</div>

                          <div className="text-gray-500">Format</div>
                          <div className="text-gray-800">{p.format}</div>

                          {p.pseudonymization_justification && <>
                            <div className="text-gray-500">Pseudonymization justification</div>
                            <div className="text-gray-800">{p.pseudonymization_justification}</div>
                          </>}

                          <div className="text-gray-500">Data domains</div>
                          <div className="text-gray-800">{(p.data_scope?.domains ?? []).join(", ") || "-"}</div>

                          {(p.data_scope?.concept_ids ?? []).length > 0 && <>
                            <div className="text-gray-500">Concept IDs</div>
                            <div className="text-gray-800">{p.data_scope.concept_ids.join(", ")}</div>
                          </>}

                          <div className="text-gray-500">Time window</div>
                          <div className="text-gray-800">{p.data_scope?.time_window_from} - {p.data_scope?.time_window_until}</div>

                          {p.valid_from && <>
                            <div className="text-gray-500">Valid</div>
                            <div className="text-gray-800">{p.valid_from} - {p.valid_until}</div>
                          </>}

                          {p.reviewer_comment && <>
                            <div className="text-gray-500">Reviewer comment</div>
                            <div className="text-gray-800">{p.reviewer_comment}</div>
                          </>}

                          <div className="text-gray-500">OMOP snapshot</div>
                          <div className="text-gray-800">{p.omop_snapshot}</div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
