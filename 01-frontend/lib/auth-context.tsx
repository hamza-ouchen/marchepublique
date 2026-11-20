"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { AppUser, Role } from "./types";

// ---------------------------------------------------------------------------
// AUTH PROTOTYPE — localStorage uniquement, aucun vrai backend pour l'instant.
// A remplacer par de vrais appels API (JWT / session) des que le backend
// (Hamza Midouni, FastAPI) sera disponible. Mots de passe stockes en clair
// ici par simplicite de prototype : ne jamais faire ca en production.
// ---------------------------------------------------------------------------

const USERS_KEY = "sou9na_users";
const SESSION_KEY = "sou9na_session";

const SEED_ADMIN: AppUser = {
  id: "admin-seed",
  nom: "Administrateur Sou9na",
  email: "admin@sou9na.ma",
  password: "admin123",
  role: "admin",
  dateInscription: "2026-10-01",
};

function loadUsers(): AppUser[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(USERS_KEY);
  if (!raw) {
    window.localStorage.setItem(USERS_KEY, JSON.stringify([SEED_ADMIN]));
    return [SEED_ADMIN];
  }
  try {
    const parsed = JSON.parse(raw) as AppUser[];
    if (!parsed.find((u) => u.email === SEED_ADMIN.email)) {
      parsed.push(SEED_ADMIN);
    }
    return parsed;
  } catch {
    return [SEED_ADMIN];
  }
}

function saveUsers(users: AppUser[]) {
  window.localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

interface AuthContextValue {
  user: AppUser | null;
  loading: boolean;
  login: (email: string, password: string) => { ok: boolean; error?: string };
  signup: (data: {
    nom: string;
    email: string;
    password: string;
    entreprise: string;
    ice?: string;
    telephone?: string;
    secteurActivite?: string;
    region?: string;
    qualifications?: string;
  }) => { ok: boolean; error?: string };
  updateProfile: (
    patch: Partial<
      Pick<
        AppUser,
        "nom" | "entreprise" | "ice" | "telephone" | "secteurActivite" | "region" | "qualifications"
      >
    >
  ) => { ok: boolean; error?: string };
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AppUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (raw) {
      try {
        setUser(JSON.parse(raw));
      } catch {
        // ignore
      }
    }
    setLoading(false);
  }, []);

  function login(email: string, password: string) {
    const users = loadUsers();
    const found = users.find(
      (u) => u.email.toLowerCase() === email.toLowerCase() && u.password === password
    );
    if (!found) {
      return { ok: false, error: "Email ou mot de passe incorrect." };
    }
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(found));
    setUser(found);
    return { ok: true };
  }

  function signup(data: {
    nom: string;
    email: string;
    password: string;
    entreprise: string;
    ice?: string;
    telephone?: string;
    secteurActivite?: string;
    region?: string;
    qualifications?: string;
  }) {
    const users = loadUsers();
    if (users.find((u) => u.email.toLowerCase() === data.email.toLowerCase())) {
      return { ok: false, error: "Un compte existe deja avec cet email." };
    }
    const newUser: AppUser = {
      id: `u-${Date.now()}`,
      nom: data.nom,
      email: data.email,
      password: data.password,
      role: "user",
      entreprise: data.entreprise,
      ice: data.ice,
      telephone: data.telephone,
      secteurActivite: data.secteurActivite,
      region: data.region,
      qualifications: data.qualifications,
      dateInscription: new Date().toISOString().slice(0, 10),
    };
    const updated = [...users, newUser];
    saveUsers(updated);
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(newUser));
    setUser(newUser);
    return { ok: true };
  }

  function updateProfile(patch: Partial<Pick<AppUser, "nom" | "entreprise" | "ice" | "telephone">>) {
    if (!user) return { ok: false, error: "Non connecte." };
    const users = loadUsers();
    const updatedUser = { ...user, ...patch };
    const updatedUsers = users.map((u) => (u.id === user.id ? updatedUser : u));
    saveUsers(updatedUsers);
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(updatedUser));
    setUser(updatedUser);
    return { ok: true };
  }

  function logout() {
    window.localStorage.removeItem(SESSION_KEY);
    setUser(null);
    router.push("/login");
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, updateProfile, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit etre utilise dans AuthProvider");
  return ctx;
}

export function roleHome(role: Role) {
  return role === "admin" ? "/admin" : "/user";
}
