"use client";

// Tableau de bord entreprise — design premium "Sou9na" (paper / encre /
// vert émeraude / safran / terracotta), porté depuis le mockup soukna.
// Données de démonstration, bilingue FR/AR avec bascule RTL.

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ChatPanel from "@/components/chat-panel";
import { api } from "@/lib/api";
import type { Opportunity } from "@/lib/types";
import { clearAuth, getAuth } from "../lib";
import BrandLoader from "../brand-loader";

// ------------------------------------------------------------------ types
type Lang = "fr" | "ar";
type Verdict = "go" | "study" | "nogo";
type Status = "study" | "prep" | "submitted";

type Opp = {
  id: string;
  source_ref: string;
  title: Record<Lang, string>;
  buyer: Record<Lang, string>;
  city: string;
  sector: keyof typeof SECTORS;
  opportunity_type: "appel_offres" | "bon_commande" | "consultation";
  deadline: string;
  deadline_time?: string | null;
  publication_time?: string | null;
  publication_date?: string | null;
  amount: number | null;
  guarantee: number | null;
  match_score: number;
  verdict: Verdict;
  risks: string[];
  reasons: string[];
  recommendations?: string[];
  advice?: string;
  confidence?: Opportunity["confidence"];
  citation?: Opportunity["citation"];
  breakdown: Record<string, number>;
  saved: boolean;
  status: Status;
  note: string;
  url: string | null;
  is_new: boolean;
};

const SECTORS = {
  it: { fr: "Informatique", ar: "المعلوميات" },
  btp: { fr: "BTP", ar: "البناء والأشغال" },
  fournitures: { fr: "Fournitures", ar: "التوريدات" },
  services: { fr: "Services et maintenance", ar: "الخدمات والصيانة" },
  conseil: { fr: "Conseil et études", ar: "الاستشارة والدراسات" },
} as const;

const CITIES = ["Casablanca", "Rabat", "Tanger", "Marrakech", "Agadir"];

// ------------------------------------------------------------------ i18n
const T: Record<Lang, Record<string, string>> = {
  fr: {
    espacePro: "Espace Pro",
    searchPlaceholder: "Mots-clés, acheteur, ville...",
    notifications: "Notifications",
    notifTitle: "Notifications récentes",
    noNotif: "Aucune notification pour l'instant",
    logout: "Déconnexion",
    tabFeed: "Tableau de bord",
    tabDossiers: "Mes Dossiers",
    tabProfile: "Profil Entreprise",
    tabAlerts: "Alertes & Synthèse",

    kpi1Title: "Nouvelles opportunités (24h)",
    kpi1Sub: "Scannées dans les avis publics",
    kpi2Title: "Matchs élevés (GO)",
    kpi2Sub: "Match ≥ seuil de recommandation",
    kpi3Title: "Avis à étudier",
    kpi3Sub: "Points de risque à vérifier",
    kpi4Title: "Dossiers suivis",
    kpi4Tag: "Pipeline actif",
    kpi4Sub: "En cours de préparation",

    filterKeyword: "Filtrer par objet, référence...",
    allSectors: "Tous les secteurs",
    allCities: "Toutes les villes",
    allVerdicts: "Tous les verdicts",
    allTypes: "Tous les types",
    typeAO: "Appel d'offres",
    typeBC: "Bon de commande",
    typeConsult: "Consultation",
    verdictGo: "✓ GO uniquement",
    verdictStudy: "! À étudier",
    verdictNogo: "× NO-GO",
    new24: "Nouveaux 24h",
    resetBtn: "Réinitialiser",
    oppsFound: "opportunités trouvées selon vos critères",
    sortBy: "Trier par :",
    sortMatch: "Score de Match (Décroissant)",
    sortDeadline: "Échéance imminente",
    noResultsTitle: "Aucune opportunité ne correspond à ces filtres",
    noResultsText: "Essayez de modifier votre recherche ou de réinitialiser vos filtres.",
    newBadge: "NOUVEAU",
    seeAnalysis: "Voir l'analyse",
    match: "MATCH",
    keyDeadline: "Date d'échéance",
    keyCity: "Localisation",
    keyBudget: "Budget / Montant",
    keySector: "Secteur",
    keyGuarantee: "Caution provisoire",
    notProvided: "Non renseigné",

    drawerSubtitle: "Analyse d'opportunité Sou9na",
    matchLabel: "MATCH /100",
    breakdownHeader: "Détail des facteurs de Match",
    sectorFit: "Adéquation sectorielle",
    keywordFit: "Mots-clés & Métier",
    regionFit: "Proximité géographique",
    sizeFit: "Capacité & Taille",
    historyFit: "Historique & Références",
    risksHeader: "Points à vérifier dans le dossier",
    noRisks: "Aucun point bloquant identifié dans les pièces analysées.",
    risksNote:
      "Actions de vérification déduites du dossier officiel. Sou9na n'affirme aucune pénalité ni retard non mentionné dans les pièces.",
    recommendationsHeader: "Recommandations",
    adviceHeader: "Conseil Sou9na",
    openFull: "Voir le dossier complet",
    officialSourceTitle: "Document Officiel & CPS",
    officialSourceDesc:
      "Le résumé Sou9na est indicatif. Consultez le dossier de consultation officiel avant tout engagement.",
    openSourceBtn: "Ouvrir l'avis sur le portail",
    closeBtn: "Fermer",
    saveDossier: "Enregistrer dans Mes Dossiers",
    savedDossier: "Dossier Enregistré",

    dossiersTitle: "Suivi des Dossiers & Candidatures",
    dossiersSub:
      "Organisez vos réponses aux appels d'offres et suivez vos pièces administratives.",
    colStudy: "En cours d'étude",
    colPrep: "Dossier en préparation",
    colSubmitted: "Soumis / Clôturé",
    emptyStudy: "Aucun dossier en étude",
    emptyPrep: "Aucun dossier en préparation",
    emptySubmitted: "Aucun dossier soumis pour le moment",
    notePlaceholder: "Ajouter une note d'équipe...",
    remove: "Retirer",
    statusStudy: "En étude",
    statusPrep: "En préparation",
    statusSubmitted: "Soumis",

    profileHeading: "Profil Entreprise & Capacités",
    profileDesc:
      "Mettez à jour vos critères d'entreprise pour recalculer l'algorithme de Match au prochain passage du pipeline.",
    profileNameLabel: "Nom de l'entreprise",
    profileSectorLabel: "Secteur principal",
    profileSizeLabel: "Taille d'entreprise",
    profileCityLabel: "Régions d'intervention (séparées par des virgules)",
    profileGuaranteeLabel: "Capacité garantie provisoire max (MAD)",
    profileKeywordsLabel: "Mots-clés d'activité (séparés par des virgules)",
    budgetMin: "Budget min (MAD)",
    budgetMax: "Budget max (MAD)",
    certsLabel: "Certifications (séparées par ,)",
    qualifLabel: "Qualification / classement",
    expLabel: "Années d'expérience",
    profileNote: "Les recalculs s'appliqueront au prochain run du pipeline.",
    saveProfileBtn: "Enregistrer les modifications",

    alertsHeading: "Configuration des Alertes & Synthèse",
    alertsDesc:
      "Choisissez quand et comment recevoir vos opportunités personnalisées par email ou WhatsApp.",
    alertDailyTitle: "Synthèse (Email)",
    alertDailySub: "Recevez chaque matin les marchés filtrés pour votre entreprise.",
    alertWaTitle: "Alertes Instantanées WhatsApp",
    alertWaSub: "Soyez notifié dès qu'un Match dépasse votre seuil.",
    alertThreshTitle: "Seuil minimal de Match pour notification",
    lastDigest: "Dernière synthèse",
    noDigest: "Aucune synthèse reçue pour l'instant.",
    saveAlertsBtn: "Sauvegarder mes préférences",

    savedToast: "Opportunité enregistrée dans Mes Dossiers",
    removedToast: "Opportunité retirée de vos dossiers",
    profileSavedToast: "Profil entreprise sauvegardé ✅",
    alertSavedToast: "Préférences d'alertes enregistrées.",

    verdictGoPill: "GO — À considérer",
    verdictStudyPill: "À étudier",
    verdictNogoPill: "NO-GO",
    reasonGo: "Bonne adéquation sectorielle et géographique. Vérifiez les exigences techniques avant de décider.",
    reasonStudy: "L'opportunité pourrait convenir, mais certaines conditions méritent une vérification.",
    reasonNo: "L'opportunité semble peu adaptée au profil ou présente une contrainte importante.",
    riskDeadline: "Délai à confirmer",
    riskDocs: "Pièces techniques",
    riskGuarantee: "Garantie provisoire élevée",
    riskQualification: "Qualification requise",
    riskVisit: "Visite obligatoire",
    riskPayment: "Conditions de paiement",
    sizeSmall: "TPE / petite entreprise",
    sizePme: "PME",
    sizeLarge: "Grande entreprise",
    footer: "© 2026 Sou9na — Intelligence des marchés publics au Maroc",
  },
  ar: {
    espacePro: "فضاء المقاولة",
    searchPlaceholder: "كلمات مفتاحية، جهة الشراء، المدينة...",
    notifications: "الإشعارات",
    notifTitle: "الإشعارات الأخيرة",
    noNotif: "لا توجد إشعارات حالياً",
    logout: "تسجيل الخروج",
    tabFeed: "لوحة القيادة",
    tabDossiers: "ملفاتي",
    tabProfile: "ملف الشركة",
    tabAlerts: "التنبيهات والملخص",

    kpi1Title: "فرص جديدة (24 ساعة)",
    kpi1Sub: "تم مسحها في الإعلانات العمومية",
    kpi2Title: "توافق مرتفع (تقدّم)",
    kpi2Sub: "توافق فوق حد التوصية",
    kpi3Title: "عروض للدراسة",
    kpi3Sub: "نقاط خطر تتطلب التحقق",
    kpi4Title: "ملفات قيد المتابعة",
    kpi4Tag: "متابعة نشطة",
    kpi4Sub: "قيد التحضير",

    filterKeyword: "تصفية حسب الموضوع أو المرجع...",
    allSectors: "جميع القطاعات",
    allCities: "جميع المدن",
    allVerdicts: "جميع التوصيات",
    allTypes: "كل الأنواع",
    typeAO: "مناقصة",
    typeBC: "أمر بالتأدية",
    typeConsult: "استشارة",
    verdictGo: "✓ تقدّم فقط",
    verdictStudy: "! للدراسة",
    verdictNogo: "× تجاوز",
    new24: "جديد 24س",
    resetBtn: "إعادة ضبط",
    oppsFound: "فرص تم العثور عليها وفق معاييرك",
    sortBy: "ترتيب حسب:",
    sortMatch: "درجة التوافق (تنازلي)",
    sortDeadline: "الاقتراب من آخر أجل",
    noResultsTitle: "لا توجد فرص تطابق هذه المرشحات",
    noResultsText: "جرب تغيير البحث أو إعادة ضبط مرشحات الاختيار.",
    newBadge: "جديد",
    seeAnalysis: "عرض التحليل",
    match: "التوافق",
    keyDeadline: "تاريخ آخر أجل",
    keyCity: "الموقع الجغرافي",
    keyBudget: "الميزانية / المبلغ",
    keySector: "القطاع",
    keyGuarantee: "الضمان المؤقت",
    notProvided: "غير محدد",

    drawerSubtitle: "تحليل الفرصة من Sou9na",
    matchLabel: "التوافق /100",
    breakdownHeader: "تفاصيل عوامل التوافق",
    sectorFit: "ملاءمة القطاع",
    keywordFit: "الكلمات المفتاحية والمهنة",
    regionFit: "القرب الجغرافي",
    sizeFit: "القدرة والحجم",
    historyFit: "السجل والخبرة السابقة",
    risksHeader: "نقاط يجب التحقق منها في الملف",
    noRisks: "لم يتم تحديد أي نقطة حاجزة في المستندات المحللة.",
    risksNote:
      "إجراءات تحقق مستنتجة من الملف الرسمي. لا يؤكد Sou9na أي غرامة أو تأخير غير مذكور في المستندات.",
    recommendationsHeader: "التوصيات",
    adviceHeader: "نصيحة Sou9na",
    openFull: "عرض الملف الكامل",
    officialSourceTitle: "الوثيقة الرسمية ودفتر الشروط",
    officialSourceDesc:
      "ملخص Sou9na إرشادي. يرجى الاطلاع على ملف الاستشارة الرسمي قبل أي التزام.",
    openSourceBtn: "فتح الإعلان على البوابة",
    closeBtn: "إغلاق",
    saveDossier: "حفظ في ملفاتي",
    savedDossier: "تم حفظ الملف",

    dossiersTitle: "متابعة الملفات الترشيحية",
    dossiersSub: "نظم إجاباتك على طلبات العروض وتابع الوثائق الإدارية.",
    colStudy: "قيد الدراسة",
    colPrep: "الملف قيد التحضير",
    colSubmitted: "تم الإرسال / مغلق",
    emptyStudy: "لا يوجد ملف قيد الدراسة",
    emptyPrep: "لا يوجد ملف قيد التحضير",
    emptySubmitted: "لا يوجد ملف مرسل حالياً",
    notePlaceholder: "أضف ملاحظة للفريق...",
    remove: "إزالة",
    statusStudy: "قيد الدراسة",
    statusPrep: "قيد التحضير",
    statusSubmitted: "تم الإرسال",

    profileHeading: "ملف الشركة والقدرات",
    profileDesc:
      "قم بتحديث معايير شركتك لإعادة حساب خوارزمية التوافق في المرور القادم.",
    profileNameLabel: "اسم الشركة",
    profileSectorLabel: "القطاع الرئيسي",
    profileSizeLabel: "حجم الشركة",
    profileCityLabel: "مناطق التدخل (مفصولة بفواصل)",
    profileGuaranteeLabel: "الحد الأقصى للضمان المؤقت (درهم)",
    profileKeywordsLabel: "الكلمات المفتاحية للنشاط (مفصولة بفواصل)",
    budgetMin: "الميزانية الدنيا (درهم)",
    budgetMax: "الميزانية القصوى (درهم)",
    certsLabel: "الشهادات (مفصولة بفواصل)",
    qualifLabel: "التصنيف",
    expLabel: "سنوات الخبرة",
    profileNote: "ستطبق الحسابات الجديدة في المرور القادم للنظام.",
    saveProfileBtn: "حفظ التغييرات",

    alertsHeading: "إعداد التنبيهات والملخص",
    alertsDesc: "اختر وقت وطريقة استلام الفرص المخصصة عبر البريد أو الواتساب.",
    alertDailyTitle: "الملخص (بريد إلكتروني)",
    alertDailySub: "استلم كل صباح الصفقات المفلترة لشركتك.",
    alertWaTitle: "تنبيهات فورية عبر الواتساب",
    alertWaSub: "احصل على إشعار مباشر فور تجاوز درجة التوافق لحدك.",
    alertThreshTitle: "الحد الأدنى للتوافق للإشعار",
    lastDigest: "آخر ملخص",
    noDigest: "لا يوجد ملخص مستلم حالياً.",
    saveAlertsBtn: "حفظ التفضيلات",

    savedToast: "تم حفظ الفرصة في ملفاتي",
    removedToast: "تم إزالة الفرصة من ملفاتك",
    profileSavedToast: "تم حفظ ملف الشركة ✅",
    alertSavedToast: "تم حفظ تفضيلات التنبيهات.",

    verdictGoPill: "تقدّم — ممتازة",
    verdictStudyPill: "للدراسة",
    verdictNogoPill: "تجاوز",
    reasonGo: "توافق جيد مع القطاع والموقع. تحقق من المتطلبات التقنية قبل اتخاذ القرار.",
    reasonStudy: "قد تناسب الفرصة شركتك، لكن بعض الشروط تستحق التحقق.",
    reasonNo: "تبدو الفرصة غير ملائمة للملف أو تتضمن قيداً مهماً.",
    riskDeadline: "تحقق من الأجل",
    riskDocs: "وثائق تقنية",
    riskGuarantee: "ضمان مؤقت مرتفع",
    riskQualification: "مؤهل مطلوب",
    riskVisit: "زيارة إلزامية",
    riskPayment: "شروط الأداء",
    sizeSmall: "مقاولة صغيرة",
    sizePme: "مقاولة متوسطة",
    sizeLarge: "مقاولة كبيرة",
    footer: "© 2026 Sou9na — ذكاء طلبات العروض العمومية بالمغرب",
  },
};

// ------------------------------------------------------------------ mock data
const OPPS: Opp[] = [
  {
    id: "o1",
    source_ref: "SO-2026-001",
    title: {
      fr: "Maintenance et évolution d'une plateforme de gestion",
      ar: "صيانة وتطوير منصة للتدبير",
    },
    buyer: { fr: "Organisme acheteur fictif A", ar: "جهة شراء افتراضية أ" },
    city: "Casablanca",
    sector: "it",
    opportunity_type: "appel_offres",
    deadline: "2026-11-24",
    amount: 450000,
    guarantee: 9000,
    match_score: 92,
    verdict: "go",
    risks: ["riskDeadline", "riskDocs"],
    reasons: ["reasonGo"],
    breakdown: { sector: 95, keywords: 90, region: 100, size: 80, history: 85 },
    saved: true,
    status: "prep",
    note: "Relancer l'équipe technique pour le CPS.",
    url: null,
    is_new: true,
  },
  {
    id: "o2",
    source_ref: "SO-2026-002",
    title: {
      fr: "Réhabilitation d'un bâtiment administratif",
      ar: "إعادة تأهيل مبنى إداري",
    },
    buyer: { fr: "Maître d'ouvrage fictif B", ar: "صاحب مشروع افتراضي ب" },
    city: "Rabat",
    sector: "btp",
    opportunity_type: "appel_offres",
    deadline: "2026-11-29",
    amount: 1850000,
    guarantee: 37000,
    match_score: 74,
    verdict: "study",
    risks: ["riskGuarantee", "riskQualification"],
    reasons: ["reasonStudy"],
    breakdown: { sector: 88, keywords: 72, region: 85, size: 62, history: 60 },
    saved: true,
    status: "study",
    note: "",
    url: null,
    is_new: true,
  },
  {
    id: "o3",
    source_ref: "SO-2026-003",
    title: {
      fr: "Fourniture de matériel de bureau",
      ar: "توريد معدات مكتبية",
    },
    buyer: { fr: "Établissement public fictif C", ar: "مؤسسة عمومية افتراضية ج" },
    city: "Tanger",
    sector: "fournitures",
    opportunity_type: "bon_commande",
    deadline: "2026-12-02",
    amount: 220000,
    guarantee: null,
    match_score: 48,
    verdict: "nogo",
    risks: ["riskDocs"],
    reasons: ["reasonNo"],
    breakdown: { sector: 55, keywords: 42, region: 70, size: 68, history: 25 },
    saved: false,
    status: "study",
    note: "",
    url: null,
    is_new: false,
  },
  {
    id: "o4",
    source_ref: "SO-2026-004",
    title: {
      fr: "Maintenance des équipements techniques",
      ar: "صيانة التجهيزات التقنية",
    },
    buyer: { fr: "Service acheteur fictif D", ar: "مصلحة شراء افتراضية د" },
    city: "Marrakech",
    sector: "services",
    opportunity_type: "appel_offres",
    deadline: "2026-12-06",
    amount: 680000,
    guarantee: 13600,
    match_score: 83,
    verdict: "go",
    risks: ["riskVisit"],
    reasons: ["reasonGo"],
    breakdown: { sector: 91, keywords: 82, region: 76, size: 85, history: 80 },
    saved: true,
    status: "submitted",
    note: "Dossier déposé le 18/11.",
    url: null,
    is_new: true,
  },
  {
    id: "o5",
    source_ref: "SO-2026-005",
    title: {
      fr: "Étude d'optimisation des processus",
      ar: "دراسة لتحسين المساطر",
    },
    buyer: { fr: "Institution fictive E", ar: "مؤسسة افتراضية هـ" },
    city: "Agadir",
    sector: "conseil",
    opportunity_type: "consultation",
    deadline: "2026-12-11",
    amount: null,
    guarantee: null,
    match_score: 68,
    verdict: "study",
    risks: ["riskPayment", "riskDocs"],
    reasons: ["reasonStudy"],
    breakdown: { sector: 82, keywords: 69, region: 65, size: 70, history: 54 },
    saved: false,
    status: "study",
    note: "",
    url: null,
    is_new: false,
  },
  {
    id: "o6",
    source_ref: "SO-2026-006",
    title: {
      fr: "Prestations de support informatique",
      ar: "خدمات الدعم المعلوماتي",
    },
    buyer: { fr: "Organisme fictif F", ar: "هيئة افتراضية و" },
    city: "Casablanca",
    sector: "it",
    opportunity_type: "appel_offres",
    deadline: "2026-12-18",
    amount: 520000,
    guarantee: 10400,
    match_score: 77,
    verdict: "study",
    risks: ["riskQualification"],
    reasons: ["reasonStudy"],
    breakdown: { sector: 88, keywords: 80, region: 95, size: 58, history: 70 },
    saved: false,
    status: "study",
    note: "",
    url: null,
    is_new: false,
  },
];

const RING_LEN = 251.2;
const ringOffset = (score: number) =>
  RING_LEN - (Math.max(0, Math.min(100, score)) * RING_LEN) / 100;

function fmtDate(d: string | null | undefined, lang: Lang): string {
  if (!d) return "—";
  const date = new Date(d.length === 10 ? `${d}T12:00:00` : d);
  if (isNaN(date.getTime())) return d;
  return new Intl.DateTimeFormat(lang === "fr" ? "fr-MA" : "ar-MA", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

function fmtMoney(n: number | null, lang: Lang): string {
  if (n == null) return T[lang].notProvided;
  return new Intl.NumberFormat(lang === "fr" ? "fr-MA" : "ar-MA", {
    style: "currency",
    currency: "MAD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

// ---------------------------------------------------------- API -> UI
const REGION_LABELS: Record<string, string> = {
  "casa-settat": "Casablanca-Settat",
  "tanger-tetouan-alhoceima": "Tanger-Tétouan-Al Hoceïma",
  "souss-massa": "Souss-Massa",
  "rabat-sale-kenitra": "Rabat-Salé-Kénitra",
  "marrakech-safi": "Marrakech-Safi",
  "fes-meknes": "Fès-Meknès",
};

function toOpp(o: Opportunity): Opp {
  const sector = (o.sector in SECTORS ? o.sector : "services") as Opp["sector"];
  const statut = o.status === "prep" || o.status === "submitted" ? o.status : "study";
  return {
    ...o,
    sector,
    city: REGION_LABELS[o.city] || o.city,
    status: statut,
    is_new: false,
  };
}

// ------------------------------------------------------------------ page
export default function DashboardPage() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("fr");
  const [tab, setTab] = useState<"feed" | "dossiers" | "profile" | "alerts">("feed");
  const [opps, setOpps] = useState<Opp[]>([]);
  const [loading, setLoading] = useState(true);
  const [companyId, setCompanyId] = useState("");
  const [initStatus, setInitStatus] = useState<"ready" | "running" | "error">("ready");
  const [apiError, setApiError] = useState("");
  const [companyName, setCompanyName] = useState("Sou9na");
  const [companyInitials, setCompanyInitials] = useState("S");
  const [digestInfo, setDigestInfo] = useState<{
    date: string;
    lines: Array<{
      reference: string;
      objet: string;
      match: number;
      remise?: string;
      verdict?: string;
      confiance?: string;
      risques?: string[];
    }>;
    stats: { total: number; go: number; a_etudier: number; no_go: number; dossiers_suivis: number };
  } | null>(null);
  const [toast, setToast] = useState("");
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const auth = getAuth();
    if (!auth) {
      window.location.href = "/login";
      return;
    }
    if (auth.role === "admin") {
      window.location.href = "/admin";
    }
  }, []);

  useEffect(() => {
    if (getAuth()?.role !== "entreprise") return;
    let vivant = true;
    let prochain: ReturnType<typeof setTimeout> | undefined;
    function charger() {
      void api.dashboard()
      .then((data) => {
        if (!vivant) return;
        setCompanyId(data.company.company_id);
        setInitStatus(data.init_status);
        if (data.init_status === "running") {
          prochain = setTimeout(charger, 4000);
        }
        setOpps(data.opportunities.map(toOpp));
        const nom = data.company?.nom || "Sou9na";
        setCompanyName(nom);
        setCompanyInitials(
          nom
            .split(/\s+/)
            .slice(0, 2)
            .map((mot) => mot[0] || "")
            .join("")
            .toUpperCase() || "S",
        );
        setDigestInfo({
          date: data.date,
          lines: data.digest?.top_matchs || [],
          stats: data.stats,
        });
        setApiError("");
      })
      .catch((err: Error) => {
        if (vivant) {
          setApiError(err.message || "API indisponible");
          prochain = setTimeout(charger, 10000);
        }
      })
      .finally(() => {
        if (vivant) setLoading(false);
      });
    }
    charger();
    return () => {
      vivant = false;
      clearTimeout(prochain);
    };
  }, []);

  const digestTexte = useMemo(() => {
    if (!digestInfo) return lang === "fr" ? "Chargement du digest…" : "جارٍ تحميل الملخص…";
    const date = new Date(`${digestInfo.date}T12:00:00`);
    const dateFr = Number.isNaN(date.getTime())
      ? digestInfo.date
      : date.toLocaleDateString("fr-MA", { day: "2-digit", month: "long", year: "numeric" });
    const lignes = digestInfo.lines.slice(0, 5).map((m, i) => {
      const risques = (m.risques || []).slice(0, 2).join(" · ") || "—";
      return lang === "fr"
        ? `  ${i + 1}. ${m.objet || m.reference} — ${m.match}/100 · confiance ${m.confiance || "faible"}\n     Risques : ${risques}`
        : `  ${i + 1}. ${m.objet || m.reference} — ${m.match}/100 · الثقة ${m.confiance || "faible"}\n     المخاطر: ${risques}`;
    });
    const s = digestInfo.stats;
    if (lang === "ar") {
      return `مرحباً،\n\nملخص ${dateFr} :\n\n📋 أفرص مختارة :\n${lignes.join("\n") || "  لا توجد فرص"}\n\n📊 توصية تقدّم: ${s.go} · للدراسة: ${s.a_etudier} · تجاوز: ${s.no_go}`;
    }
    return `Bonjour,\n\nVoici votre synthèse du ${dateFr} :\n\n📋 Opportunités sélectionnées :\n${lignes.join("\n") || "  Aucune opportunité"}\n\n📊 GO : ${s.go} · À étudier : ${s.a_etudier} · NO-GO : ${s.no_go}`;
  }, [digestInfo, lang]);

  // filtres
  const [kw, setKw] = useState("");
  const [sector, setSector] = useState("all");
  const [city, setCity] = useState("all");
  const [verdict, setVerdict] = useState("all");
  const [otype, setOtype] = useState("all");
  const [sort, setSort] = useState("score");

  // drawer + notifications
  const [activeId, setActiveId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [notifOpen, setNotifOpen] = useState(false);

  // profil (démo)
  const [fName, setFName] = useState("Atlas Solutions");
  const [fSector, setFSector] = useState<keyof typeof SECTORS>("it");
  const [fSize, setFSize] = useState("pme");
  const [fRegions, setFRegions] = useState("Casablanca, Rabat");
  const [fGuarantee, setFGuarantee] = useState("50000");
  const [fBudgetMin, setFBudgetMin] = useState("100000");
  const [fBudgetMax, setFBudgetMax] = useState("3000000");
  const [fCerts, setFCerts] = useState("ISO 9001");
  const [fQualif, setFQualif] = useState("Classe II — Services");
  const [fExp, setFExp] = useState("8");
  const [fKeywords, setFKeywords] = useState("maintenance, informatique, support");

  // alertes (démo)
  const [waEnabled, setWaEnabled] = useState(true);
  const [mailEnabled, setMailEnabled] = useState(true);
  const [thresh, setThresh] = useState(70);

  const t = (key: string) => T[lang][key] ?? key;

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 3200);
  }

  async function downloadOriginal(reference: string) {
    setDownloading(reference);
    try {
      const { url } = await api.opportunityDocument(reference);
      window.location.assign(url);
    } catch {
      showToast(lang === "fr" ? "Document original indisponible." : "الملف الأصلي غير متاح.");
    } finally {
      setDownloading(null);
    }
  }

  function toggleLang() {
    const next: Lang = lang === "fr" ? "ar" : "fr";
    setLang(next);
    document.documentElement.lang = next;
    document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
  }

  function verdictPill(v: Verdict): { cls: string; label: string } {
    if (v === "go")
      return {
        cls: "bg-greenbg text-greenbrand border border-greenbrand/20",
        label: `✓ ${t("verdictGoPill")}`,
      };
    if (v === "study")
      return {
        cls: "bg-amberbg text-amberbrand border border-amberbrand/20",
        label: `! ${t("verdictStudyPill")}`,
      };
    return {
      cls: "bg-redbg text-redbrand border border-redbrand/20",
      label: `× ${t("verdictNogoPill")}`,
    };
  }

  // ---------------------------------------------------------- dérivés
  const sectors = useMemo(
    () => Array.from(new Set(opps.map((o) => o.sector))),
    [opps],
  );
  const cities = useMemo(
    () => Array.from(new Set(opps.map((o) => o.city))).sort(),
    [opps],
  );

  const filtered = useMemo(() => {
    const needle = kw.trim().toLowerCase();
    const out = opps.filter((o) => {
      const matchKw =
        !needle ||
        o.title[lang].toLowerCase().includes(needle) ||
        o.buyer[lang].toLowerCase().includes(needle) ||
        o.city.toLowerCase().includes(needle) ||
        o.source_ref.toLowerCase().includes(needle);
      const matchSector = sector === "all" || o.sector === sector;
      const matchCity = city === "all" || o.city === city;
      const matchVerdict = verdict === "all" || o.verdict === verdict;
      const matchType = otype === "all" || o.opportunity_type === otype;
      return matchKw && matchSector && matchCity && matchVerdict && matchType;
    });
    out.sort((a, b) =>
      sort === "deadline"
        ? (a.deadline || "9999").localeCompare(b.deadline || "9999")
        : b.match_score - a.match_score,
    );
    return out;
  }, [opps, kw, sector, city, verdict, otype, sort, lang]);

  const saved = useMemo(() => opps.filter((o) => o.saved), [opps]);
  const activeOpp = activeId ? opps.find((o) => o.id === activeId) : null;

  const stats = useMemo(
    () => ({
      new24: opps.filter((o) => o.is_new).length,
      go: opps.filter((o) => o.verdict === "go").length,
      study: opps.filter((o) => o.verdict === "study").length,
      saved: opps.filter((o) => o.saved).length,
    }),
    [opps],
  );

  const notifs = useMemo(
    () =>
      opps
        .filter((o) => o.verdict !== "nogo")
        .slice(0, 4)
        .map((o) => ({
          title: o.title[lang],
          city: o.city,
          score: o.match_score,
          deadline: o.deadline,
        })),
    [opps, lang],
  );

  // ---------------------------------------------------------- actions
  function toggleSave(o: Opp) {
    const prochain = !o.saved;
    setOpps((prev) =>
      prev.map((x) => (x.id === o.id ? { ...x, saved: prochain } : x)),
    );
    showToast(prochain ? t("savedToast") : t("removedToast"));
    void api.save(companyId, o.id, prochain).catch((err: Error) => {
      showToast(err.message);
    });
  }

  function changeStatus(id: string, status: Status) {
    setOpps((prev) => prev.map((x) => (x.id === id ? { ...x, status } : x)));
    const ref = opps.find((x) => x.id === id)?.id;
    if (ref) {
      void api.update(companyId, ref, status).catch((err: Error) => {
        showToast(err.message);
      });
    }
  }

  function saveNote(id: string, note: string) {
    setOpps((prev) => prev.map((x) => (x.id === id ? { ...x, note } : x)));
    const ref = opps.find((x) => x.id === id)?.id;
    if (ref) {
      void api.update(companyId, ref, undefined, note).catch((err: Error) => {
        showToast(err.message);
      });
    }
  }

  function resetFilters() {
    setKw("");
    setSector("all");
    setCity("all");
    setVerdict("all");
    setOtype("all");
    setSort("score");
  }

  // ---------------------------------------------------------- header
  const headerEl = (
    <header className="sticky top-0 z-40 bg-[#f5f0e6ed] backdrop-blur-md border-b border-line px-4 lg:px-8 py-3">
      <div className="max-w-[1400px] mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <a href="/" className="flex items-center gap-2 text-xl font-bold tracking-tight text-ink">
            <svg className="w-8 h-8 text-greenbrand" viewBox="0 0 40 40" fill="none" aria-hidden="true">
              <path d="M20 2 38 20 20 38 2 20Z" fill="currentColor" />
              <path d="M20 10 30 20 20 30 10 20Z" fill="#f5f0e6" />
              <path d="M20 15 25 20 20 25 15 20Z" fill="#c2603a" />
            </svg>
            <span className="font-display">Sou9na</span>
            <span className="text-[10px] uppercase tracking-wider bg-greenbg text-greenbrand px-2 py-0.5 rounded font-bold border border-greenbrand/20 hidden sm:inline-block">
              {t("espacePro")}
            </span>
          </a>
          <div className="hidden md:flex items-center relative w-64 lg:w-80">
            <svg
              className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 rtl:right-3 rtl:left-auto text-muted"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={kw}
              onChange={(e) => {
                setKw(e.target.value);
                setTab("feed");
              }}
              placeholder={t("searchPlaceholder")}
              className="w-full bg-white border border-line rounded-lg pl-9 rtl:pr-9 rtl:pl-3 pr-3 py-1.5 text-xs text-ink placeholder-muted focus:border-greenbrand focus:ring-1 focus:ring-greenbrand transition-all"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={toggleLang}
            type="button"
            className="border border-line bg-white hover:bg-paper px-3 py-1.5 rounded-md text-xs font-semibold text-ink transition-all"
          >
            {lang === "fr" ? "العربية" : "Français"}
          </button>

          <div className="relative">
            <button
              onClick={() => setNotifOpen((v) => !v)}
              type="button"
              className="border border-line bg-white hover:bg-paper p-2 rounded-md text-ink relative transition-all"
              aria-label={t("notifications")}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              {notifs.length > 0 && (
                <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-terra rounded-full ring-2 ring-white" />
              )}
            </button>
            {notifOpen && (
              <div className="absolute right-0 rtl:right-auto rtl:left-0 mt-2 w-80 bg-white border border-line rounded-lg shadow-xl p-3 z-50">
                <div className="flex items-center justify-between border-b border-line pb-2 mb-2">
                  <span className="text-xs font-bold text-ink">{t("notifTitle")}</span>
                  <span className="text-[10px] bg-greenbg text-greenbrand px-1.5 py-0.5 rounded font-bold">
                    {notifs.length}
                  </span>
                </div>
                <div className="space-y-2 text-xs max-h-72 overflow-y-auto">
                  {notifs.length === 0 && (
                    <p className="text-muted py-3 text-center">{t("noNotif")}</p>
                  )}
                  {notifs.map((n, i) => (
                    <div key={i} className="p-2 bg-paper/60 rounded border border-line/50">
                      <p className="font-semibold text-ink">
                        {t("match")} {n.score}% — {n.title}
                      </p>
                      <span className="text-[10px] text-muted">
                        {n.city} · {fmtDate(n.deadline, lang)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 pl-2 border-l rtl:border-l-0 rtl:border-r rtl:pl-0 rtl:pr-2 border-line">
            <div className="w-8 h-8 rounded-full bg-greenbrand text-white flex items-center justify-center font-bold text-xs shadow-sm">
              {companyInitials}
            </div>
            <div className="hidden lg:block text-left rtl:text-right">
              <div className="text-xs font-bold text-ink leading-none">{companyName}</div>
              <div className="text-[10px] text-muted mt-0.5">{fName}</div>
            </div>
            <button
              type="button"
              onClick={() => {
                clearAuth();
                window.location.href = "/";
              }}
              className="text-[11px] font-semibold text-muted hover:text-redbrand transition-colors ms-2"
            >
              {t("logout")}
            </button>
          </div>
        </div>
      </div>
    </header>
  );

  // ---------------------------------------------------------- tabs
  const tabsEl = (
    <nav className="bg-white border-b border-line px-4 lg:px-8">
      <div className="max-w-[1400px] mx-auto flex items-center gap-1 sm:gap-6 overflow-x-auto no-scrollbar py-1">
        {(
          [
            ["feed", t("tabFeed")],
            ["dossiers", t("tabDossiers")],
            ["profile", t("tabProfile")],
            ["alerts", t("tabAlerts")],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`tab-btn px-3 sm:px-4 py-3 text-xs sm:text-sm font-medium text-muted hover:text-ink transition-all flex items-center gap-2 whitespace-nowrap ${
              tab === id ? "active" : ""
            }`}
          >
            {label}
            {id === "dossiers" && (
              <span className="bg-paper text-ink border border-line text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                {saved.length}
              </span>
            )}
          </button>
        ))}
      </div>
    </nav>
  );

  // ---------------------------------------------------------- KPI
  const kpisEl = (
    <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[
        { value: stats.new24, cls: "text-ink", tag: "+24h", tagCls: "text-greenbrand bg-greenbg", title: t("kpi1Title"), sub: t("kpi1Sub") },
        { value: stats.go, cls: "text-greenbrand", tag: "GO", tagCls: "text-greenbrand bg-greenbg", title: t("kpi2Title"), sub: t("kpi2Sub") },
        { value: stats.study, cls: "text-amberbrand", tag: "60-79%", tagCls: "text-amberbrand bg-amberbg", title: t("kpi3Title"), sub: t("kpi3Sub") },
        { value: stats.saved, cls: "text-terra", tag: t("kpi4Tag"), tagCls: "text-muted bg-paper", title: t("kpi4Title"), sub: t("kpi4Sub") },
      ].map((k, i) => (
        <div key={i} className="bg-white border border-line rounded-lg p-4 shadow-sm">
          <div className="text-[11px] font-bold text-muted uppercase tracking-wider mb-1">
            {k.title}
          </div>
          <div className="flex items-baseline justify-between">
            <span className={`text-3xl font-bold font-display ${k.cls}`}>{k.value}</span>
            <span className={`text-xs px-2 py-0.5 rounded font-semibold ${k.tagCls}`}>{k.tag}</span>
          </div>
          <div className="text-[11px] text-muted mt-2">{k.sub}</div>
        </div>
      ))}
    </section>
  );

  // ---------------------------------------------------------- opp card
  function oppCard(o: Opp) {
    const pill = verdictPill(o.verdict);
    return (
      <article
        key={o.id}
        className="bg-white border border-line rounded-lg p-4 shadow-sm hover:shadow-md transition-all flex flex-col justify-between"
      >
        <div>
          <div className="flex items-start justify-between gap-2 border-b border-line/60 pb-3 mb-3">
            <div className="min-w-0">
              <span className="text-[10px] uppercase font-bold text-terra tracking-wider block">
                {o.source_ref}
              </span>
              <h3 className="font-display font-bold text-sm text-ink leading-snug mt-0.5 line-clamp-2">
                {o.title[lang]}
              </h3>
              <div className="text-[11px] text-muted mt-1">{o.buyer[lang]}</div>
              <div className="flex flex-wrap items-center gap-1 mt-1">
                {o.is_new && (
                  <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-greenbrand text-white">
                    {t("newBadge")}
                  </span>
                )}
                {o.opportunity_type !== "appel_offres" && (
                  <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amberbg text-amberbrand">
                    {o.opportunity_type === "bon_commande" ? t("typeBC") : t("typeConsult")}
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-col items-center justify-center flex-shrink-0">
              <div className="w-14 h-14 relative flex items-center justify-center">
                <svg className="ring-svg w-full h-full" viewBox="0 0 100 100">
                  <circle className="ring-track" cx="50" cy="50" r="40" />
                  <circle
                    className="ring-value"
                    cx="50"
                    cy="50"
                    r="40"
                    style={{ strokeDashoffset: ringOffset(o.match_score) }}
                  />
                </svg>
                <span className="absolute font-display font-bold text-sm text-ink">
                  {o.match_score}
                </span>
              </div>
              <span className="text-[9px] font-bold text-muted uppercase mt-0.5">{t("match")}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px] text-muted mb-3 bg-paper/50 p-2 rounded">
            <div>
              <span className="block text-[9px] font-bold uppercase text-muted">{t("keyDeadline")}</span>
              <strong className="text-ink font-semibold">◷ {fmtDate(o.deadline, lang)}{o.deadline_time && ` · ${o.deadline_time}`}</strong>
            </div>
            <div>
              <span className="block text-[9px] font-bold uppercase text-muted">{t("keyCity")}</span>
              <strong className="text-ink font-semibold">⌖ {o.city}</strong>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px] mb-3">
            <div><span className="block text-muted">{t("keyBudget")}</span>{fmtMoney(o.amount, lang)}</div>
            <div><span className="block text-muted">{t("keyGuarantee")}</span>{fmtMoney(o.guarantee, lang)}</div>
          </div>
          {o.reasons[0] && <p className="text-xs text-ink mb-3">{o.reasons[0]}</p>}
          {o.confidence && (
            <p className="text-[11px] text-muted mb-3">
              {lang === "fr" ? "Confiance de l’analyse" : "مستوى الثقة في التحليل"}{" · "}
              {lang === "fr"
                ? { faible: "faible", moyen: "moyenne", eleve: "élevée" }[o.confidence]
                : { faible: "منخفضة", moyen: "متوسطة", eleve: "مرتفعة" }[o.confidence]}
            </p>
          )}
          {o.risks.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-4">
              {o.risks.slice(0, 3).map((r, i) => (
                <span key={i} className="text-[10px] bg-paper border border-line px-1.5 py-0.5 rounded text-muted">
                  ! {t(r)}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="pt-3 border-t border-line flex items-center justify-between gap-2">
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold ${pill.cls}`}>
            {pill.label}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => downloadOriginal(o.id)}
              disabled={downloading !== null}
              className="text-xs font-semibold text-greenbrand px-2 py-1.5 rounded border border-line hover:bg-paper disabled:opacity-50"
              type="button"
            >
              {downloading === o.id ? "…" : lang === "fr" ? "Document" : "المستند"}
            </button>
            <button
              onClick={() => toggleSave(o)}
              className="p-1.5 rounded border border-line hover:bg-paper transition-all"
              aria-label="save"
              type="button"
            >
              <span className={o.saved ? "text-terra font-bold" : "text-muted"}>★</span>
            </button>
            <button
              onClick={() => setActiveId(o.id)}
              className="bg-greenbrand hover:bg-[#18553f] text-white text-xs font-bold px-3 py-1.5 rounded transition-all"
              type="button"
            >
              {t("seeAnalysis")}
            </button>
          </div>
        </div>
      </article>
    );
  }

  // ---------------------------------------------------------- feed
  const feedEl = (
    <section className="space-y-4">
      <div className="bg-white border border-line rounded-lg p-4 shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row items-center justify-between gap-3">
          <div className="w-full md:w-1/3">
            <input
              type="text"
              value={kw}
              onChange={(e) => setKw(e.target.value)}
              placeholder={t("filterKeyword")}
              className="w-full bg-paper/50 border border-line rounded-md px-3 py-2 text-xs text-ink placeholder-muted focus:bg-white focus:border-greenbrand focus:ring-1 focus:ring-greenbrand transition-all"
            />
          </div>
          <div className="w-full md:w-2/3 flex flex-wrap items-center justify-end gap-2 text-xs">
            <select
              value={sector}
              onChange={(e) => setSector(e.target.value)}
              className="flex-1 min-w-[130px] bg-paper/50 border border-line rounded-md px-2.5 py-2 text-ink focus:bg-white focus:border-greenbrand"
            >
              <option value="all">{t("allSectors")}</option>
              {sectors.map((s) => (
                <option key={s} value={s}>
                  {SECTORS[s][lang]}
                </option>
              ))}
            </select>
            <select
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="flex-1 min-w-[120px] bg-paper/50 border border-line rounded-md px-2.5 py-2 text-ink focus:bg-white focus:border-greenbrand"
            >
              <option value="all">{t("allCities")}</option>
              {cities.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <select
              value={verdict}
              onChange={(e) => setVerdict(e.target.value)}
              className="flex-1 min-w-[120px] bg-paper/50 border border-line rounded-md px-2.5 py-2 text-ink focus:bg-white focus:border-greenbrand"
            >
              <option value="all">{t("allVerdicts")}</option>
              <option value="go">{t("verdictGo")}</option>
              <option value="study">{t("verdictStudy")}</option>
              <option value="nogo">{t("verdictNogo")}</option>
            </select>
            <select
              value={otype}
              onChange={(e) => setOtype(e.target.value)}
              className="flex-1 min-w-[120px] bg-paper/50 border border-line rounded-md px-2.5 py-2 text-ink focus:bg-white focus:border-greenbrand"
            >
              <option value="all">{t("allTypes")}</option>
              <option value="appel_offres">{t("typeAO")}</option>
              <option value="bon_commande">{t("typeBC")}</option>
              <option value="consultation">{t("typeConsult")}</option>
            </select>
            <button
              onClick={resetFilters}
              className="bg-paper hover:bg-line border border-line text-muted hover:text-ink px-3 py-2 rounded-md font-semibold transition-all"
              type="button"
            >
              {t("resetBtn")}
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between pt-2 border-t border-line/60 text-xs text-muted">
          <div>
            <span className="font-bold text-ink">{filtered.length}</span> {t("oppsFound")}
          </div>
          <div className="flex items-center gap-2">
            <span>{t("sortBy")}</span>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="bg-transparent border-0 text-ink font-semibold focus:ring-0 cursor-pointer p-0 text-xs"
            >
              <option value="score">{t("sortMatch")}</option>
              <option value="deadline">{t("sortDeadline")}</option>
            </select>
          </div>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white border border-dashed border-line rounded-lg p-12 text-center text-muted">
          <h3 className="text-base font-bold text-ink">{t("noResultsTitle")}</h3>
          <p className="text-xs mt-1">{t("noResultsText")}</p>
          <button
            onClick={resetFilters}
            className="mt-4 bg-greenbrand text-white text-xs font-bold px-4 py-2 rounded hover:bg-[#18553f] transition-all"
            type="button"
          >
            {t("resetBtn")}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(oppCard)}
        </div>
      )}
    </section>
  );

  // ---------------------------------------------------------- dossiers
  function dossierCard(o: Opp) {
    return (
      <div key={o.id} className="bg-white border border-line rounded p-3 shadow-sm space-y-2 text-xs">
        <div className="flex items-start justify-between gap-2">
          <h4 className="font-bold text-ink leading-tight">{o.title[lang]}</h4>
          <span className="font-display font-bold text-greenbrand text-xs">{o.match_score}%</span>
        </div>
        <div className="text-[11px] text-muted">
          {o.city} · {fmtDate(o.deadline, lang)}
        </div>
        <input
          type="text"
          defaultValue={o.note}
          onBlur={(e) => saveNote(o.id, e.target.value)}
          placeholder={t("notePlaceholder")}
          className="w-full bg-paper/50 border border-line rounded px-2 py-1 text-[11px] text-ink placeholder-muted focus:bg-white"
        />
        <div className="flex items-center justify-between pt-1 text-[10px]">
          <select
            value={o.status}
            onChange={(e) => changeStatus(o.id, e.target.value as Status)}
            className="bg-paper border border-line rounded px-1.5 py-0.5 text-ink font-semibold"
          >
            <option value="study">{t("statusStudy")}</option>
            <option value="prep">{t("statusPrep")}</option>
            <option value="submitted">{t("statusSubmitted")}</option>
          </select>
          <button
            onClick={() => toggleSave(o)}
            className="text-redbrand font-bold hover:underline"
            type="button"
          >
            {t("remove")}
          </button>
        </div>
      </div>
    );
  }

  const dossiersEl = (
    <section className="space-y-4">
      <div className="bg-white border border-line rounded-lg p-4 shadow-sm flex items-center justify-between">
        <div>
          <h2 className="font-display text-xl font-bold text-ink">{t("dossiersTitle")}</h2>
          <p className="text-xs text-muted">{t("dossiersSub")}</p>
        </div>
        <button
          onClick={() => setTab("feed")}
          className="bg-greenbrand text-white px-3 py-1.5 rounded text-xs font-bold hover:bg-[#18553f] transition-all"
          type="button"
        >
          + {t("tabFeed")}
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {(
          [
            ["study", t("colStudy"), t("emptyStudy"), "bg-amberbrand"],
            ["prep", t("colPrep"), t("emptyPrep"), "bg-terra"],
            ["submitted", t("colSubmitted"), t("emptySubmitted"), "bg-greenbrand"],
          ] as const
        ).map(([status, label, empty, dot]) => {
          const list = saved.filter((o) => o.status === status);
          return (
            <div key={status} className="bg-paper/60 border border-line rounded-lg p-3 space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-line">
                <span className="text-xs font-bold text-ink flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${dot}`} />
                  {label}
                </span>
                <span className="text-xs font-bold text-muted">{list.length}</span>
              </div>
              <div className="space-y-3">
                {list.length === 0 ? (
                  <div className="text-center text-xs text-muted py-4">{empty}</div>
                ) : (
                  list.map(dossierCard)
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );

  // ---------------------------------------------------------- profil
  const profileEl = (
    <section className="space-y-4">
      <div className="bg-white border border-line rounded-lg p-6 shadow-sm max-w-3xl mx-auto space-y-6">
        <div>
          <h2 className="font-display text-2xl font-bold text-ink">{t("profileHeading")}</h2>
          <p className="text-xs text-muted mt-1">{t("profileDesc")}</p>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            showToast(t("profileSavedToast"));
          }}
          className="space-y-4"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block text-xs font-bold text-ink">
              {t("profileNameLabel")}
              <input value={fName} onChange={(e) => setFName(e.target.value)}
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("profileSectorLabel")}
              <select value={fSector} onChange={(e) => setFSector(e.target.value as keyof typeof SECTORS)}
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink">
                {sectors.map((s) => (
                  <option key={s} value={s}>{SECTORS[s][lang]}</option>
                ))}
              </select>
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("profileSizeLabel")}
              <select value={fSize} onChange={(e) => setFSize(e.target.value)}
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink">
                <option value="petite">{t("sizeSmall")}</option>
                <option value="pme">{t("sizePme")}</option>
                <option value="grande">{t("sizeLarge")}</option>
              </select>
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("profileCityLabel")}
              <input value={fRegions} onChange={(e) => setFRegions(e.target.value)} placeholder="Casablanca, Rabat"
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("profileGuaranteeLabel")}
              <input type="number" min={0} value={fGuarantee} onChange={(e) => setFGuarantee(e.target.value)}
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("budgetMin")}
              <input type="number" min={0} value={fBudgetMin} onChange={(e) => setFBudgetMin(e.target.value)}
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("budgetMax")}
              <input type="number" min={0} value={fBudgetMax} onChange={(e) => setFBudgetMax(e.target.value)}
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("certsLabel")}
              <input value={fCerts} onChange={(e) => setFCerts(e.target.value)} placeholder="ISO 9001, ISO 14001"
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("qualifLabel")}
              <input value={fQualif} onChange={(e) => setFQualif(e.target.value)} placeholder="Classe II — Travaux publics"
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("expLabel")}
              <input type="number" min={0} value={fExp} onChange={(e) => setFExp(e.target.value)}
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
            <label className="block text-xs font-bold text-ink">
              {t("profileKeywordsLabel")}
              <input value={fKeywords} onChange={(e) => setFKeywords(e.target.value)} placeholder="maintenance, informatique"
                className="mt-1 w-full bg-paper/50 border border-line rounded px-3 py-2 text-xs font-semibold text-ink" />
            </label>
          </div>
          <div className="pt-4 border-t border-line flex items-center justify-between">
            <span className="text-[11px] text-muted">{t("profileNote")}</span>
            <button type="submit"
              className="bg-greenbrand hover:bg-[#18553f] text-white px-5 py-2 rounded text-xs font-bold transition-all shadow-sm">
              {t("saveProfileBtn")}
            </button>
          </div>
        </form>
      </div>
    </section>
  );

  // ---------------------------------------------------------- alertes
  const alertsEl = (
    <section className="space-y-4">
      <div className="bg-white border border-line rounded-lg p-6 shadow-sm max-w-3xl mx-auto space-y-6">
        <div>
          <h2 className="font-display text-2xl font-bold text-ink">{t("alertsHeading")}</h2>
          <p className="text-xs text-muted mt-1">{t("alertsDesc")}</p>
        </div>
        <div className="space-y-4 text-xs">
          <div className="p-4 bg-paper/50 border border-line rounded-lg flex items-center justify-between">
            <div>
              <div className="font-bold text-ink">{t("alertDailyTitle")}</div>
              <div className="text-muted text-[11px]">{t("alertDailySub")}</div>
            </div>
            <input type="checkbox" checked={mailEnabled} onChange={(e) => setMailEnabled(e.target.checked)}
              className="w-4 h-4 accent-greenbrand cursor-pointer" />
          </div>
          <div className="p-4 bg-paper/50 border border-line rounded-lg flex items-center justify-between">
            <div>
              <div className="font-bold text-ink">{t("alertWaTitle")}</div>
              <div className="text-muted text-[11px]">{t("alertWaSub")}</div>
            </div>
            <input type="checkbox" checked={waEnabled} onChange={(e) => setWaEnabled(e.target.checked)}
              className="w-4 h-4 accent-greenbrand cursor-pointer" />
          </div>
          <div className="p-4 bg-paper/50 border border-line rounded-lg space-y-2">
            <div className="flex items-center justify-between font-bold text-ink">
              <span>{t("alertThreshTitle")}</span>
              <span className="text-greenbrand font-extrabold text-sm">{thresh}%</span>
            </div>
            <input type="range" min={50} max={90} step={5} value={thresh}
              onChange={(e) => setThresh(parseInt(e.target.value, 10))}
              className="w-full accent-greenbrand cursor-pointer" />
            <div className="flex justify-between text-[10px] text-muted">
              <span>50%</span><span>70%</span><span>90%</span>
            </div>
          </div>
        </div>
        <div className="pt-4 border-t border-line text-right rtl:text-left">
          <button onClick={() => showToast(t("alertSavedToast"))}
            className="bg-greenbrand hover:bg-[#18553f] text-white px-5 py-2 rounded text-xs font-bold transition-all shadow-sm"
            type="button">
            {t("saveAlertsBtn")}
          </button>
        </div>
        <div className="pt-4 border-t border-line">
          <h3 className="text-xs font-bold text-ink uppercase tracking-wider mb-2">{t("lastDigest")}</h3>
          <div className="hint mb-2">
            {digestInfo?.date || "—"} · {lang === "fr" ? "email" : "بريد إلكتروني"}
          </div>
          <pre className="digest-pre">{digestTexte}</pre>
        </div>
      </div>
    </section>
  );

  // ---------------------------------------------------------- drawer
  const breakdownKeys: Array<[string, string, number]> = [
    ["secteur", t("sectorFit"), 25],
    ["keywords", lang === "fr" ? "Qualifications" : "المؤهلات", 15],
    ["region", t("regionFit"), 15],
    ["size", lang === "fr" ? "Capacité financière" : "القدرة المالية", 20],
    ["caution", t("keyGuarantee"), 10],
    ["delai", lang === "fr" ? "Délai d’exécution" : "مدة التنفيذ", 10],
    ["history", t("historyFit"), 5],
  ];

  const drawerEl = (
    <div
      className={`drawer-backdrop ${activeOpp ? "open" : ""}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) setActiveId(null);
      }}
      aria-hidden={!activeOpp}
    >
      <aside className="drawer-panel p-6">
        {activeOpp && (() => {
          const pill = verdictPill(activeOpp.verdict);
          const bd = activeOpp.breakdown || {};
          return (
            <div className="flex flex-col justify-between min-h-full">
              <div className="space-y-6">
                <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
                  <div>
                    <span className="text-[10px] uppercase font-bold tracking-wider text-terra">
                      {t("drawerSubtitle")}
                    </span>
                    <h2 className="font-display text-xl font-bold text-ink leading-tight mt-1">
                      {activeOpp.title[lang]}
                    </h2>
                    <p className="text-xs text-muted mt-1">
                      {activeOpp.buyer[lang]} · {activeOpp.source_ref}
                    </p>
                  </div>
                  <button onClick={() => setActiveId(null)} type="button"
                    className="border border-line rounded-md p-1.5 hover:bg-paper text-ink transition-all"
                    aria-label={t("closeBtn")}>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="bg-paper/60 border border-line rounded-lg p-4 flex items-center gap-4">
                  <div className="relative w-20 h-20 flex-shrink-0">
                    <svg className="ring-svg w-full h-full" viewBox="0 0 100 100">
                      <circle className="ring-track" cx="50" cy="50" r="40" />
                      <circle className="ring-value" cx="50" cy="50" r="40"
                        style={{ strokeDashoffset: ringOffset(activeOpp.match_score) }} />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                      <span className="font-display font-bold text-xl text-ink leading-none">
                        {activeOpp.match_score}
                      </span>
                      <span className="text-[8px] font-bold text-muted uppercase mt-0.5">
                        {t("matchLabel")}
                      </span>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className={`inline-flex items-center gap-1 font-bold text-xs px-2 py-0.5 rounded ${pill.cls}`}>
                      {pill.label}
                    </span>
                    <p className="text-xs text-muted leading-snug">
                      {activeOpp.reasons.map((r) => t(r)).join(" ") || "—"}
                    </p>
                  </div>
                </div>

                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-ink uppercase tracking-wider border-b border-line pb-1">
                    {t("breakdownHeader")}
                  </h3>
                  <div className="space-y-2 text-xs">
                    {breakdownKeys.map(([k, label, maximum]) => {
                      const val = bd[k];
                      if (typeof val !== "number") return null;
                      return (
                        <div key={k} className="space-y-0.5">
                          <div className="flex justify-between font-semibold text-ink">
                            <span>{label}</span>
                            <span>{val} / {maximum}</span>
                          </div>
                          <div className="h-1.5 w-full bg-paper rounded-full overflow-hidden border border-line/40">
                            <div className="h-full bg-greenbrand" style={{ width: `${Math.min(100, val / maximum * 100)}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {activeOpp.citation?.reference && (
                  <p className="text-xs text-muted">
                    {lang === "fr" ? "Pièce citée" : "المستند المشار إليه"}{" · "}
                    {activeOpp.citation.reference}
                    {activeOpp.citation.pages && ` · p. ${activeOpp.citation.pages}`}
                  </p>
                )}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {[
                    [t("keyDeadline"), [fmtDate(activeOpp.deadline, lang), activeOpp.deadline_time].filter(Boolean).join(" · ")],
                    ...(activeOpp.publication_date ? [[lang === "fr" ? "Publication" : "النشر",
                      [fmtDate(activeOpp.publication_date, lang), activeOpp.publication_time].filter(Boolean).join(" · ")]] : []),
                    [t("keyCity"), activeOpp.city],
                    [t("keyBudget"), fmtMoney(activeOpp.amount, lang)],
                    [t("keyGuarantee"), fmtMoney(activeOpp.guarantee, lang)],
                  ].map(([label, value], i) => (
                    <div key={i} className="bg-paper p-2.5 rounded border border-line">
                      <span className="text-[10px] text-muted block">{label}</span>
                      <strong className="text-ink font-bold">{value}</strong>
                    </div>
                  ))}
                </div>

                <div className="space-y-2">
                  <h3 className="text-xs font-bold text-ink uppercase tracking-wider border-b border-line pb-1">
                    {t("risksHeader")}
                  </h3>
                  <p className="text-[11px] text-muted leading-snug">{t("risksNote")}</p>
                  <div className="space-y-2">
                    {activeOpp.risks.length === 0 ? (
                      <p className="text-xs text-muted">{t("noRisks")}</p>
                    ) : (
                      activeOpp.risks.map((r, i) => (
                        <div key={i} className="p-2 bg-paper/60 border border-line rounded flex items-center gap-2 text-xs">
                          <span className="text-amberbrand font-bold">!</span>
                          <span className="font-semibold text-ink">{t(r)}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {!!activeOpp.recommendations?.length && (
                  <div className="space-y-2">
                    <h3 className="text-xs font-bold text-ink uppercase tracking-wider border-b border-line pb-1">
                      {t("recommendationsHeader")}
                    </h3>
                    <ol className="space-y-1.5 text-xs text-ink">
                      {activeOpp.recommendations.map((rec, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-greenbrand/10 text-[9px] font-bold text-greenbrand">
                            {i + 1}
                          </span>
                          <span>{t(rec)}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}

                {activeOpp.advice && (
                  <div className="p-3 bg-greenbg/60 border border-greenbrand/20 rounded text-xs text-ink">
                    <span className="font-bold text-greenbrand block mb-1">{t("adviceHeader")}</span>
                    <p className="leading-snug">{t(activeOpp.advice)}</p>
                  </div>
                )}

                <div className="p-3 bg-paper/40 border border-line rounded text-xs space-y-1">
                  <span className="font-bold text-ink block">{t("officialSourceTitle")}</span>
                  <p className="text-[11px] text-muted">{t("officialSourceDesc")}</p>
                  <span className="text-greenbrand font-bold text-xs inline-flex items-center gap-1 mt-1">
                    {t("openSourceBtn")} ↗
                  </span>
                </div>
              </div>

              <div className="pt-4 border-t border-line mt-6 flex items-center justify-between gap-2">
                <button
                  onClick={() => toggleSave(activeOpp)}
                  className={`flex-1 py-2 rounded text-xs font-bold transition-all border ${
                    activeOpp.saved
                      ? "bg-greenbg text-greenbrand border-greenbrand/30"
                      : "bg-paper hover:bg-line border-line text-ink"
                  }`}
                  type="button"
                >
                  ★ {activeOpp.saved ? t("savedDossier") : t("saveDossier")}
                </button>
                <button
                  onClick={() => {
                    const reference = activeOpp.id;
                    setActiveId(null);
                    router.push(`/offres?reference=${encodeURIComponent(reference)}`);
                  }}
                  className="flex-1 bg-greenbrand hover:bg-[#18553f] text-white py-2 rounded text-xs font-bold transition-all"
                  type="button">
                  {t("openFull")} →
                </button>
                <button onClick={() => setActiveId(null)}
                  className="flex-1 border border-line bg-white text-ink py-2 rounded text-xs font-bold transition-all hover:bg-paper"
                  type="button">
                  {t("closeBtn")}
                </button>
              </div>
            </div>
          );
        })()}
      </aside>
    </div>
  );

  // ---------------------------------------------------------- render
  const preparationSteps = lang === "fr"
    ? [
        "Synchronisation de votre entreprise et de son profil",
        "Analyse des offres documentées correspondantes",
        "Préparation de votre sélection et de vos alertes",
      ]
    : [
        "مزامنة شركتك وملفها التعريفي",
        "تحليل العروض الموثّقة المطابقة",
        "تجهيز قائمتك المختارة وتنبيهاتك",
      ];

  // Le chargement « pro » en 3 étapes est réservé à la PREMIÈRE analyse :
  // le temps est utilisé par le pipeline pour calculer scores et verdicts.
  // Les simples rechargements gardent un loader léger et discret.
  if (initStatus === "running") {
    return (
      <BrandLoader
        label={lang === "fr"
          ? "Préparation de votre espace Sou9na…"
          : "جارٍ تجهيز مساحة Sou9na الخاصة بك…"}
        showProgress
        steps={preparationSteps}
      />
    );
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      {headerEl}
      {tabsEl}

      <main className="max-w-[1400px] mx-auto px-4 lg:px-8 py-6 space-y-6">
        {apiError && (
          <div className="rounded border border-redbrand bg-red-50 px-4 py-3 text-xs text-redbrand">
            {lang === "fr"
              ? `Données indisponibles : ${apiError}. Vérifiez que l'API est démarrée.`
              : `البيانات غير متوفرة: ${apiError}. تحقق من تشغيل الواجهة الخلفية.`}
          </div>
        )}
        {loading && (
          <div className="text-xs text-muted">
            {lang === "fr" ? "Chargement des données réelles…" : "جارٍ تحميل البيانات الحقيقية…"}
          </div>
        )}
        {initStatus === "error" && (
          <div role="alert" className="rounded-lg border border-line bg-white p-4 text-sm text-ink">
            {lang === "fr"
              ? "La première analyse n’a pas abouti. Contactez Sou9na pour relancer la préparation."
              : "تعذّر إتمام التحليل الأول. تواصل مع Sou9na لإعادة تشغيله."}
          </div>
        )}
        {tab === "feed" && initStatus === "ready" && (
          <>
            {kpisEl}
            {feedEl}
          </>
        )}
        {tab === "dossiers" && dossiersEl}
        {tab === "profile" && profileEl}
        {tab === "alerts" && alertsEl}
      </main>

      <footer className="border-t border-line py-5 text-center text-[11px] text-muted">
        {t("footer")}
      </footer>

      {drawerEl}

      {companyId && <ChatPanel lang={lang} companyId={companyId} />}

      {toast && (
        <div className="fixed bottom-5 right-5 z-[80] bg-ink text-white px-4 py-3 rounded-md shadow-xl text-xs max-w-sm">
          {toast}
        </div>
      )}
    </div>
  );
}
