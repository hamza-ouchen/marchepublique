"use client";

import { useEffect, useRef, useState } from "react";
import { api, COMPANY_ID } from "@/lib/api";
import type { ChatResponse, Lang } from "@/lib/types";

type Message = {
  role: "user" | "assistant";
  texte: string;
  citation?: ChatResponse["citation"];
  hitl?: boolean;
};

const SUGGESTIONS: Record<Lang, string[]> = {
  fr: [
    "Quels sont mes risques prioritaires ?",
    "Montre mes meilleures opportunités",
    "Où en est la preuve documentaire ?",
    "Fais-moi la synthèse du jour",
  ],
  ar: [
    "ما أبرز المخاطر؟",
    "أرني أفضل الفرص",
    "ما وضع الوثائق؟",
    "لخص لي اليوم",
  ],
};

const LABELS: Record<Lang, Record<string, string>> = {
  fr: {
    title: "Concierge Sou9na",
    subtitle: "Réponses traçables, sans hallucination",
    placeholder: "Posez votre question…",
    send: "Envoyer",
    thinking: "Analyse en cours…",
    hitl: "Décision humaine requise",
    source: "Source",
    error: "Le concierge est momentanément indisponible.",
    open: "Ouvrir le concierge",
    close: "Fermer le concierge",
    intro:
      "Bonjour. Je peux vous expliquer les risques d'un dossier, le classement des offres, la synthèse du jour ou l'état des preuves documentaires.",
  },
  ar: {
    title: "مساعد سوكنة",
    subtitle: "إجابات موثقة وبدون تخمين",
    placeholder: "اطرح سؤالك…",
    send: "إرسال",
    thinking: "جارٍ التحليل…",
    hitl: "يستدعي قراراً بشرياً",
    source: "المصدر",
    error: "المساعد غير متاح حالياً.",
    open: "فتح المساعد",
    close: "إغلاق المساعد",
    intro:
      "مرحباً. يمكنني شرح مخاطر ملف، ترتيب الفرص، ملخص اليوم أو حالة الوثائق.",
  },
};

export default function ChatPanel({
  lang = "fr",
  companyId = COMPANY_ID,
}: {
  lang?: Lang;
  companyId?: string;
}) {
  const t = LABELS[lang];
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", texte: t.intro },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const finRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function envoyer(texte: string) {
    const question = texte.trim();
    if (!question || busy) return;
    setMessages((prev) => [...prev, { role: "user", texte: question }]);
    setInput("");
    setBusy(true);
    try {
      const reponse = await api.chat(question, companyId);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          texte: reponse.texte,
          citation: reponse.citation,
          hitl: reponse.hitl,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", texte: t.error },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed bottom-5 right-5 z-[70] flex flex-col items-end gap-3">
      {open && (
        <section
          dir={lang === "ar" ? "rtl" : "ltr"}
          className="flex h-[min(70vh,620px)] w-[min(92vw,420px)] flex-col overflow-hidden rounded-lg border border-line bg-white shadow-2xl"
          aria-label={t.title}
        >
          <header className="flex items-center gap-3 border-b border-line bg-ink px-4 py-3 text-white">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-greenbrand text-sm font-bold">
              S
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-bold leading-none">{t.title}</div>
              <div className="mt-1 text-[10px] text-white/60">{t.subtitle}</div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded border border-white/30 px-2 py-1 text-xs hover:bg-white/10"
              aria-label={t.close}
            >
              ✕
            </button>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto bg-paper px-3 py-4">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[88%] whitespace-pre-line rounded-lg px-3 py-2 text-xs leading-relaxed shadow-sm ${
                    m.role === "user"
                      ? "bg-greenbrand text-white"
                      : "border border-line bg-white text-ink"
                  }`}
                >
                  {m.texte}
                  {m.hitl && (
                    <div className="mt-2 inline-block rounded bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800">
                      ⚠ {t.hitl}
                    </div>
                  )}
                  {m.citation?.constat && (
                    <div className="mt-2 border-t border-line pt-2 text-[10px] text-muted">
                      <strong>{t.source} :</strong> {m.citation.constat}
                      {m.citation.article ? ` — ${m.citation.article}` : ""}
                      {m.citation.pages ? ` (${m.citation.pages})` : ""}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="text-[11px] italic text-muted">{t.thinking}</div>
            )}
            <div ref={finRef} />
          </div>

          <div className="border-t border-line bg-white px-3 py-3">
            <div className="mb-2 flex flex-wrap gap-1">
              {SUGGESTIONS[lang].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => envoyer(s)}
                  disabled={busy}
                  className="rounded-full border border-line px-2 py-1 text-[10px] text-muted hover:border-greenbrand hover:text-greenbrand disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                envoyer(input);
              }}
              className="flex gap-2"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={t.placeholder}
                className="min-w-0 flex-1 rounded border border-line px-3 py-2 text-xs outline-none focus:border-greenbrand"
                aria-label={t.placeholder}
              />
              <button
                type="submit"
                disabled={busy || !input.trim()}
                className="rounded bg-greenbrand px-3 py-2 text-xs font-bold text-white hover:bg-[#18553f] disabled:opacity-50"
              >
                {t.send}
              </button>
            </form>
          </div>
        </section>
      )}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full bg-greenbrand px-4 py-3 text-xs font-bold text-white shadow-xl transition hover:bg-[#18553f]"
        aria-label={open ? t.close : t.open}
      >
        <span className="text-base">✦</span>
        {open ? t.close : t.title}
      </button>
    </div>
  );
}
