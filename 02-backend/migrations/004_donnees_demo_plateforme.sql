-- ═══════════════════════════════════════════════════════════════════
-- SOU9NA — Données de démonstration « plateforme » (APRÈS 003)
-- Idempotent : ON CONFLICT DO NOTHING (norme N7).
-- ═══════════════════════════════════════════════════════════════════

-- ── Utilisateurs (l'équipe de chaque entreprise) ──────────────────
insert into utilisateurs (company_id, nom, email, whatsapp, role, statut) values
('001528471000047', 'Karim Benali',  'contact@marocmetaux.ma', '+212661234567', 'admin',  'actif'),
('001528471000047', 'Leila Amrani',  'leila.amrani@marocmetaux.ma', '+212661987654', 'membre', 'invite'),
('002345678000012', 'Youssef Idrissi', 'info@atlasdigital.ma', '+212662987654', 'admin', 'actif'),
('003987654000021', 'Mohamed Rifai',  'bati.riff@gestion.ma', '+212663112233', 'admin', 'actif'),
('004555666000033', 'Salma Chaoui',   'dgs@transportchaouia.ma', '+212664334455', 'admin', 'actif'),
('005111222000044', 'Ahmed Ouali',    'coop@sudagro.ma', null, 'admin', 'actif')
on conflict (email) do nothing;

-- ── Abonnements (essai 14 jours + plans) ─────────────────────────
insert into abonnements (company_id, plan, statut, essai_fin, prix_mad, debute_le) values
('001528471000047', 'pro',      'essai',  '2026-12-01', 199, null),   -- essai démarré le 17/11
('002345678000012', 'pro',      'essai',  '2026-11-30', 199, null),   -- essai démarré le 16/11
('003987654000021', 'pro',      'essai',  '2026-11-29', 199, null),   -- essai démarré le 15/11
('004555666000033', 'business', 'essai',  '2026-11-24', 499, null),   -- essai démarré le 10/11
('005111222000044', 'decouverte', 'actif', null,         0,   '2026-09-01')  -- fin d'essai → Découverte gratuit
on conflict (company_id) do nothing;

-- ── Codes OTP (exemple : un actif, un utilisé) ───────────────────
insert into otp_codes (canal, destinataire, code, expire_le, utilise_le, cree_le) values
('email', 'contact@marocmetaux.ma', '482913', '2026-11-18 10:40:00+00', null, '2026-11-18 10:30:00+00'),
('whatsapp', '+212662987654', '719345', '2026-11-17 12:15:00+00', '2026-11-17 12:12:00+00', '2026-11-17 12:05:00+00')
on conflict do nothing;

-- ── Favoris (dossiers suivis) ────────────────────────────────────
insert into favoris (company_id, reference, statut_dossier, note) values
('001528471000047', '2026/DTR/0123', 'envoye',   'Dossier déposé le 28/11 — attente ouverture des plis'),
('001528471000047', '2026/DTR/0124', 'a_etudier', 'Chercher partenaire certifié ISO 9001'),
('002345678000012', '2026/DTR/0131', 'a_etudier', 'Budget interne validé'),
('003987654000021', '2026/DTR/0123', 'a_etudier', null)
on conflict (company_id, reference) do nothing;

-- ── Notifications (la cloche du dashboard) ───────────────────────
insert into notifications (company_id, type, titre, contenu, lue, cree_le) values
('001528471000047', 'digest', 'Votre digest du 17/11 est prêt', '3 opportunités — dont 1 GO (réf. 2026/DTR/0123, Match 96)', false, '2026-11-17 08:00:05+00'),
('001528471000047', 'hitl',   'Verdict À ÉTUDIER — 3 risques à vérifier', 'Réf. 2026/DTR/0124 — ISO 9001, sous-lots, partenaire certifié', false, '2026-11-17 07:06:00+00'),
('002345678000012', 'digest', 'Votre digest du 17/11 est prêt', '1 opportunité GO — réf. 2026/DTR/0131 (Match 100)', true,  '2026-11-17 08:00:05+00'),
('003987654000021', 'digest', 'Votre digest du 17/11 est prêt', '1 opportunité GO — réf. 2026/DTR/0123', false, '2026-11-17 08:00:05+00')
on conflict do nothing;

-- ── Admins (l'équipe Soukna — gouvernance collective, pas de chef) ─
insert into admins (nom, email, role, actif) values
('Hamza Mhalli',        'hamzamhalli95@gmail.com', 'equipe', true),
('Hamza Midouni',       'hamza.midouni@sou9na.ma', 'equipe', true),
('Hamza Ouchen',        'hamza.ouchen@sou9na.ma',  'admin',  true),  -- déploiement & sécurité : accès infra
('Ayoub Abdelmoughit',  'ayoub@sou9na.ma',         'equipe', true),
('Achraf Outlit',       'achraf.outlit@sou9na.ma', 'equipe', true)
on conflict (email) do nothing;
