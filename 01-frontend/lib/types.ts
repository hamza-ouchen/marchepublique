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
  email: string;
  password: string; // prototype only — jamais a faire ainsi avec un vrai backend
  role: Role;
  entreprise?: string;
  ice?: string;
  telephone?: string;
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
