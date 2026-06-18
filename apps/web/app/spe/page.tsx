"use client";

import { useState } from "react";
import { api, Permit } from "@/lib/api";

interface SPEInfo {
  permit_id: string;
  jupyter_url: string;
  status: string;
}

interface PermitWithSPE {
  permit: Permit;
  spe: SPEInfo | null;
  speLoading: boolean;
  speError: string | null;
}

function statusBadge(status: string) {
  const styles: Record<string, string> = {
    running: "bg-green-100 text-green-800",
    stopped: "bg-gray-100 text-gray-600",
    not_found: "bg-gray-100 text-gray-400",
    error: "bg-red-100 text-red-700",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status.replace("_", " ")}
    </span>
  );
}

export default function SPEPage() {
  const [username, setUsername] = useState("");
  const [items, setItems] = useState<PermitWithSPE[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const permits = await api.permits.listByHolder(username.trim());
      const granted = permits.filter((p) => p.state === "granted");

      const withSPE = await Promise.all(
        granted.map(async (permit): Promise<PermitWithSPE> => {
          try {
            const spe = await api.spe.status(permit.permit_id);
            return { permit, spe, speLoading: false, speError: null };
          } catch {
            return { permit, spe: null, speLoading: false, speError: null };
          }
        })
      );
      setItems(withSPE);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  async function launch(permitId: string) {
    setItems((prev) =>
      prev?.map((i) => i.permit.permit_id === permitId ? { ...i, speLoading: true, speError: null } : i) ?? null
    );
    try {
      const spe = await api.spe.launch(permitId);
      setItems((prev) =>
        prev?.map((i) => i.permit.permit_id === permitId ? { ...i, spe, speLoading: false } : i) ?? null
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Launch failed";
      setItems((prev) =>
        prev?.map((i) => i.permit.permit_id === permitId ? { ...i, speLoading: false, speError: msg } : i) ?? null
      );
    }
  }

  async function stop(permitId: string) {
    setItems((prev) =>
      prev?.map((i) => i.permit.permit_id === permitId ? { ...i, speLoading: true, speError: null } : i) ?? null
    );
    try {
      await api.spe.teardown(permitId);
      setItems((prev) =>
        prev?.map((i) => i.permit.permit_id === permitId ? { ...i, spe: null, speLoading: false } : i) ?? null
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Stop failed";
      setItems((prev) =>
        prev?.map((i) => i.permit.permit_id === permitId ? { ...i, speLoading: false, speError: msg } : i) ?? null
      );
    }
  }

  return (
    <div className="max-w-5xl">
      <div className="bg-blue-700 rounded-xl px-6 py-5 mb-8 text-white">
        <h1 className="text-2xl font-bold">My Secure Processing Environments</h1>
        <p className="text-blue-200 text-sm mt-1">
          Launch and manage JupyterLab environments for your granted permits.
        </p>
      </div>

      <form onSubmit={load} className="flex gap-3 mb-8 max-w-sm">
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Your username"
          className="flex-1 bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
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

      {items !== null && items.length === 0 && (
        <p className="text-gray-500 text-sm">No granted permits found for &quot;{username}&quot;.</p>
      )}

      {items && items.length > 0 && (
        <div className="flex flex-col gap-4">
          {items.map(({ permit, spe, speLoading, speError }) => {
            const isRunning = spe?.status === "running";
            return (
              <div key={permit.permit_id} className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {permit.purpose} - {permit.type}
                    </p>
                    <p className="text-xs text-gray-400 font-mono mt-0.5">{permit.permit_id}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {statusBadge(spe?.status ?? "not provisioned")}
                  </div>
                </div>

                <div className="px-5 py-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                  <div className="text-gray-500">Data domains</div>
                  <div className="text-gray-800">{permit.data_scope?.domains?.join(", ") || "-"}</div>
                  <div className="text-gray-500">Valid until</div>
                  <div className="text-gray-800">{permit.valid_until ?? "-"}</div>
                  <div className="text-gray-500">Format</div>
                  <div className="text-gray-800">{permit.format}</div>
                </div>

                <div className="px-5 py-3 border-t border-gray-100 flex items-center gap-3">
                  {speLoading ? (
                    <span className="text-sm text-gray-400">Working...</span>
                  ) : isRunning ? (
                    <>
                      <a
                        href={spe.jupyter_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="bg-blue-600 text-white rounded-lg px-4 py-1.5 text-sm hover:bg-blue-700"
                      >
                        Open JupyterLab
                      </a>
                      <button
                        onClick={() => stop(permit.permit_id)}
                        className="border border-red-300 text-red-600 rounded-lg px-4 py-1.5 text-sm hover:bg-red-50"
                      >
                        Stop SPE
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => launch(permit.permit_id)}
                      className="bg-blue-600 text-white rounded-lg px-4 py-1.5 text-sm hover:bg-blue-700"
                    >
                      Launch SPE
                    </button>
                  )}
                  {speError && <p className="text-red-600 text-xs">{speError}</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
