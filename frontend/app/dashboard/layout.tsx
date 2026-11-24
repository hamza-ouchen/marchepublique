import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sou9na — Tableau de bord",
  description:
    "Vos opportunités de marchés publics, scores de Match, verdicts et dossiers suivis.",
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
