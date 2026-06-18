export interface Dataset {
  id: string;
  name: string;
  description: string;
  population_size: number;
  time_range_from: string;
  time_range_until: string;
  domains: string[];
  omop_version: string;
}

export interface Concept {
  concept_id: number;
  concept_name: string;
  vocabulary_id: string;
  domain_id: string;
  concept_class_id: string;
  standard_concept: string | null;
}

export interface CountResult {
  concept_id: number;
  concept_name: string | null;
  patient_count: number | string;
}

export interface DataScope {
  domains: string[];
  concept_ids: number[];
  time_window_from: string;
  time_window_until: string;
}

export interface Permit {
  permit_id: string;
  type: string;
  holder: string;
  named_users: string[];
  purpose: string;
  data_scope: DataScope;
  format: string;
  pseudonymization_justification: string | null;
  valid_from: string | null;
  valid_until: string | null;
  state: string;
  omop_snapshot: string;
  vocab_version: string;
  reviewer_comment: string | null;
  created_at: string;
  updated_at: string;
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  datasets: {
    list: () => get<Dataset[]>("/api/discovery/datasets"),
    get: (id: string) => get<Dataset>(`/api/discovery/datasets/${id}`),
  },
  concepts: {
    search: (q: string, domain?: string) => {
      const params = new URLSearchParams({ q });
      if (domain) params.set("domain", domain);
      return get<Concept[]>(`/api/discovery/concepts/search?${params}`);
    },
    descendants: (id: number) =>
      get<Concept[]>(`/api/discovery/concepts/${id}/descendants`),
  },
  counts: {
    get: (conceptId: number) =>
      get<CountResult>(`/api/discovery/counts?concept_id=${conceptId}`),
  },
  llm: {
    chat: (messages: {role: string; content: string}[], userId = "anonymous") =>
      post<{reply: string; provider: string}>("/api/llm/chat", { messages, user_id: userId }),
  },
  permits: {
    create: (body: {
      type: string;
      holder: string;
      named_users: string[];
      purpose: string;
      data_scope: DataScope;
      format: string;
      pseudonymization_justification: string | null;
    }) => post<Permit>("/api/permits/permits", body),
    submit: (permitId: string, actor: string) =>
      post<Permit>(`/api/permits/permits/${permitId}/submit`, { actor }),
    listByHolder: (holder: string) =>
      get<Permit[]>(`/api/permits/permits?holder=${encodeURIComponent(holder)}`),
    register: () => get<Permit[]>("/api/permits/permits/register"),
  },
};
