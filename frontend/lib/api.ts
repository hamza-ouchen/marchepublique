import type {
  ChatResponse,
  DashboardResponse,
  Lang,
  OpportunityDetail,
  Status,
} from "./types";
import { getAuth } from "../app/lib";

// Vide = même origine (le rewrite Next /api/* -> FastAPI). En local on peut
// aussi viser directement http://127.0.0.1:8000 via .env.local.
const BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

export const COMPANY_ID =
  process.env.NEXT_PUBLIC_COMPANY_ID || "EXPLEO-IT-001";

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authorization(),
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    let detail = `Erreur ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // réseau / HTML
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

function authorization(): Record<string, string> {
  const auth = getAuth();
  return auth ? { Authorization: `Bearer ${auth.token}` } : {};
}

function params(values: Record<string, string | number | boolean | undefined | null>) {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

export const api = {
  opportunityDocument(reference: string) {
    return request<{ url: string }>(`/api/opportunity-document${params({ reference })}`);
  },

  opportunityDetail(reference: string) {
    return request<OpportunityDetail>(`/api/opportunity-detail${params({ reference })}`);
  },

  async downloadReport(reference: string): Promise<void> {
    const response = await fetch(
      `${BASE_URL}/api/opportunity-report${params({ reference })}`,
      { headers: authorization() },
    );
    if (!response.ok) throw new Error(`Erreur ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `sou9na-rapport-${reference.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 60)}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },

  dashboard(companyId?: string, date?: string) {
    return request<DashboardResponse>(
      `/api/dashboard${params({ company_id: companyId, date })}`,
    );
  },

  chat(message: string, companyId = COMPANY_ID, date?: string) {
    return request<ChatResponse>(
      `/api/chat${params({ message, company_id: companyId, date })}`,
      { method: "POST" },
    );
  },

  save(companyId: string, reference: string, saved: boolean) {
    return request<{ reference: string; saved: boolean }>(
      `/api/opportunities/${encodeURIComponent(reference)}/save${params({
        company_id: companyId,
        saved,
      })}`,
      { method: "POST" },
    );
  },

  update(
    companyId: string,
    reference: string,
    statut?: Status,
    note?: string,
  ) {
    return request<{ reference: string }>(
      `/api/opportunities/${encodeURIComponent(reference)}${params({
        company_id: companyId,
        statut: statut ? statusToBackend(statut) : undefined,
        note,
      })}`,
      { method: "PATCH" },
    );
  },

  prospect(payload: Record<string, unknown>) {
    return request<{ succes: boolean }>("/api/prospects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};

function statusToBackend(status: Status): string {
  if (status === "prep") return "envoye";
  if (status === "submitted") return "gagne";
  return "a_etudier";
}

export function formatDate(value: string | undefined, lang: Lang): string {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(lang === "fr" ? "fr-MA" : "ar-MA", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function formatMoney(value: number | null, lang: Lang): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat(lang === "fr" ? "fr-MA" : "ar-MA", {
    style: "currency",
    currency: "MAD",
    maximumFractionDigits: 0,
  }).format(value);
}
