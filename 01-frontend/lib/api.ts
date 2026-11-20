// ---------------------------------------------------------------------------
// COUCHE D'INTEGRATION — point d'entree unique pour toutes les donnees
// affichees dans le dashboard (admin + user).
//
// Aujourd'hui : ces fonctions renvoient les donnees de demonstration
// (lib/mock-data.ts). Toutes les pages du dashboard passent par ICI pour
// lire leurs donnees (jamais directement par lib/mock-data) — donc pour
// brancher le vrai backend, il suffit de modifier CE fichier, sans toucher
// aux pages.
//
// Quand le backend (Hamza Midouni, FastAPI) et le workflow LangGraph
// (RAG de Hamza Ouchen, agents RÉGISSEUR / INSPECTEUR / SENTINELLE) seront
// prets :
//   1. Definir NEXT_PUBLIC_API_URL dans .env.local (ex: https://api.sou9na.ma)
//   2. Remplacer le contenu de chaque fonction ci-dessous par un vrai appel
//      fetch(`${API_BASE_URL}/...`) vers l'endpoint correspondant.
//   3. La forme des donnees (types dans lib/types.ts) doit rester alignee
//      avec le schema officiel SOU9NA-REF-004 (langue / reponse / citation /
//      hitl) pour les conversations issues de l'agent CONCIERGE.
// ---------------------------------------------------------------------------

import {
  mockConversations,
  weeklyVolume,
  clientsTable,
  userHistorique,
  mockDossiers,
} from "./mock-data";
import { Conversation, Dossier, StatPoint } from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? null;

// ---------------------------------------------------------------------------
// AUTH OTP — contrat officiel SOU9NA-REF-001 §3.2 : POST /auth/otp (demande
// de code), POST /auth/verify (verification + session). Cote backend chez
// Hamza Midouni (FastAPI). Tant que l'endpoint n'est pas branche
// (NEXT_PUBLIC_API_URL non defini), on simule localement en MODE TEST —
// aucun mot de passe, aucune donnee sensible stockee : seul un code a 6
// chiffres a duree de vie courte, garde en memoire (sessionStorage), jamais
// un vrai secret.
// ---------------------------------------------------------------------------

const OTP_MOCK_KEY = "sou9na_otp_mock"; // mode test uniquement — jamais en production
const OTP_TTL_MS = 5 * 60 * 1000;

export interface OtpRequestResult {
  ok: boolean;
  error?: string;
  // present uniquement en mode test (backend non branche) — pour que le
  // prototype reste utilisable sans envoi WhatsApp reel.
  devCode?: string;
}

export interface OtpVerifyResult {
  ok: boolean;
  error?: string;
  token?: string;
  user?: {
    id: string;
    nom: string;
    telephone: string;
    role: "admin" | "user";
    entreprise?: string;
  };
}

export async function requestOtp(telephone: string): Promise<OtpRequestResult> {
  if (API_BASE_URL) {
    const res = await fetch(`${API_BASE_URL}/auth/otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ telephone }),
    });
    return res.json();
  }
  // MODE TEST — sans backend : genere un code local, duree de vie 5 min.
  const code = Math.floor(100000 + Math.random() * 900000).toString();
  window.sessionStorage.setItem(
    OTP_MOCK_KEY,
    JSON.stringify({ telephone, code, expiresAt: Date.now() + OTP_TTL_MS })
  );
  return { ok: true, devCode: code };
}

export async function verifyOtp(
  telephone: string,
  code: string
): Promise<OtpVerifyResult> {
  if (API_BASE_URL) {
    const res = await fetch(`${API_BASE_URL}/auth/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ telephone, code }),
    });
    return res.json();
  }
  // MODE TEST — verifie contre le code local genere par requestOtp().
  const raw = window.sessionStorage.getItem(OTP_MOCK_KEY);
  if (!raw) return { ok: false, error: "Aucun code demande. Recommencez." };
  const stored = JSON.parse(raw) as { telephone: string; code: string; expiresAt: number };
  if (Date.now() > stored.expiresAt) {
    window.sessionStorage.removeItem(OTP_MOCK_KEY);
    return { ok: false, error: "Code expire. Demandez un nouveau code." };
  }
  if (stored.telephone !== telephone || stored.code !== code) {
    return { ok: false, error: "Code incorrect." };
  }
  window.sessionStorage.removeItem(OTP_MOCK_KEY);
  return { ok: true, token: `mock-${Date.now()}` }; // user resolu/cree par auth-context en mode test
}

// GET /conversations — toutes les conversations WhatsApp (vue admin).
// Reponse attendue par conversation : voir le type Conversation (lib/types.ts),
// aligne sur le schema SOU9NA-REF-004 (langue, reponse, citation, hitl).
export function getConversations(): Conversation[] {
  // TODO(backend): remplacer par un fetch(`${API_BASE_URL}/conversations`)
  return mockConversations;
}

// GET /stats/volume?days=7 — volume de conversations par jour (7 derniers jours).
export function getWeeklyVolume(): StatPoint[] {
  // TODO(backend): remplacer par un fetch(`${API_BASE_URL}/stats/volume?days=7`)
  return weeklyVolume;
}

// GET /clients — liste des TPME inscrites (vue admin "Clients").
export function getClients(): typeof clientsTable {
  // TODO(backend): remplacer par un fetch(`${API_BASE_URL}/clients`)
  return clientsTable;
}

// GET /me/historique — historique des conversations du TPME connecte (vue user).
export function getUserHistorique(): Conversation[] {
  // TODO(backend): remplacer par un fetch(`${API_BASE_URL}/me/historique`)
  // avec le token/session du TPME connecte.
  return userHistorique;
}

// GET /me/dossiers — dossiers (avis + Match + verdict) du TPME connecte.
// Schema aligne sur SOU9NA-REF-001 §4.3 (COMPAGNON + JUGE). Mutations locales
// (favori/statut) sont gardees en memoire ici tant que le backend n'expose
// pas PATCH /me/dossiers/:reference.
let dossiersState: Dossier[] = mockDossiers;

export function getDossiers(): Dossier[] {
  // TODO(backend): remplacer par un fetch(`${API_BASE_URL}/me/dossiers`)
  return dossiersState;
}

export function getDossier(reference: string): Dossier | undefined {
  // TODO(backend): remplacer par un fetch(`${API_BASE_URL}/me/dossiers/${reference}`)
  return dossiersState.find((d) => d.reference === reference);
}

export function setDossierFavori(reference: string, favori: boolean): void {
  // TODO(backend): remplacer par un PATCH `${API_BASE_URL}/me/dossiers/${reference}`
  dossiersState = dossiersState.map((d) => (d.reference === reference ? { ...d, favori } : d));
}

export function setDossierStatut(reference: string, statut: Dossier["statut"]): void {
  // TODO(backend): remplacer par un PATCH `${API_BASE_URL}/me/dossiers/${reference}`
  dossiersState = dossiersState.map((d) => (d.reference === reference ? { ...d, statut } : d));
}
