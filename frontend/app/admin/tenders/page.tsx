"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, getAuth } from "../../lib";

type Tender = {
  reference: string;
  organisme?: string;
  objet?: string;
  secteur?: string;
  region?: string;
  statut?: string;
  offer_type?: string;
  date_remise?: string | null;
  source?: string;
  source_url?: string | null;
  montant_mad?: number | null;
  score?: number | null;
};

type Liste = {
  items: Tender[];
  total: number;
  limit: number;
  offset: number;
};

type Filtres = {
  q: string;
  secteur: string;
  region: string;
  statut: string;
  offer_type: string;
  date_from: string;
  date_to: string;
  min_score: string;
  max_score: string;
  company_id: string;
};

const VIDE: Filtres = {
  q: "",
  secteur: "",
  region: "",
  statut: "",
  offer_type: "",
  date_from: "",
  date_to: "",
  min_score: "",
  max_score: "",
  company_id: "EXPLEO-IT-001",
};

const TYPES = [
  { value: "", label: "Tous les types" },
  { value: "appel_offres", label: "Appel d'offres" },
  { value: "consultation", label: "Consultation" },
  { value: "bon_de_commande", label: "Bon de commande" },
];

export default function AdminTendersPage() {
  const [filtres, setFiltres] = useState<Filtres>(VIDE);
  const [liste, setListe] = useState<Liste>({ items: [], total: 0, limit: 50, offset: 0 });
  const [erreur, setErreur] = useState("");
  const [message, setMessage] = useState("");
  const [chargement, setChargement] = useState(false);
  const [creation, setCreation] = useState<Record<string, string>>({
    reference: "",
    organisme: "",
    objet: "",
    secteur: "informatique",
    region: "casa-settat",
    montant_mad: "",
    caution_mad: "",
    offer_type: "appel_offres",
    date_remise: "",
    source_url: "",
  });

  const query = useMemo(() => {
    const p = new URLSearchParams();
    Object.entries(filtres).forEach(([key, value]) => {
      if (value.trim()) p.set(key, value.trim());
    });
    p.set("limit", "50");
    p.set("offset", String(liste.offset));
    return p.toString();
  }, [filtres, liste.offset]);

  const charger = useCallback(async () => {
    setChargement(true);
    setErreur("");
    try {
      const resultat = await api<Liste>(`/tenders?${query}`);
      setListe((prev) => ({ ...prev, ...resultat }));
    } catch (err) {
      setErreur((err as Error).message);
    } finally {
      setChargement(false);
    }
  }, [query]);

  useEffect(() => {
    const auth = getAuth();
    if (!auth || auth.role !== "admin") {
      window.location.href = "/login";
      return;
    }
    void charger();
  }, [charger]);

  async function action(reference: string, route: string) {
    setErreur("");
    setMessage("");
    try {
      await api(`/admin/tenders/${encodeURIComponent(reference)}/${route}`, { method: "POST" });
      setMessage(`${route} OK — ${reference}`);
      await charger();
    } catch (err) {
      setErreur((err as Error).message);
    }
  }

  async function synchroniser() {
    setErreur("");
    try {
      const resultat = await api<Record<string, number>>("/admin/tenders/sync", { method: "POST" });
      setMessage(`Synchronisation : ${JSON.stringify(resultat)}`);
    } catch (err) {
      setErreur((err as Error).message);
    }
  }

  async function creer(event: FormEvent) {
    event.preventDefault();
    setErreur("");
    setMessage("");
    const corps: Record<string, unknown> = {
      ...creation,
      montant_mad: creation.montant_mad ? Number(creation.montant_mad) : null,
      caution_mad: creation.caution_mad ? Number(creation.caution_mad) : null,
      statut: "ouvert",
      source: "manuel",
    };
    try {
      const tender = await api<Tender>("/tenders", {
        method: "POST",
        body: JSON.stringify(corps),
      });
      setMessage(`Tender créé : ${tender.reference}`);
      await charger();
    } catch (err) {
      setErreur((err as Error).message);
    }
  }

  const totalPages = Math.max(1, Math.ceil(liste.total / liste.limit));
  const page = Math.floor(liste.offset / liste.limit) + 1;

  return (
    <main className="page container">
      <nav className="topnav" style={{ marginBottom: 16 }}>
        <Link href="/admin">← Administration</Link>
        <Link href="/dashboard">Tableau de bord</Link>
      </nav>

      <h1>Appels d&apos;offres — administration</h1>
      <p className="subtitle">
        Liste des tenders, filtres expiration/score/type et création manuelle. Aucune création ne
        déclenche de GO automatique : le verdict reste soumis aux preuves caution/budget.
      </p>

      {erreur && <div className="message message-err">{erreur}</div>}
      {message && <div className="message message-ok">{message}</div>}

      <section className="panel">
        <h2 style={{ marginTop: 0 }}>Filtres</h2>
        <div className="form-grid">
          <label className="field">Recherche
            <input value={filtres.q} onChange={(e) => setFiltres({ ...filtres, q: e.target.value })} placeholder="référence, objet, organisme" />
          </label>
          <label className="field">Secteur
            <input value={filtres.secteur} onChange={(e) => setFiltres({ ...filtres, secteur: e.target.value })} />
          </label>
          <label className="field">Région
            <input value={filtres.region} onChange={(e) => setFiltres({ ...filtres, region: e.target.value })} />
          </label>
          <label className="field">Statut
            <input value={filtres.statut} onChange={(e) => setFiltres({ ...filtres, statut: e.target.value })} placeholder="ouvert / clos" />
          </label>
          <label className="field">Type d&apos;offre
            <select value={filtres.offer_type} onChange={(e) => setFiltres({ ...filtres, offer_type: e.target.value })}>
              {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </label>
          <label className="field">Échéance du
            <input type="date" value={filtres.date_from} onChange={(e) => setFiltres({ ...filtres, date_from: e.target.value })} />
          </label>
          <label className="field">Échéance au
            <input type="date" value={filtres.date_to} onChange={(e) => setFiltres({ ...filtres, date_to: e.target.value })} />
          </label>
          <label className="field">Score min
            <input type="number" min={0} max={100} value={filtres.min_score} onChange={(e) => setFiltres({ ...filtres, min_score: e.target.value })} />
          </label>
          <label className="field">Score max
            <input type="number" min={0} max={100} value={filtres.max_score} onChange={(e) => setFiltres({ ...filtres, max_score: e.target.value })} />
          </label>
          <label className="field">Entreprise (scores)
            <input value={filtres.company_id} onChange={(e) => setFiltres({ ...filtres, company_id: e.target.value })} />
          </label>
        </div>
        <div className="switch-row">
          <button className="btn btn-primary" type="button" onClick={() => { setListe((p) => ({ ...p, offset: 0 })); void charger(); }} disabled={chargement}>
            {chargement ? "Chargement…" : "Appliquer"}
          </button>
          <button className="btn" type="button" onClick={() => setFiltres(VIDE)}>Réinitialiser</button>
          <button className="btn" type="button" onClick={() => void synchroniser()}>Synchroniser vers opportunities</button>
        </div>
      </section>

      <section className="panel" style={{ overflowX: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ marginTop: 0 }}>{liste.total} tender(s)</h2>
          <span className="hint">Page {page}/{totalPages}</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Référence</th><th>Organisme</th><th>Objet</th><th>Type</th>
              <th>Échéance</th><th>Statut</th><th>Source</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {liste.items.map((t) => (
              <tr key={t.reference}>
                <td className="score">{t.reference}</td>
                <td>{t.organisme || "—"}</td>
                <td>{t.objet || "—"}</td>
                <td>{t.offer_type || "—"}</td>
                <td>{t.date_remise || "—"}</td>
                <td>{t.statut || "—"}</td>
                <td>{t.source || "—"}</td>
                <td>
                  <button className="btn" style={{ padding: "5px 10px" }} onClick={() => void action(t.reference, "cps-ready")}>
                    CPS prêt
                  </button>
                </td>
              </tr>
            ))}
            {liste.items.length === 0 && <tr><td colSpan={8} className="hint">Aucun tender pour ces filtres.</td></tr>}
          </tbody>
        </table>
        <div className="switch-row">
          <button className="btn" disabled={liste.offset === 0} onClick={() => setListe((p) => ({ ...p, offset: Math.max(0, p.offset - p.limit) }))}>← Précédent</button>
          <button className="btn" disabled={page >= totalPages} onClick={() => setListe((p) => ({ ...p, offset: p.offset + p.limit }))}>Suivant →</button>
        </div>
      </section>

      <section className="panel">
        <h2 style={{ marginTop: 0 }}>Créer un tender manuellement</h2>
        <form onSubmit={(e) => void creer(e)}>
          <div className="form-grid">
            <label className="field">Référence *
              <input required value={creation.reference} onChange={(e) => setCreation({ ...creation, reference: e.target.value })} />
            </label>
            <label className="field">Organisme
              <input value={creation.organisme} onChange={(e) => setCreation({ ...creation, organisme: e.target.value })} />
            </label>
            <label className="field">Objet
              <input value={creation.objet} onChange={(e) => setCreation({ ...creation, objet: e.target.value })} />
            </label>
            <label className="field">Type
              <select value={creation.offer_type} onChange={(e) => setCreation({ ...creation, offer_type: e.target.value })}>
                {TYPES.filter((t) => t.value).map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
            <label className="field">Secteur
              <input value={creation.secteur} onChange={(e) => setCreation({ ...creation, secteur: e.target.value })} />
            </label>
            <label className="field">Région
              <input value={creation.region} onChange={(e) => setCreation({ ...creation, region: e.target.value })} />
            </label>
            <label className="field">Montant MAD
              <input type="number" min={0} value={creation.montant_mad} onChange={(e) => setCreation({ ...creation, montant_mad: e.target.value })} />
            </label>
            <label className="field">Caution MAD
              <input type="number" min={0} value={creation.caution_mad} onChange={(e) => setCreation({ ...creation, caution_mad: e.target.value })} />
            </label>
            <label className="field">Date de remise
              <input type="date" value={creation.date_remise} onChange={(e) => setCreation({ ...creation, date_remise: e.target.value })} />
            </label>
            <label className="field">URL source
              <input value={creation.source_url} onChange={(e) => setCreation({ ...creation, source_url: e.target.value })} />
            </label>
          </div>
          <button className="btn btn-primary" type="submit">Créer / mettre à jour</button>
        </form>
      </section>
    </main>
  );
}
