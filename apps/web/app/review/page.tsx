"use client";

import { useState, useEffect, useCallback } from "react";
import { api, Permit } from "@/lib/api";

const STATE_STYLES: Record<string, string> = {
  submitted: "bg-yellow-100 text-yellow-800",
  under_review: "bg-blue-100 text-blue-800",
  granted: "bg-green-100 text-green-800",
  refused: "bg-red-100 text-red-800",
  draft: "bg-gray-100 text-gray-600",
  expired: "bg-gray-200 text-gray-500",
};

function defaultGrantDates() {
  const from = new Date().toISOString().slice(0, 10);
  const until = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  return { validFrom: from, validUntil: until };
}

type ActionPanel = { type: "grant" | "refuse"; validFrom: string; validUntil: string; comment: string } | null;

export default function ReviewPage() {
  const [reviewer, setReviewer] = useState("");
  const [reviewerInput, setReviewerInput] = useState("");
  const [permits, setPermits] = useState<Permit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [actionPanel, setActionPanel] = useState<Record<string, ActionPanel>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  const loadPermits = useCallback(async () => {
    if (!reviewer) return;
    setLoading(true);
    setError(null);
    try {
      const [submitted, underReview] = await Promise.all([
        api.permits.listByState("submitted"),
        api.permits.listByState("under_review"),
      ]);
      setPermits([...submitted, ...underReview]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [reviewer]);

  useEffect(() => { loadPermits(); }, [loadPermits]);

  function login(e: React.FormEvent) {
    e.preventDefault();
    if (reviewerInput.trim()) setReviewer(reviewerInput.trim());
  }

  function setPanel(permitId: string, panel: ActionPanel) {
    setActionPanel((prev) => ({ ...prev, [permitId]: panel }));
  }

  async function startReview(permitId: string) {
    setBusy((b) => ({ ...b, [permitId]: true }));
    try {
      const updated = await api.permits.startReview(permitId, reviewer);
      setPermits((prev) => prev.map((p) => p.permit_id === permitId ? updated : p));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy((b) => ({ ...b, [permitId]: false }));
    }
  }

  async function grant(permitId: string) {
    const panel = actionPanel[permitId];
    if (!panel || panel.type !== "grant") return;
    setBusy((b) => ({ ...b, [permitId]: true }));
    try {
      const updated = await api.permits.grant(permitId, reviewer, panel.validFrom, panel.validUntil);
      setPermits((prev) => prev.map((p) => p.permit_id === permitId ? updated : p));
      setPanel(permitId, null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Grant failed");
    } finally {
      setBusy((b) => ({ ...b, [permitId]: false }));
    }
  }

  async function refuse(permitId: string) {
    const panel = actionPanel[permitId];
    if (!panel || panel.type !== "refuse") return;
    setBusy((b) => ({ ...b, [permitId]: true }));
    try {
      const updated = await api.permits.refuse(permitId, reviewer, panel.comment);
      setPermits((prev) => prev.map((p) => p.permit_id === permitId ? updated : p));
      setPanel(permitId, null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Refuse failed");
    } finally {
      setBusy((b) => ({ ...b, [permitId]: false }));
    }
  }

  if (!reviewer) {
    return (
      <div className="max-w-2xl">
        <div className="bg-blue-700 rounded-xl px-6 py-5 mb-8 text-white">
          <h1 className="text-2xl font-bold">Reviewer Dashboard</h1>
          <p className="text-blue-200 text-sm mt-1">Review and decide on submitted data access permit applications.</p>
        </div>
        <form onSubmit={login} className="flex gap-3 max-w-sm">
          <input
            type="text"
            value={reviewerInput}
            onChange={(e) => setReviewerInput(e.target.value)}
            placeholder="Reviewer username"
            className="flex-1 bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
          />
          <button type="submit" className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-blue-700">
            Enter
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="max-w-5xl">
      <div className="bg-blue-700 rounded-xl px-6 py-5 mb-8 text-white flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">Reviewer Dashboard</h1>
          <p className="text-blue-200 text-sm mt-1">Reviewing as <span className="font-medium text-white">{reviewer}</span></p>
        </div>
        <button onClick={() => setReviewer("")} className="text-blue-300 text-sm hover:text-white mt-1">
          Switch user
        </button>
      </div>

      {loading && <p className="text-gray-500 text-sm mb-4">Loading...</p>}
      {error && <p className="text-red-600 text-sm mb-4">Error: {error}</p>}

      {!loading && permits.length === 0 && (
        <p className="text-gray-500 text-sm">No pending applications.</p>
      )}

      {permits.length > 0 && (
        <div className="flex flex-col gap-4">
          {permits.map((p) => {
            const panel = actionPanel[p.permit_id] ?? null;
            const isBusy = busy[p.permit_id] ?? false;
            const isExpanded = expanded === p.permit_id;

            return (
              <div key={p.permit_id} className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                {/* Header row */}
                <div className="px-5 py-4 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATE_STYLES[p.state] ?? "bg-gray-100 text-gray-600"}`}>
                      {p.state.replace("_", " ")}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{p.holder}</p>
                      <p className="text-xs text-gray-400">{p.purpose} - {p.type} - {p.format}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400 font-mono">{p.permit_id.slice(0, 8)}...</span>
                    <button
                      onClick={() => setExpanded(isExpanded ? null : p.permit_id)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      {isExpanded ? "hide" : "details"}
                    </button>
                  </div>
                </div>

                {/* Details */}
                {isExpanded && (
                  <div className="px-5 pb-4 border-t border-gray-100 pt-3 grid grid-cols-2 gap-x-8 gap-y-1.5 text-sm">
                    <div className="text-gray-500">Permit ID</div>
                    <div className="font-mono text-gray-800 text-xs">{p.permit_id}</div>
                    <div className="text-gray-500">Data domains</div>
                    <div className="text-gray-800">{(p.data_scope?.domains ?? []).join(", ") || "-"}</div>
                    <div className="text-gray-500">Time window</div>
                    <div className="text-gray-800">{p.data_scope?.time_window_from} - {p.data_scope?.time_window_until}</div>
                    {(p.data_scope?.concept_ids ?? []).length > 0 && <>
                      <div className="text-gray-500">Concept IDs</div>
                      <div className="text-gray-800">{p.data_scope.concept_ids.join(", ")}</div>
                    </>}
                    {p.pseudonymization_justification && <>
                      <div className="text-gray-500">Pseudonymization justification</div>
                      <div className="text-gray-800">{p.pseudonymization_justification}</div>
                    </>}
                    <div className="text-gray-500">Submitted</div>
                    <div className="text-gray-800">{p.created_at.slice(0, 10)}</div>
                  </div>
                )}

                {/* Actions */}
                <div className="px-5 py-3 border-t border-gray-100 flex flex-col gap-3">
                  {isBusy ? (
                    <span className="text-sm text-gray-400">Working...</span>
                  ) : (
                    <>
                      <div className="flex gap-2">
                        {p.state === "submitted" && (
                          <button
                            onClick={() => startReview(p.permit_id)}
                            className="bg-blue-600 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-blue-700"
                          >
                            Start Review
                          </button>
                        )}
                        {p.state === "under_review" && !panel && (
                          <>
                            <button
                              onClick={() => setPanel(p.permit_id, { type: "grant", ...defaultGrantDates(), comment: "" })}
                              className="bg-green-600 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-green-700"
                            >
                              Grant
                            </button>
                            <button
                              onClick={() => setPanel(p.permit_id, { type: "refuse", validFrom: "", validUntil: "", comment: "" })}
                              className="border border-red-300 text-red-600 rounded-lg px-3 py-1.5 text-sm hover:bg-red-50"
                            >
                              Refuse
                            </button>
                          </>
                        )}
                      </div>

                      {/* Grant panel */}
                      {panel?.type === "grant" && (
                        <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex flex-col gap-3">
                          <p className="text-sm font-medium text-green-800">Grant permit - set validity period</p>
                          <div className="flex gap-3 flex-wrap">
                            <div>
                              <label className="block text-xs text-gray-500 mb-1">Valid from</label>
                              <input
                                type="date"
                                value={panel.validFrom}
                                onChange={(e) => setPanel(p.permit_id, { ...panel, validFrom: e.target.value })}
                                className="border border-gray-300 rounded px-2 py-1 text-sm"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-gray-500 mb-1">Valid until</label>
                              <input
                                type="date"
                                value={panel.validUntil}
                                onChange={(e) => setPanel(p.permit_id, { ...panel, validUntil: e.target.value })}
                                className="border border-gray-300 rounded px-2 py-1 text-sm"
                              />
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={() => grant(p.permit_id)}
                              disabled={!panel.validFrom || !panel.validUntil}
                              className="bg-green-600 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-green-700 disabled:opacity-40"
                            >
                              Confirm Grant
                            </button>
                            <button
                              onClick={() => setPanel(p.permit_id, null)}
                              className="text-gray-500 text-sm hover:text-gray-700"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Refuse panel */}
                      {panel?.type === "refuse" && (
                        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex flex-col gap-3">
                          <p className="text-sm font-medium text-red-800">Refuse permit</p>
                          <textarea
                            value={panel.comment}
                            onChange={(e) => setPanel(p.permit_id, { ...panel, comment: e.target.value })}
                            placeholder="Reason for refusal (shown to applicant)"
                            rows={2}
                            className="border border-gray-300 rounded px-2 py-1 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-200"
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => refuse(p.permit_id)}
                              disabled={!panel.comment.trim()}
                              className="bg-red-600 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-red-700 disabled:opacity-40"
                            >
                              Confirm Refusal
                            </button>
                            <button
                              onClick={() => setPanel(p.permit_id, null)}
                              className="text-gray-500 text-sm hover:text-gray-700"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
