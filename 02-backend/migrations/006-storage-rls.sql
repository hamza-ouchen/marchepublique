-- =====================================================================
-- Soukna — migration 006 : bucket Supabase Storage 'cps-originaux' + RLS.
--
-- À exécuter APRÈS avoir créé le bucket 'cps-originaux' (privé, non public)
-- dans le dashboard Supabase (Storage > New bucket) ou via l'API Storage.
--
-- Politique : service_role (backend) lit/écrit/supprime ; anon et
-- authenticated n'ont AUCUN accès (texte brut protégé, lecture via backend).
-- =====================================================================

-- Bucket (idempotent via INSERT ... ON CONFLICT ; nécessite le rôle service_role)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('cps-originaux', 'cps-originaux', false, 26214400, ARRAY['application/pdf'])
ON CONFLICT (id) DO NOTHING;

-- Nettoyage des policies existantes (idempotent)
DROP POLICY IF EXISTS "cps_originaux_service_role_all" ON storage.objects;
DROP POLICY IF EXISTS "cps_originaux_no_anon" ON storage.objects;

-- Le service_role a tous les droits sur le bucket cps-originaux.
CREATE POLICY "cps_originaux_service_role_all"
ON storage.objects
FOR ALL
TO service_role
USING (bucket_id = 'cps-originaux')
WITH CHECK (bucket_id = 'cps-originaux');

-- Aucun accès pour anon / authenticated (pas de policy = refus par défaut).