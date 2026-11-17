-- ═══════════════════════════════════════════════════════════════════
-- SOU9NA — Données de démonstration (à exécuter APRÈS 001_schema_v3.sql)
-- Idempotent : ON CONFLICT DO NOTHING (norme N7) — réexécution = 0 doublon.
-- Match /100 — pondérations validées : secteur 35 · région 20 · capacité 20 ·
-- qualifications 15 · historique 10  (algo_version "1.0.0")
-- ═══════════════════════════════════════════════════════════════════

-- ── Entreprises (profils de démonstration) ────────────────────────
insert into entreprises (company_id, nom, email, whatsapp, secteur, region, capacite_mad, qualifications, historique, canaux_optin, essai_debut, statut) values
('001528471000047', 'Maroc Métaux SARL', 'contact@marocmetaux.ma', '+212661234567',
 'construction', 'casa-settat', 3000000, array['catégorie C'],
 '[{"annee": 2025, "resultat": "gagne"}, {"annee": 2025, "resultat": "perdu", "motif": "prix"}]',
 '{"whatsapp": true, "email": true}', '2026-11-17', 'essai'),
('002345678000012', 'Atlas Digital SARL AU', 'info@atlasdigital.ma', '+212662987654',
 'it', 'casa-settat', 8000000, array['ISO 27001', 'MSA'],
 '[{"annee": 2025, "resultat": "gagne"}, {"annee": 2024, "resultat": "gagne"}]',
 '{"whatsapp": true, "email": false}', '2026-11-16', 'essai'),
('003987654000021', 'Bati Riff SARL', 'bati.riff@gestion.ma', '+212663112233',
 'construction', 'tanger-tetouan-alhoceima', 1200000, array['catégorie C'],
 '[{"annee": 2025, "resultat": "gagne"}]',
 '{"whatsapp": true, "email": true}', '2026-11-15', 'essai'),
('004555666000033', 'Transport Chaouia SA', 'dgs@transportchaouia.ma', '+212664334455',
 'transport', 'casa-settat', 2000000, array['licence transport marchandises'],
 '[]', '{"whatsapp": true, "email": true}', '2026-11-10', 'essai'),
('005111222000044', 'Sud Agro Coop', 'coop@sudagro.ma', null,
 'agriculture', 'souss-massa', 500000, array[],
 '[]', '{"whatsapp": true, "email": true}', null, 'actif')
on conflict (company_id) do nothing;

-- ── Tenders (avis collectés par INSPECTEUR) ───────────────────────
insert into tenders (reference, organisme, objet, secteur, region, montant_mad, caution_mad, lots, qualifications_exigees, delai_jours, date_publication, date_remise, date_collecte, statut, source, source_url) values
('2026/DTR/0123', 'Commune de Sidi X', 'Travaux de réhabilitation du siège communal',
 'construction', 'casa-settat', 1500000, 45000, array['gros œuvre'], array['catégorie C'],
 120, '2026-11-17', '2026-12-01', '2026-11-17', 'ouvert', 'backfill', 'https://marchespublics.gov.ma/…/0123'),
('2026/DTR/0124', 'CHU Casablanca', 'Fourniture et pose de menuiseries aluminées — exigence ISO 9001',
 'construction', 'casa-settat', 2800000, 84000, array['menuiserie'], array['catégorie C', 'ISO 9001'],
 90, '2026-11-17', '2026-12-05', '2026-11-17', 'ouvert', 'backfill', 'https://marchespublics.gov.ma/…/0124'),
('2026/DTR/0125', 'Direction Régionale de l''Équipement', 'Construction d''un complexe administratif',
 'construction', 'casa-settat', 50000000, 1500000, array['gros œuvre', 'VRD'], array['catégorie F'],
 365, '2026-11-17', '2027-01-15', '2026-11-17', 'ouvert', 'backfill', 'https://marchespublics.gov.ma/…/0125'),
('2026/DTR/0126', 'Université Hassan II', 'Entretien des espaces verts (avis clos)',
 'construction', 'casa-settat', 400000, 12000, array[], array['catégorie C'],
 60, '2026-10-20', '2026-11-10', '2026-11-17', 'clos', 'backfill', 'https://marchespublics.gov.ma/…/0126'),
('2026/DTR/0130', 'Agence Urbaine', 'Développement d''un portail de dépôt en ligne',
 'it', 'casa-settat', 600000, 18000, array['développement'], array['MSA'],
 75, '2026-11-17', '2026-12-10', '2026-11-17', 'ouvert', 'backfill', 'https://marchespublics.gov.ma/…/0130'),
('2026/DTR/0131', 'Département de la Formation Professionnelle', 'E-learning platform pour centres PF',
 'it', 'casa-settat', 4000000, 120000, array['développement', 'infrastructure'], array['ISO 27001'],
 150, '2026-11-17', '2026-12-15', '2026-11-17', 'ouvert', 'backfill', 'https://marchespublics.gov.ma/…/0131'),
('2026/DTR/0132', 'Direction Provinciale du Transport', 'Affrètement de bus scolaires',
 'transport', 'casa-settat', 1800000, 54000, array[], array['licence transport marchandises'],
 180, '2026-11-17', '2026-12-20', '2026-11-17', 'ouvert', 'backfill', 'https://marchespublics.gov.ma/…/0132'),
('2026/DTR/0133', 'Commune de Salé', 'Réhabilitation d''un marché couvert',
 'construction', 'rabat-sale-kenitra', 800000, 24000, array['gros œuvre'], array['catégorie C'],
 90, '2026-11-17', '2026-12-08', '2026-11-17', 'ouvert', 'backfill', 'https://marchespublics.gov.ma/…/0133'),
('2026/DTR/0134', 'Préfecture de Casablanca', 'Rénovation du marché central (avis d''attribution)',
 'construction', 'casa-settat', 2100000, null, array['gros œuvre'], array['catégorie C'],
 120, '2026-09-01', '2026-09-25', '2026-11-17', 'attribution', 'backfill', 'https://marchespublics.gov.ma/…/0134'),
('2026/DTR/0135', 'Office Régional de l''Eau', 'Modernisation du système de facturation (collecte du jour)',
 'it', 'casa-settat', 1200000, 36000, array['développement'], array['MSA'],
 100, '2026-11-18', '2026-12-18', '2026-11-18', 'ouvert', 'portail', 'https://marchespublics.gov.ma/…/0135')
on conflict (reference) do nothing;

-- ── Scores (COMPAGNON — déterministe) ─────────────────────────────
-- ice-001 (Maroc Métaux : construction, casa-settat, cap. 3 M, cat. C, hist. 1 gagné + 1 perdu → /10 = 6)
insert into scores (company_id, reference, match_total, composantes, points_perdus, algo_version, calcule_le) values
('001528471000047', '2026/DTR/0123', 96,
 '{"secteur": 35, "region": 20, "capacite": 20, "qualifications": 15, "historique": 6}',
 '["historique : 1 marché perdu (−4)"]', '1.0.0', '2026-11-17 06:20:00+00'),
('001528471000047', '2026/DTR/0124', 81,
 '{"secteur": 35, "region": 20, "capacite": 20, "qualifications": 0, "historique": 6}',
 '["qualifications : ISO 9001 non détenue (−15)", "historique : 1 marché perdu (−4)"]', '1.0.0', '2026-11-17 06:20:00+00'),
('001528471000047', '2026/DTR/0125', 76,
 '{"secteur": 35, "region": 20, "capacite": 0, "qualifications": 15, "historique": 6}',
 '["capacité : montant 50 M > capacité 3 M (−20)", "historique : 1 marché perdu (−4)"]', '1.0.0', '2026-11-17 06:20:00+00'),
('001528471000047', '2026/DTR/0130', 26,
 '{"secteur": 0, "region": 20, "capacite": 20, "qualifications": 0, "historique": 6}',
 '["secteur : IT ≠ construction (−35)", "qualifications : MSA non détenue (−15)", "historique : 1 marché perdu (−4)"]', '1.0.0', '2026-11-17 06:20:00+00'),
('001528471000047', '2026/DTR/0133', 76,
 '{"secteur": 35, "region": 0, "capacite": 20, "qualifications": 15, "historique": 6}',
 '["région : rabat-sale-kenitra ≠ casa-settat (−20)", "historique : 1 marché perdu (−4)"]', '1.0.0', '2026-11-17 06:20:00+00'),
-- atlas digital (it, casa-settat, cap. 8 M, ISO 27001, hist. 2 gagnés → 10)
('002345678000012', '2026/DTR/0131', 100,
 '{"secteur": 35, "region": 20, "capacite": 20, "qualifications": 15, "historique": 10}', '[]', '1.0.0', '2026-11-17 06:20:00+00'),
-- bati riff (construction, tanger-tetouan, cap. 1,2 M, cat. C, hist. 1 gagné → 10)
('003987654000021', '2026/DTR/0123', 80,
 '{"secteur": 35, "region": 0, "capacite": 20, "qualifications": 15, "historique": 10}',
 '["région : casa-settat ≠ tanger-tetouan-alhoceima (−20)"]', '1.0.0', '2026-11-17 06:20:00+00')
on conflict (company_id, reference, algo_version) do nothing;
-- Note : score 26 (sous le seuil du JUGE) → jamais évalué par le JUGE.

-- ── Verdicts (JUGE — au-dessus du seuil uniquement) ───────────────
insert into verdicts (company_id, reference, verdict, controles, justifications, risques_a_verifier, rendu_le) values
('001528471000047', '2026/DTR/0123', 'GO',
 '{"caution_vs_capacite": "ok", "ice_attestations": "ok", "qualifications": "ok", "delai_atteignable": "ok"}',
 '[{"constat": "caution 45 000 MAD ≤ capacité 3 000 000 MAD", "reference": "décret 2-22-431, art. 12"},
   {"constat": "catégorie C détenue, exigée", "reference": "cctp du dossier officiel"}]',
 '[]', '2026-11-17 07:05:00+00'),
('001528471000047', '2026/DTR/0124', 'A_ETUDIER',
 '{"caution_vs_capacite": "ok", "ice_attestations": "ok", "qualifications": "risque", "delai_atteignable": "ok"}',
 '[{"constat": "ISO 9001 exigée mais non détenue au dossier", "reference": "avis officiel, art. qualifications"}]',
 '["obtenir l''attestation ISO 9001 avant le 05/12", "confirmer la faisabilité avec un partenaire certifié", "vérifier le détail des sous-lots menuiserie"]',
 '2026-11-17 07:05:00+00'),
('001528471000047', '2026/DTR/0125', 'NO_GO',
 '{"caution_vs_capacite": "ko", "ice_attestations": "ok", "qualifications": "risque", "delai_atteignable": "ok"}',
 '[{"constat": "montant 50 000 000 MAD > capacité 3 000 000 MAD — éliminatoire", "reference": "décret 2-22-431, art. capacité"}]',
 '[]', '2026-11-17 07:05:00+00'),
('002345678000012', '2026/DTR/0131', 'GO',
 '{"caution_vs_capacite": "ok", "ice_attestations": "ok", "qualifications": "ok", "delai_atteignable": "ok"}',
 '[{"constat": "ISO 27001 détenue, exigée", "reference": "avis officiel, art. qualifications"}]',
 '[]', '2026-11-17 07:10:00+00'),
('003987654000021', '2026/DTR/0123', 'GO',
 '{"caution_vs_capacite": "ok", "ice_attestations": "ok", "qualifications": "ok", "delai_atteignable": "ok"}',
 '[{"constat": "caution 45 000 MAD ≤ capacité 1 200 000 MAD", "reference": "décret 2-22-431, art. 12"}]',
 '[]', '2026-11-17 07:10:00+00')
on conflict (company_id, reference) do nothing;

-- ── Digest (composé par COMPAGNON 7h30, envoyé par CONCIERGE 8h00) ─
insert into digests (company_id, jour, contenu_fr, contenu_ar, bandeau, statut_envoi, envoye_le) values
('001528471000047', '2026-11-17',
 '{"titre": "Vos opportunités du 17 novembre", "top_matchs": [
    {"reference": "2026/DTR/0123", "objet": "Réhabilitation du siège communal", "match": 96, "verdict": "GO", "remise": "2026-12-01"},
    {"reference": "2026/DTR/0124", "objet": "Menuiseries aluminées CHU", "match": 81, "verdict": "A_ETUDIER", "remise": "2026-12-05"},
    {"reference": "2026/DTR/0125", "objet": "Complexe administratif", "match": 76, "verdict": "NO_GO"}]}',
 '{"titre": "فرصكم ديال 17 نونبر", "top_matchs": [
    {"reference": "2026/DTR/0123", "match": 96, "verdict": "GO", "remise": "01/12/2026"},
    {"reference": "2026/DTR/0124", "match": 81, "verdict": "A_ETUDIER", "remise": "05/12/2026"},
    {"reference": "2026/DTR/0125", "match": 76, "verdict": "NO_GO"}]}',
 'Essai gratuit — jour 1 sur 14', 'envoye', '2026-11-17 08:00:00+00')
on conflict (company_id, jour) do nothing;

-- ── Messages (CONCIERGE — unique émetteur) ────────────────────────
insert into messages (company_id, canal, type, direction, texte, langue, intention, citation, statut_envoi, request_id, cree_le) values
('001528471000047', 'whatsapp', 'conversation', 'entrant', 'c''est quoi le quota de 30% pour les TPME ?', 'fr', 'faq', null, null, 'req-001', '2026-11-17 09:12:00+00'),
('001528471000047', 'whatsapp', 'conversation', 'sortant', 'Les TPME bénéficient d''un quota de 30 % dans les marchés publics…', 'fr', 'faq',
 '{"document": "décret 2-22-431", "article": "art. 12"}', 'envoye', 'req-001', '2026-11-17 09:12:30+00'),
('001528471000047', 'whatsapp', 'gabarit', 'sortant', 'Digest quotidien — 3 opportunités', 'fr', null, null, 'envoye', 'run-2026-11-17', '2026-11-17 08:00:00+00')
on conflict do nothing;

-- ── Feedback (boucle d'amélioration) ──────────────────────────────
insert into feedback (company_id, reference, resultat, motif, date) values
('001528471000047', '2026/DTR/0123', 'gagne', 'prix', '2026-11-18')
on conflict (company_id, reference) do nothing;

-- ── Run logs (backfill de lancement + cron du jour) ───────────────
insert into run_logs (run_id, type, statut, debute_le, cloture_le, avis_nouveaux, rejetes, doublons, tokens, cout_mad) values
('run-2026-11-17-backfill', 'backfill', 'cloture', '2026-11-17 04:30:00+00', '2026-11-17 06:00:00+00', 438, 11, 0, 0, 0),
('run-2026-11-17', 'cron', 'cloture', '2026-11-17 06:00:00+00', '2026-11-17 07:55:00+00', 132, 3, 0, 14500, 1.10),
('run-2026-11-18', 'cron', 'ouvert', '2026-11-18 06:00:00+00', null, null, null, null, null, null)
on conflict (run_id) do nothing;

-- ── Prospects (file d'attente) + invitations (liens 7 jours) ──────
insert into prospects (id, nom, email, whatsapp, secteur, taille, consentement_loi_09_08, honeypot, statut, cree_le) values
('11111111-1111-1111-1111-111111111101', 'Medina Bâtiment SARL', 'contact@medinabatiment.ma', '+212665112233', 'construction', '1–10', true, '', 'approuve', '2026-11-16 10:00:00+00'),
('11111111-1111-1111-1111-111111111102', 'Cabinet Tazi & Fils', 'cabinet.tazi@consult.ma', null, 'services', '1–10', true, '', 'en_attente_approbation', '2026-11-17 14:30:00+00'),
('11111111-1111-1111-1111-111111111103', 'Nour Transport', 'nour.transport@mail.ma', '+212666778899', 'transport', '11–50', true, '', 'en_attente_approbation', '2026-11-18 09:15:00+00')
on conflict (email) do nothing;

insert into invitations (token, prospect_id, company_id, expire_le, utilise_le, cree_le) values
('inv_a7f3c9e2d1b4', '11111111-1111-1111-1111-111111111101', '001528471000047',
 '2026-11-23 10:00:00+00', '2026-11-17 10:05:00+00', '2026-11-16 11:00:00+00'),
('inv_c2d8e4f1a9b6', '11111111-1111-1111-1111-111111111102', null,
 '2026-11-24 15:00:00+00', null, '2026-11-17 15:00:00+00')
on conflict (token) do nothing;
-- inv_a7f3c9e2d1b4 : utilisée → activation de Maroc Métaux (essai 14 j commencé)
-- inv_c2d8e4f1a9b6 : en attente — le client n'a pas encore ouvert le lien (expire dans 7 j)
