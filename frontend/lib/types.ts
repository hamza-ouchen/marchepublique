export type Lang = "fr" | "ar";
export type Verdict = "go" | "study" | "nogo";
export type Status = "study" | "prep" | "submitted";

export type Breakdown = {
  secteur: number;
  keywords: number;
  region: number;
  size: number;
  history: number;
};

export type Citation = {
  constat?: string;
  reference?: string;
  article?: string;
  pages?: string;
};

export type Opportunity = {
  id: string;
  source_ref: string;
  title: Record<Lang, string>;
  buyer: Record<Lang, string>;
  city: string;
  sector: string;
  opportunity_type: "appel_offres" | "bon_commande" | "consultation";
  deadline: string;
  amount: number | null;
  guarantee: number | null;
  match_score: number;
  verdict: Verdict;
  risks: string[];
  reasons: string[];
  breakdown: Breakdown;
  confidence: "faible" | "moyen" | "eleve";
  source_preuve: string;
  citation: Citation | null;
  saved: boolean;
  status: Status;
  note: string;
  url: string | null;
  is_new: boolean;
};

export type DigestLine = {
  reference: string;
  objet: string;
  organisme?: string;
  match: number;
  remise?: string;
  verdict: string;
  confiance?: string;
  risques?: string[];
  citation?: Citation;
};

export type DashboardResponse = {
  date: string;
  company: {
    company_id: string;
    nom: string;
    secteur: string;
    region: string;
    email: string;
    canaux_optin?: Record<string, boolean>;
  };
  profile: { name: string; sector: string; region: string };
  stats: {
    total: number;
    go: number;
    a_etudier: number;
    no_go: number;
    dossiers_suivis: number;
  };
  opportunities: Opportunity[];
  digest: {
    titre?: string;
    top_matchs?: DigestLine[];
    resume?: string;
    [key: string]: unknown;
  };
  digest_status: string | null;
};

export type ChatResponse = {
  texte: string;
  citation: Citation | null;
  hitl: boolean;
  donnees: Record<string, unknown>;
};
