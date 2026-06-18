"use client";

import { useEffect, useState } from "react";
import { api, Dataset } from "@/lib/api";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.datasets
      .list()
      .then(setDatasets)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-gray-500 text-sm">Loading datasets...</p>;
  if (error) return <p className="text-red-600 text-sm">Error: {error}</p>;

  return (
    <div className="max-w-5xl">
      <div className="bg-blue-700 rounded-xl px-6 py-5 mb-8 text-white">
        <h1 className="text-2xl font-bold">Datasets</h1>
        <p className="text-blue-200 text-sm mt-1">Available OMOP health datasets and their coverage.</p>
      </div>
      <div className="flex flex-col gap-4">
        {datasets.map((d) => (
          <div key={d.id} className="border border-gray-200 rounded-lg shadow-sm">
            <button
              className="w-full text-left p-5"
              onClick={() => setExpanded(expanded === d.id ? null : d.id)}
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-base font-medium text-gray-900">{d.name}</h2>
                  <p className="text-sm text-gray-500 mt-1">{d.description}</p>
                </div>
                <span className="text-xs text-gray-400 ml-4 shrink-0">
                  {expanded === d.id ? "collapse" : "details"}
                </span>
              </div>
            </button>
            {expanded === d.id && (
              <div className="border-t border-gray-100 px-5 py-4 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-gray-500">Patients</span>
                  <p className="font-medium">{d.population_size?.toLocaleString() ?? "-"}</p>
                </div>
                <div>
                  <span className="text-gray-500">OMOP version</span>
                  <p className="font-medium">{d.omop_version ?? "5.4"}</p>
                </div>
                <div>
                  <span className="text-gray-500">Time range</span>
                  <p className="font-medium">
                    {d.time_range_from} - {d.time_range_until}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500">Domains</span>
                  <p className="font-medium">{d.domains?.join(", ") ?? "-"}</p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
