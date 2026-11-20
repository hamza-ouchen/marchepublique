export type Role = "admin" | "user";

export const SECTEURS = [
  "BTP / Travaux publics",
  "Electromenager / Electronique",
  "Textile / Confection",
  "Informatique / Services IT",
  "Agroalimentaire",
  "Transport / Logistique",
  "Autre",
] as const;

export const REGIONS = [
  "Tanger-Tetouan-Al Hoceima",
  "Oriental",
  "Fes-Meknes",
  "Rabat-Sale-Kenitra",
  "Beni Mellal-Khenifra",
  "Casablanca-Settat",
  "Marrakech-Safi",
  "Draa-Tafilalet",
  "Souss-Massa",
  "Guelmim-Oued Noun",
  "Laayoune-Sakia El Hamra",
  "Dakhla-Oued Ed-Dahab",
] as const;

export interface AppUser {
  id: string;
  nom: string;
  telephone: string; // identifiant principal — format E.164 (ex. 212612345678)
  email?: string;
  role: Role;
  entreprise?: string;
  ice?: string;
  secteurActivite?: string;
  region?: string;
  qualifications?: string;
  dateInscription: string;
}

export type HitlStatus = "en_attente" | "confirme" | "rejete" | "non_requis";

export interface Conversation {
  id: string;
  clientNom: string;
  entreprise: string;
  langue: "fr" | "ar" | "darija";
  dernierMessage: string;
  reponse: string;
  hitl: boolean;
  hitlStatus: HitlStatus;
  canal: "whatsapp";
  horodatage: string;
}

export interface StatPoint {
  label: string;
  value: number;
}

// ---------------------------------------------------------------------------
// Dossier (avis de marche + Match /100 + verdict) — schema aligne sur
// SOU9NA-REF-001 §4.3 (contrats E/S INSPECTEUR / COMPAGNON / JUGE).
// ---------------------------------------------------------------------------

export type Verdict = "GO" | "A_ETUDIER" | "NO_GO";
export type Controle = "ok" | "risque" | "ko";
export type StatutDossier = "a_etudier" | "envoye" | "gagne" | "perdu";

export interface MatchComposantes {
  secteur: number;
  region: number;
  capacite: number;
  qualifications: number;
  historique: number;
}

export interface Justification {
  constat: string;
  reference: string;
}

export interface Dossier {
  reference: string;
  organisme: string;
  objet: string;
  secteur: string;
  region: string;
  montantMad: number;
  cautionMad: number;
  qualificationsExigees: string[];
  delaiJours: number;
  datePublication: string;
  dateRemise: string;
  match: {
    total: number;
    algoVersion: string;
    composantes: MatchComposantes;
    pointsPerdus: string[];
  };
  verdict: Verdict;
  controles: {
    cautionVsCapacite: Controle;
    iceAttestations: Controle;
    qualifications: Controle;
    delaiAtteignable: Controle;
  };
  justifications: Justification[];
  risquesAVerifier: string[];
  statut: StatutDossier;
  favori: boolean;
}
