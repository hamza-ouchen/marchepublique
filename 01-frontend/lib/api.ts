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
} from "./mock-data";
import { Conversation, StatPoint } from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? null;

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
