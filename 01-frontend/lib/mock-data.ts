import { Conversation, StatPoint } from "./types";

// Donnees de demonstration pour le prototype frontend.
// Remplacer par de vrais appels API des que le backend (Hamza Midouni) est branche.

export const mockConversations: Conversation[] = [
  {
    id: "c1",
    clientNom: "Youssef Amrani",
    entreprise: "Amrani Travaux SARL",
    langue: "darija",
    dernierMessage: "Salam, bghit n3rf chno homa les documents li khasni...",
    reponse: "je verifie et je reviens vers vous",
    hitl: true,
    hitlStatus: "en_attente",
    canal: "whatsapp",
    horodatage: "2026-11-18T08:12:00Z",
  },
  {
    id: "c2",
    clientNom: "Sanaa Benali",
    entreprise: "Benali Construction",
    langue: "fr",
    dernierMessage: "Bonjour, quel est le delai de paiement des marches publics ?",
    reponse: "je verifie et je reviens vers vous",
    hitl: true,
    hitlStatus: "confirme",
    canal: "whatsapp",
    horodatage: "2026-11-17T15:40:00Z",
  },
  {
    id: "c3",
    clientNom: "Karim Idrissi",
    entreprise: "Idrissi Electromenager",
    langue: "ar",
    dernierMessage: "مرحبا، عاوز نغير رقم الهاتف ديالي فالملف",
    reponse: "تم استلام طلبكم، سيتم التأكيد يدويا قبل التعديل",
    hitl: true,
    hitlStatus: "en_attente",
    canal: "whatsapp",
    horodatage: "2026-11-17T11:05:00Z",
  },
  {
    id: "c4",
    clientNom: "Nadia Chraibi",
    entreprise: "Chraibi Textile",
    langue: "fr",
    dernierMessage: "Merci pour les infos sur le premier appel d'offres",
    reponse: "Avec plaisir, n'hesitez pas si vous avez d'autres questions.",
    hitl: false,
    hitlStatus: "non_requis",
    canal: "whatsapp",
    horodatage: "2026-11-16T09:22:00Z",
  },
];

export const weeklyVolume: StatPoint[] = [
  { label: "Lun", value: 12 },
  { label: "Mar", value: 18 },
  { label: "Mer", value: 9 },
  { label: "Jeu", value: 23 },
  { label: "Ven", value: 15 },
  { label: "Sam", value: 6 },
  { label: "Dim", value: 4 },
];

export const clientsTable = [
  { id: "t1", entreprise: "Amrani Travaux SARL", ice: "0012345678", contact: "Youssef Amrani", secteur: "BTP / Travaux publics", region: "Beni Mellal-Khenifra", statut: "Actif", depuis: "Oct 2026" },
  { id: "t2", entreprise: "Benali Construction", ice: "0098765432", contact: "Sanaa Benali", secteur: "BTP / Travaux publics", region: "Casablanca-Settat", statut: "Actif", depuis: "Sep 2026" },
  { id: "t3", entreprise: "Idrissi Electromenager", ice: "0055512345", contact: "Karim Idrissi", secteur: "Electromenager / Electronique", region: "Rabat-Sale-Kenitra", statut: "En attente", depuis: "Nov 2026" },
  { id: "t4", entreprise: "Chraibi Textile", ice: "0077788899", contact: "Nadia Chraibi", secteur: "Textile / Confection", region: "Fes-Meknes", statut: "Actif", depuis: "Aout 2026" },
];

export const userHistorique: Conversation[] = [
  {
    id: "h1",
    clientNom: "Vous",
    entreprise: "",
    langue: "darija",
    dernierMessage: "Salam, bghit n3rf chno homa les documents li khasni bach nchark f appel d'offre?",
    reponse: "je verifie et je reviens vers vous",
    hitl: true,
    hitlStatus: "en_attente",
    canal: "whatsapp",
    horodatage: "2026-11-18T08:12:00Z",
  },
  {
    id: "h2",
    clientNom: "Vous",
    entreprise: "",
    langue: "fr",
    dernierMessage: "Bonjour, quel est le delai de paiement des marches publics ?",
    reponse: "je verifie et je reviens vers vous",
    hitl: true,
    hitlStatus: "confirme",
    canal: "whatsapp",
    horodatage: "2026-11-15T10:03:00Z",
  },
];
