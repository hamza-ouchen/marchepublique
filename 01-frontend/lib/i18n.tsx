"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";

export type Lang = "fr" | "ar";

const STORAGE_KEY = "sou9na_lang";

export const DICTIONARY: Record<string, Record<Lang, string>> = {
  // Commun / navigation
  "common.login": { fr: "Se connecter", ar: "تسجيل الدخول" },
  "common.signup": { fr: "Creer un compte", ar: "إنشاء حساب" },
  "common.logout": { fr: "Deconnexion", ar: "تسجيل الخروج" },
  "common.spaceAdmin": { fr: "Espace Admin", ar: "فضاء المشرف" },
  "common.spaceUser": { fr: "Espace TPME", ar: "فضاء المقاولة" },
  "common.email": { fr: "Email", ar: "البريد الإلكتروني" },
  "common.password": { fr: "Mot de passe", ar: "كلمة السر" },
  "common.select": { fr: "Selectionner...", ar: "اختر..." },

  "auth.phone": { fr: "Numero WhatsApp", ar: "رقم واتساب" },
  "auth.phoneHint": {
    fr: "Format international, ex. 212612345678",
    ar: "صيغة دولية، مثال 212612345678",
  },
  "auth.sendCode": { fr: "Envoyer le code", ar: "إرسال الرمز" },
  "auth.sending": { fr: "Envoi...", ar: "جاري الإرسال..." },
  "auth.enterCode": { fr: "Code recu par WhatsApp", ar: "الرمز المستلم عبر واتساب" },
  "auth.codeSentTo": { fr: "Un code a 6 chiffres a ete envoye par WhatsApp.", ar: "تم إرسال رمز من 6 أرقام عبر واتساب." },
  "auth.verify": { fr: "Verifier", ar: "تأكيد" },
  "auth.verifying": { fr: "Verification...", ar: "جاري التحقق..." },
  "auth.changeNumber": { fr: "Changer de numero", ar: "تغيير الرقم" },
  "auth.resend": { fr: "Renvoyer le code", ar: "إعادة إرسال الرمز" },
  "auth.testMode": {
    fr: "Mode test — backend non connecte, aucun WhatsApp reel envoye.",
    ar: "وضع تجريبي — الخادم غير متصل، لا يتم إرسال واتساب حقيقي.",
  },

  "nav.dashboard": { fr: "Tableau de bord", ar: "لوحة التحكم" },
  "nav.conversations": { fr: "Conversations", ar: "المحادثات" },
  "nav.clients": { fr: "Clients (TPME)", ar: "العملاء (المقاولات)" },
  "nav.history": { fr: "Historique", ar: "السجل" },
  "nav.profile": { fr: "Mon profil", ar: "ملفي الشخصي" },
  "nav.dossiers": { fr: "Dossiers", ar: "الملفات" },

  // Landing
  "landing.badge": {
    fr: "Plateforme IA marches publics",
    ar: "منصة ذكاء اصطناعي للصفقات العمومية",
  },
  "landing.title.a": { fr: "Repondez aux appels d'offres ", ar: "أجب عن طلبات العروض " },
  "landing.title.b": {
    fr: "sans rater une ligne.",
    ar: "دون أن تفوتك أي تفاصيل.",
  },
  "landing.subtitle": {
    fr: "Sou9na accompagne votre TPME sur WhatsApp — en francais, arabe ou darija. Reponses sourcees, et toujours une confirmation humaine avant toute action sensible.",
    ar: "سوقنا يواكب مقاولتك عبر واتساب — بالفرنسية أو العربية أو الدارجة. أجوبة موثقة بمصادرها، ودائما تأكيد بشري قبل أي إجراء حساس.",
  },
  "landing.ctaPrimary": { fr: "Creer mon compte TPME", ar: "إنشاء حساب مقاولتي" },
  "landing.ctaSecondary": { fr: "J'ai deja un compte", ar: "لدي حساب من قبل" },
  "landing.ctaNote": {
    fr: "Gratuit pour commencer · Aucune carte bancaire requise",
    ar: "مجاني للانطلاق · لا حاجة لبطاقة بنكية",
  },
  "landing.feature1.title": { fr: "Sur WhatsApp", ar: "على واتساب" },
  "landing.feature1.sub": { fr: "Pas d'app a installer", ar: "بدون تطبيق تثبّته" },
  "landing.feature2.title": { fr: "FR / AR / Darija", ar: "فرنسية / عربية / دارجة" },
  "landing.feature2.sub": { fr: "Dans votre langue", ar: "بلغتك" },
  "landing.feature3.title": { fr: "Confirmation humaine", ar: "تأكيد بشري" },
  "landing.feature3.sub": { fr: "Jamais d'action seule", ar: "لا إجراء بمفرده أبدا" },

  // Login
  "login.title": { fr: "Connexion", ar: "تسجيل الدخول" },
  "login.subtitle": {
    fr: "Choisissez votre espace puis connectez-vous.",
    ar: "اختر فضاءك ثم سجّل دخولك.",
  },
  "login.noAccount": { fr: "Pas encore de compte ?", ar: "ليس لديك حساب بعد؟" },
  "login.panel.badge": { fr: "Plateforme marches publics", ar: "منصة الصفقات العمومية" },
  "login.panel.title": {
    fr: "L'assistant IA pour vos marches publics",
    ar: "المساعد الذكي لصفقاتكم العمومية",
  },
  "login.panel.text": {
    fr: "Sou9na accompagne les TPME marocaines sur WhatsApp : questions, suivi de dossiers, et confirmation humaine a chaque etape sensible.",
    ar: "سوقنا يواكب المقاولات المغربية الصغرى والمتوسطة عبر واتساب: أسئلة، تتبع الملفات، وتأكيد بشري في كل خطوة حساسة.",
  },
  "login.error.default": { fr: "Erreur de connexion.", ar: "خطأ في تسجيل الدخول." },
  "login.error.notAdmin": {
    fr: "Ce compte n'est pas un compte Admin. Choisissez l'espace TPME.",
    ar: "هذا الحساب ليس حساب مشرف. اختر فضاء المقاولة.",
  },
  "login.error.notUser": {
    fr: "Ce compte est un compte Admin. Choisissez l'espace Admin.",
    ar: "هذا الحساب هو حساب مشرف. اختر فضاء المشرف.",
  },

  // Signup
  "signup.badge": { fr: "Inscription TPME", ar: "تسجيل مقاولة" },
  "signup.title": { fr: "Creer votre compte TPME", ar: "إنشاء حساب مقاولتك" },
  "signup.subtitle": {
    fr: "Quelques informations pour commencer avec Sou9na.",
    ar: "بعض المعلومات للانطلاق مع سوقنا.",
  },
  "signup.fullName": { fr: "Nom complet", ar: "الاسم الكامل" },
  "signup.phone": { fr: "Telephone", ar: "الهاتف" },
  "signup.company": { fr: "Entreprise", ar: "المقاولة" },
  "signup.iceHint": {
    fr: "Identifiant Commun de l'Entreprise (optionnel)",
    ar: "المعرف الموحد للمقاولة (اختياري)",
  },
  "signup.sector": { fr: "Secteur d'activite", ar: "قطاع النشاط" },
  "signup.region": { fr: "Region", ar: "الجهة" },
  "signup.qualifications": {
    fr: "Qualifications / certifications",
    ar: "التأهيلات / الشهادات",
  },
  "signup.qualificationsHint": {
    fr: "Optionnel — utile pour verifier l'eligibilite a certains appels d'offres",
    ar: "اختياري — مفيد للتحقق من الأهلية لبعض طلبات العروض",
  },
  "signup.submit": { fr: "Creer mon compte", ar: "إنشاء حسابي" },
  "signup.alreadyRegistered": { fr: "Deja inscrit ?", ar: "مسجل من قبل؟" },

  "profile.title": { fr: "Mon profil", ar: "ملفي الشخصي" },
  "profile.subtitle": { fr: "Vos informations chez Sou9na.", ar: "معلوماتك عند سوقنا." },
  "profile.hitlNotice": {
    fr: "Une demande de modification envoyee ici depuis WhatsApp passe par une confirmation humaine (HITL) avant d'etre appliquee. Ici, dans le prototype, la sauvegarde est directe.",
    ar: "طلب التعديل المرسل عبر واتساب يمر بتأكيد بشري (HITL) قبل تطبيقه. هنا، في هذا النموذج التجريبي، الحفظ مباشر.",
  },
  "profile.notEditable": { fr: "Identifiant de connexion — non modifiable", ar: "رقم تسجيل الدخول — غير قابل للتعديل" },
  "profile.save": { fr: "Enregistrer", ar: "حفظ" },
  "profile.saved": { fr: "Enregistre", ar: "تم الحفظ" },

  "dossiers.title": { fr: "Dossiers", ar: "الملفات" },
  "dossiers.subtitle": {
    fr: "Appels d'offres correspondant a votre profil, tries par Match decroissant.",
    ar: "طلبات العروض المطابقة لملفك، مرتبة حسب نسبة التوافق تنازليا.",
  },
  "dossiers.filter.sector": { fr: "Secteur", ar: "القطاع" },
  "dossiers.filter.region": { fr: "Region", ar: "الجهة" },
  "dossiers.filter.verdict": { fr: "Verdict", ar: "القرار" },
  "dossiers.filter.all": { fr: "Tous", ar: "الكل" },
  "dossiers.filter.minAmount": { fr: "Montant min. (MAD)", ar: "الحد الأدنى للمبلغ (درهم)" },
  "dossiers.match": { fr: "Match", ar: "التوافق" },
  "dossiers.deadline": { fr: "Remise", ar: "آخر أجل" },
  "dossiers.amount": { fr: "Montant", ar: "المبلغ" },
  "dossiers.empty": { fr: "Aucun dossier ne correspond a ces filtres.", ar: "لا يوجد ملف يطابق هذه المرشحات." },
  "dossiers.viewDetail": { fr: "Voir la fiche", ar: "عرض الملف" },
  "dossiers.favoriAdd": { fr: "Ajouter aux favoris", ar: "إضافة إلى المفضلة" },
  "dossiers.favoriRemove": { fr: "Retirer des favoris", ar: "إزالة من المفضلة" },

  "dossier.back": { fr: "Retour aux dossiers", ar: "الرجوع إلى الملفات" },
  "dossier.scoreDetail": { fr: "Detail du score", ar: "تفاصيل النقاط" },
  "dossier.pointsLost": { fr: "Points perdus", ar: "النقاط المفقودة" },
  "dossier.controls": { fr: "Controles d'eligibilite", ar: "فحوصات الأهلية" },
  "dossier.risks": { fr: "Risques a verifier", ar: "مخاطر للتحقق منها" },
  "dossier.sources": { fr: "Sources / justifications", ar: "المصادر / التبريرات" },
  "dossier.caution": { fr: "Caution", ar: "الضمان" },
  "dossier.delay": { fr: "Delai", ar: "الأجل" },
  "dossier.publication": { fr: "Publication", ar: "النشر" },
  "dossier.remise": { fr: "Remise des offres", ar: "تسليم العروض" },
  "dossier.qualifications": { fr: "Qualifications exigees", ar: "التأهيلات المطلوبة" },
  "dossier.status": { fr: "Statut", ar: "الحالة" },
  "dossier.noRisk": { fr: "Aucun risque identifie.", ar: "لا توجد مخاطر محددة." },

  "controle.caution_vs_capacite": { fr: "Caution vs capacite financiere", ar: "الضمان مقابل القدرة المالية" },
  "controle.ice_attestations": { fr: "ICE et attestations", ar: "ICE والشهادات" },
  "controle.qualifications": { fr: "Qualifications exigees", ar: "التأهيلات المطلوبة" },
  "controle.delai_atteignable": { fr: "Delai atteignable", ar: "الأجل القابل للتحقيق" },
  "controle.ok": { fr: "OK", ar: "جيد" },
  "controle.risque": { fr: "Risque", ar: "خطر" },
  "controle.ko": { fr: "Eliminatoire", ar: "إقصائي" },

  "dossiers.favorisOnly": { fr: "Favoris seulement", ar: "المفضلة فقط" },

  "nav.team": { fr: "Equipe", ar: "الفريق" },
  "team.title": { fr: "Gestion d'equipe", ar: "تدبير الفريق" },
  "team.subtitle": { fr: "Membres de votre equipe sur le plan 499.", ar: "أعضاء فريقكم في العرض 499." },
  "team.seatsUsed": { fr: "sieges utilises", ar: "مقاعد مستعملة" },
  "team.seatLimitReached": {
    fr: "Limite de sieges atteinte pour ce plan. Contactez-nous pour passer a un plan superieur.",
    ar: "تم الوصول إلى الحد الأقصى للمقاعد في هذا العرض. تواصلوا معنا للانتقال إلى عرض أعلى.",
  },
  "team.inviteTitle": { fr: "Inviter un membre", ar: "دعوة عضو" },
  "team.memberName": { fr: "Nom du membre", ar: "اسم العضو" },
  "team.invite": { fr: "Inviter", ar: "دعوة" },
  "team.remove": { fr: "Retirer", ar: "إزالة" },
  "team.role.titulaire": { fr: "Titulaire", ar: "المسؤول الرئيسي" },
  "team.role.membre": { fr: "Membre", ar: "عضو" },
  "team.since": { fr: "Depuis", ar: "منذ" },
  "team.placeholderNotice": {
    fr: "La limite de sieges du plan 499 n'est pas encore fixee officiellement — valeur provisoire en attendant confirmation de l'equipe.",
    ar: "الحد الأقصى لمقاعد العرض 499 لم يُحدد رسميا بعد — قيمة مؤقتة في انتظار تأكيد الفريق.",
  },

  "status.title": { fr: "Sante du service", ar: "حالة الخدمة" },
  "status.subtitle": {
    fr: "Transparence sur le fonctionnement de Sou9na, en temps reel.",
    ar: "شفافية حول عمل سوقنا، في الوقت الحقيقي.",
  },
  "status.operationnel": { fr: "Operationnel", ar: "يعمل بشكل جيد" },
  "status.degrade": { fr: "Mode degrade", ar: "وضع متدهور" },
  "status.panne": { fr: "Panne", ar: "عطل" },
  "status.lastCollect": { fr: "Derniere collecte", ar: "آخر تجميع للمعطيات" },
  "status.offersCollected": { fr: "Avis collectes (24h)", ar: "طلبات العروض المجمعة (24 سا)" },
  "status.digestStatus": { fr: "Digest quotidien", ar: "الملخص اليومي" },
  "status.digestOnTime": { fr: "Livre a temps", ar: "تم إرساله في الوقت" },
  "status.digestLate": { fr: "Retarde", ar: "متأخر" },
  "status.digestSla": { fr: "Taux de ponctualite (30j)", ar: "نسبة الالتزام بالوقت (30 يوما)" },
  "status.channels": { fr: "Canaux de distribution", ar: "قنوات التوزيع" },
  "status.incidents": { fr: "Historique des incidents", ar: "سجل الأعطال" },
  "status.noIncident": { fr: "Aucun incident recent.", ar: "لا عطل حديث." },
  "status.resolved": { fr: "Resolu", ar: "تم الحل" },
  "status.channel.ok": { fr: "Operationnel", ar: "يعمل" },
  "status.channel.degrade": { fr: "Degrade", ar: "متدهور" },
  "status.channel.indisponible": { fr: "Indisponible", ar: "غير متاح" },
  "status.backLink": { fr: "Retour a l'accueil", ar: "الرجوع إلى الصفحة الرئيسية" },
  "status.footerLink": { fr: "Sante du service", ar: "حالة الخدمة" },
};

interface LanguageContextValue {
  lang: Lang;
  dir: "ltr" | "rtl";
  toggleLang: () => void;
  t: (key: string) => string;
}

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("fr");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY) as Lang | null;
    if (stored === "fr" || stored === "ar") setLang(stored);
  }, []);

  useEffect(() => {
    const dir = lang === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
    window.localStorage.setItem(STORAGE_KEY, lang);
  }, [lang]);

  function toggleLang() {
    setLang((l) => (l === "fr" ? "ar" : "fr"));
  }

  function t(key: string): string {
    const entry = DICTIONARY[key];
    if (!entry) return key;
    return entry[lang] ?? entry.fr;
  }

  return (
    <LanguageContext.Provider
      value={{ lang, dir: lang === "ar" ? "rtl" : "ltr", toggleLang, t }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within LanguageProvider");
  return ctx;
}
