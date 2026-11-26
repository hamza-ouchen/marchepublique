"use client";

import { FormEvent, useState } from "react";
import { api } from "./lib";

type Reply = {
  texte: string;
  citation: unknown;
  hitl: boolean;
  donnees: { suggestions?: string[] };
};

type Msg = { role: "user" | "bot"; text: string };

const GREETING = {
  fr: "Bonjour 👋 Je suis le concierge Sou9na. Posez-moi une question sur vos opportunités, le Match ou le verdict.",
  ar: "مرحباً 👋 أنا مساعد سوقنا. اسألني عن فرصك أو درجة التوافق أو القرار.",
};

export default function ChatWidget({
  lang = "fr",
  companyId = "EXPLEO-IT-001",
}: {
  lang?: "fr" | "ar";
  companyId?: string;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [messages, setMessages] = useState<Msg[]>([
    { role: "bot", text: GREETING[lang] },
  ]);

  async function send(text: string) {
    const value = text.trim();
    if (!value || busy) return;
    setMessages((prev) => [...prev, { role: "user", text: value }]);
    setInput("");
    setBusy(true);
    try {
      const query = new URLSearchParams({
        message: value,
        company_id: companyId,
        ...(lang === "ar" ? { lang } : {}),
      });
      const reply = await api<Reply>(`/chat?${query.toString()}`);
      setMessages((prev) => [...prev, { role: "bot", text: reply.texte }]);
      setSuggestions(reply.donnees?.suggestions || []);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: (err as Error).message || "Service momentanément indisponible." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  return (
    <>
      {open && (
        <div className="chat-panel" role="dialog" aria-label="Assistant Sou9na">
          <div className="chat-head">
            <strong>{lang === "ar" ? "مساعد سوقنا" : "Concierge Sou9na"}</strong>
            <button type="button" onClick={() => setOpen(false)} aria-label="Fermer">×</button>
          </div>
          <div className="chat-log">
            {messages.map((m, i) => (
              <div key={i} className={`chat-msg ${m.role}`}>{m.text}</div>
            ))}
            {busy && <div className="chat-msg bot">…</div>}
          </div>
          {suggestions.length > 0 && (
            <div className="chat-suggestions">
              {suggestions.map((s) => (
                <button key={s} type="button" onClick={() => void send(s)}>{s}</button>
              ))}
            </div>
          )}
          <form className="chat-form" onSubmit={onSubmit}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={lang === "ar" ? "اكتب سؤالك…" : "Écrivez votre question…"}
              aria-label="Message"
            />
            <button type="submit" disabled={busy}>➤</button>
          </form>
        </div>
      )}
      <button
        type="button"
        className="chat-fab"
        onClick={() => setOpen((v) => !v)}
        aria-label={lang === "ar" ? "فتح المساعد" : "Ouvrir l'assistant"}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 5h16v11H9l-5 4V5Z" fill="currentColor" />
          <circle cx="9" cy="11" r="1" fill="#12324A" />
          <circle cx="13" cy="11" r="1" fill="#12324A" />
          <circle cx="17" cy="11" r="1" fill="#12324A" />
        </svg>
      </button>
    </>
  );
}
