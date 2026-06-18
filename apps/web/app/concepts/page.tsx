"use client";

import { useState } from "react";
import { api, Concept, CountResult } from "@/lib/api";

const DOMAINS = ["", "Condition", "Drug", "Measurement", "Visit"];

export default function ConceptsPage() {
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("");
  const [results, setResults] = useState<Concept[]>([]);
  const [counts, setCounts] = useState<Record<number, CountResult | string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResults([]);
    setCounts({});
    try {
      const data = await api.concepts.search(query.trim(), domain || undefined);
      setResults(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function fetchCount(conceptId: number) {
    setCounts((prev) => ({ ...prev, [conceptId]: "loading..." }));
    try {
      const result = await api.counts.get(conceptId);
      setCounts((prev) => ({ ...prev, [conceptId]: result }));
    } catch {
      setCounts((prev) => ({ ...prev, [conceptId]: "error" }));
    }
  }

  return (
    <div className="max-w-5xl">
      <div className="bg-blue-700 rounded-xl px-6 py-5 mb-8 text-white"><h1 className="text-2xl font-bold">Concept Search</h1><p className="text-blue-200 text-sm mt-1">Search OMOP vocabulary and view suppressed patient counts.</p></div>
      <form onSubmit={search} className="flex gap-3 mb-6">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. diabetes, metformin"
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
        />
        <select
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
        >
          {DOMAINS.map((d) => (
            <option key={d} value={d}>
              {d || "All domains"}
            </option>
          ))}
        </select>
        <button
          type="submit"
          className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-blue-700"
        >
          Search
        </button>
      </form>

      {loading && <p className="text-gray-500 text-sm">Searching...</p>}
      {error && <p className="text-red-600 text-sm">Error: {error}</p>}

      {results.length > 0 && (
        <div className="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-blue-600 border-b border-blue-700">
              <tr>
                <th className="text-left px-4 py-2 text-white font-medium">Concept ID</th>
                <th className="text-left px-4 py-2 text-white font-medium">Name</th>
                <th className="text-left px-4 py-2 text-white font-medium">Vocabulary</th>
                <th className="text-left px-4 py-2 text-white font-medium">Domain</th>
                <th className="text-left px-4 py-2 text-white font-medium">Patient count</th>
              </tr>
            </thead>
            <tbody>
              {results.map((c, i) => {
                const countEntry = counts[c.concept_id];
                const countDisplay =
                  countEntry === undefined
                    ? null
                    : countEntry === "loading..."
                      ? "loading..."
                      : countEntry === "error"
                        ? "error"
                        : typeof countEntry === "object"
                          ? String(countEntry.patient_count)
                          : String(countEntry);

                return (
                  <tr
                    key={c.concept_id}
                    className={`${i % 2 === 0 ? "bg-white" : "bg-gray-50"} border-b border-gray-100`}
                  >
                    <td className="px-4 py-2 font-mono text-gray-500">{c.concept_id}</td>
                    <td className="px-4 py-2 text-gray-900">{c.concept_name}</td>
                    <td className="px-4 py-2 text-gray-500">{c.vocabulary_id}</td>
                    <td className="px-4 py-2 text-gray-500">{c.domain_id}</td>
                    <td className="px-4 py-2">
                      {countDisplay !== null ? (
                        <span className="font-medium">{countDisplay}</span>
                      ) : (
                        <button
                          onClick={() => fetchCount(c.concept_id)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          fetch count
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
