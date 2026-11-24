import { redirect } from "next/navigation";

// La racine sert la landing premium statique (public/landing.html) via la
// réécriture Next. Ce composant n'est qu'un filet de sécurité si la
// réécriture est désactivée.
export default function Home() {
  redirect("/landing.html");
}
