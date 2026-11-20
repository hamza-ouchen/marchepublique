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
