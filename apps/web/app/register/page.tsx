"use client";

import { useEffect, useState } from "react";
import { api, Permit } from "@/lib/api";

export default function RegisterPage() {
  const [permits, setPermits] = useState<Permit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.permits.register()
      .then(setPermits)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load register"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-5xl">
      <div className="bg-blue-700 rounded-xl px-6 py-5 mb-8 text-white"><h1 className="text-2xl font-bold">Public Permit Register</h1><p className="text-blue-200 text-sm mt-1">All currently granted permits - EHDS Article 68(4).</p></div>
      <p className="text-sm text-gray-500 mb-6">
        All currently granted data access permits - published in accordance with EHDS Article 68(4).
      </p>

      {loading && <p className="text-gray-500 text-sm">Loading...</p>}
      {error && <p className="text-red-600 text-sm">Error: {error}</p>}

      {!loading && !error && permits.length === 0 && (
        <p className="text-gray-500 text-sm">No granted permits at this time.</p>
      )}

      {permits.length > 0 && (
        <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-blue-600 border-b border-blue-700">
              <tr>
                <th className="text-left px-4 py-2 text-white font-medium">Permit ID</th>
                <th className="text-left px-4 py-2 text-white font-medium">Purpose</th>
                <th className="text-left px-4 py-2 text-white font-medium">Type</th>
                <th className="text-left px-4 py-2 text-white font-medium">Format</th>
                <th className="text-left px-4 py-2 text-white font-medium">Valid from</th>
                <th className="text-left px-4 py-2 text-white font-medium">Valid until</th>
                <th className="text-left px-4 py-2 text-white font-medium">Domains</th>
              </tr>
            </thead>
            <tbody>
              {permits.map((p, i) => (
                <tr
                  key={p.permit_id}
                  className={`${i % 2 === 0 ? "bg-white" : "bg-gray-50"} border-b border-gray-100`}
                >
                  <td className="px-4 py-2 font-mono text-gray-500">{p.permit_id.slice(0, 8)}…</td>
                  <td className="px-4 py-2 text-gray-900">{p.purpose}</td>
                  <td className="px-4 py-2 text-gray-500">{p.type}</td>
                  <td className="px-4 py-2 text-gray-500">{p.format}</td>
                  <td className="px-4 py-2 text-gray-500">{p.valid_from ?? "-"}</td>
                  <td className="px-4 py-2 text-gray-500">{p.valid_until ?? "-"}</td>
                  <td className="px-4 py-2 text-gray-500">
                    {p.data_scope?.domains?.join(", ") ?? "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
