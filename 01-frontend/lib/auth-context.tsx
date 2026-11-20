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
import { requestOtp, verifyOtp } from "./api";

// ---------------------------------------------------------------------------
// AUTH — authentification par numero WhatsApp + code OTP (SOU9NA-REF-001
// §3.2/§3.4) : aucun mot de passe, aucune donnee sensible dans le navigateur.
// Tant que le backend OTP (Hamza Midouni, FastAPI /auth/otp + /auth/verify)
// n'est pas branche (NEXT_PUBLIC_API_URL absent), le registre d'utilisateurs
// ci-dessous reste local au navigateur en MODE TEST, pour que le prototype
// soit utilisable de bout en bout — a supprimer des que l'API reelle gere
// la creation/lecture des comptes.
// ---------------------------------------------------------------------------

const USERS_KEY = "sou9na_users";
const SESSION_KEY = "sou9na_session";

const SEED_ADMIN: AppUser = {
  id: "admin-seed",
  nom: "Administrateur Sou9na",
  telephone: "212600000000",
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
    if (!parsed.find((u) => u.telephone === SEED_ADMIN.telephone)) {
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

interface SignupProfile {
  nom: string;
  telephone: string;
  entreprise: string;
  email?: string;
  ice?: string;
  secteurActivite?: string;
  region?: string;
  qualifications?: string;
}

interface AuthContextValue {
  user: AppUser | null;
  loading: boolean;
  requestOtp: (telephone: string) => Promise<{ ok: boolean; error?: string; devCode?: string }>;
  confirmLogin: (
    telephone: string,
    code: string,
    space: Role
  ) => Promise<{ ok: boolean; error?: string }>;
  confirmSignup: (
    telephone: string,
    code: string,
    profile: SignupProfile
  ) => Promise<{ ok: boolean; error?: string }>;
  updateProfile: (
    patch: Partial<
      Pick<AppUser, "nom" | "entreprise" | "ice" | "secteurActivite" | "region" | "qualifications">
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
        const session = JSON.parse(raw) as { user: AppUser };
        setUser(session.user);
      } catch {
        // ignore
      }
    }
    setLoading(false);
  }, []);

  function persistSession(token: string, nextUser: AppUser) {
    // On ne garde que le profil non sensible + le jeton de session —
    // jamais de mot de passe, jamais de secret.
    window.localStorage.setItem(SESSION_KEY, JSON.stringify({ token, user: nextUser }));
    setUser(nextUser);
  }

  async function doRequestOtp(telephone: string) {
    return requestOtp(telephone);
  }

  async function confirmLogin(telephone: string, code: string, space: Role) {
    const result = await verifyOtp(telephone, code);
    if (!result.ok) return { ok: false, error: result.error ?? "Code incorrect." };

    if (result.user) {
      // Backend reel branche : il a resolu l'utilisateur et son role.
      if (result.user.role !== space) {
        return {
          ok: false,
          error:
            space === "admin"
              ? "Ce numero n'est pas associe a un compte Admin."
              : "Ce numero est associe a un compte Admin.",
        };
      }
      persistSession(result.token ?? "", result.user as AppUser);
      return { ok: true };
    }

    // MODE TEST (pas de backend) : on resout l'utilisateur localement.
    const found = loadUsers().find((u) => u.telephone === telephone);
    if (!found) {
      return { ok: false, error: "Aucun compte associe a ce numero." };
    }
    if (found.role !== space) {
      return {
        ok: false,
        error:
          space === "admin"
            ? "Ce numero n'est pas associe a un compte Admin."
            : "Ce numero est associe a un compte Admin.",
      };
    }
    persistSession(result.token ?? "", found);
    return { ok: true };
  }

  async function confirmSignup(telephone: string, code: string, profile: SignupProfile) {
    const result = await verifyOtp(telephone, code);
    if (!result.ok) return { ok: false, error: result.error ?? "Code incorrect." };

    if (result.user) {
      persistSession(result.token ?? "", result.user as AppUser);
      return { ok: true };
    }

    // MODE TEST : on cree l'utilisateur localement.
    const users = loadUsers();
    if (users.find((u) => u.telephone === telephone)) {
      return { ok: false, error: "Un compte existe deja avec ce numero." };
    }
    const newUser: AppUser = {
      id: `u-${Date.now()}`,
      nom: profile.nom,
      telephone,
      email: profile.email,
      role: "user",
      entreprise: profile.entreprise,
      ice: profile.ice,
      secteurActivite: profile.secteurActivite,
      region: profile.region,
      qualifications: profile.qualifications,
      dateInscription: new Date().toISOString().slice(0, 10),
    };
    saveUsers([...users, newUser]);
    persistSession(result.token ?? "", newUser);
    return { ok: true };
  }

  function updateProfile(
    patch: Partial<
      Pick<AppUser, "nom" | "entreprise" | "ice" | "secteurActivite" | "region" | "qualifications">
    >
  ) {
    if (!user) return { ok: false, error: "Non connecte." };
    const users = loadUsers();
    const updatedUser = { ...user, ...patch };
    const updatedUsers = users.map((u) => (u.id === user.id ? updatedUser : u));
    saveUsers(updatedUsers);
    const raw = window.localStorage.getItem(SESSION_KEY);
    const token = raw ? (JSON.parse(raw) as { token: string }).token : "";
    persistSession(token, updatedUser);
    return { ok: true };
  }

  function logout() {
    window.localStorage.removeItem(SESSION_KEY);
    setUser(null);
    router.push("/login");
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        requestOtp: doRequestOtp,
        confirmLogin,
        confirmSignup,
        updateProfile,
        logout,
      }}
    >
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
