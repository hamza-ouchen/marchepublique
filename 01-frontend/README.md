# Sou9na — Dashboard (prototype)

Dashboard frontend (Next.js 14 / React / TypeScript / Tailwind) pour Sou9na —
assistant IA pour TPME marocaines sur les marches publics.

Livrable "01-frontend" selon README SOU9NA-REF-001 §3.4 (Ayoub Abdelmoughit).

## ⚠️ Statut : prototype frontend, pas de backend reel

- L'authentification (login/signup) utilise **localStorage** uniquement —
  aucune API reelle, aucune base de donnees. C'est fait expres pour avancer
  sur l'interface pendant que le backend (Hamza Midouni, FastAPI) n'est pas
  encore pret.
- Les conversations, statistiques et la liste clients sont des **donnees de
  demonstration** (`lib/mock-data.ts`) — pas de vraies conversations WhatsApp.
- A brancher plus tard : vraie API d'authentification, vrai flux de
  conversations depuis le flow CONCIERGE (plateforme Agentic AI), vraie base
  clients.

## Installation

```bash
npm install
npm run dev
```

Puis ouvrir http://localhost:3000 — affiche la page d'accueil (landing),
avec boutons "Se connecter" / "Creer un compte".

## Comptes de demonstration

- **Admin** : `admin@sou9na.ma` / `admin123`
- **Client (TPME)** : creer un compte via `/signup` (role `user` automatique)

## Structure

```
app/
  login/            page de connexion
  signup/           creation de compte TPME
  admin/            espace admin (role "admin")
    conversations/  gestion des conversations + confirmation HITL
    clients/        liste des entreprises TPME
  user/             espace client TPME (role "user")
    historique/     historique des conversations
    profil/         profil editable
components/         composants partages (Sidebar, StatCard, Badge, ...)
lib/
  auth-context.tsx  authentification mock (localStorage)
  mock-data.ts      donnees de demonstration
  types.ts          types partages
```

## Prochaines etapes

1. Brancher une vraie API d'authentification (JWT/session) a la place de
   `lib/auth-context.tsx`.
2. Remplacer `lib/mock-data.ts` par des appels reels vers le backend qui
   lit les conversations du flow "Concierge-Conversation" (plateforme
   Agentic AI).
3. Reproduire le flux HITL reel (confirmation d'un point HITL ici doit
   notifier/mettre a jour le flow CONCIERGE, pas seulement l'etat local).
