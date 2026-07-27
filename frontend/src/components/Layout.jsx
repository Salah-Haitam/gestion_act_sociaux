import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import BulleAssistant from "./BulleAssistant";

const MENU = [
  {
    groupe: "Pilotage",
    liens: [
      { to: "/", libelle: "Tableau de bord", puce: "▤", exact: true },
      { to: "/statistiques", libelle: "Statistiques", puce: "▦" },
      { to: "/budget", libelle: "Budget", puce: "◧" },
    ],
  },
  {
    groupe: "Equite",
    liens: [
      { to: "/equite", libelle: "Servis / non servis", puce: "⚖" },
      { to: "/recommandations", libelle: "Priorisation IA", puce: "★" },
      { to: "/clusters", libelle: "Profils (K-Means)", puce: "◍" },
      { to: "/assistant", libelle: "Assistant admin", puce: "✎" },
    ],
  },
  {
    groupe: "Donnees",
    liens: [
      { to: "/personnel", libelle: "Personnel", puce: "◉" },
      { to: "/activites", libelle: "Activites", puce: "◈" },
      { to: "/transactions", libelle: "Transactions", puce: "⇄" },
    ],
  },
];

export default function Layout() {
  const { utilisateur, deconnexion } = useAuth();

  return (
    <div className="app">
      <aside className="laterale">
        <div className="marque">
          <img src="/logo-marsasocial.png" alt="" className="embleme" />
          <div>
            <strong>MarsaSocial</strong>
            <span>Actions sociales — Espace RH</span>
          </div>
        </div>
        <nav>
          {MENU.map((section) => (
            <div key={section.groupe}>
              <div className="groupe">{section.groupe}</div>
              {section.liens.map((lien) => (
                <NavLink
                  key={lien.to}
                  to={lien.to}
                  end={lien.exact}
                  className={({ isActive }) => (isActive ? "actif" : "")}
                >
                  <span className="puce" aria-hidden="true">
                    {lien.puce}
                  </span>
                  {lien.libelle}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="pied">
          Connecte : <strong>{utilisateur?.username}</strong>
        </div>
      </aside>

      <div className="contenu">
        <header className="entete">
          <div>
            <h1>Gestion des actions sociales</h1>
            <p>Suivi des prestations sociales du personnel et de leur equite de distribution.</p>
          </div>
          <div className="actions" style={{ alignItems: "center" }}>
            <img src="/logo-marsa-maroc.png" alt="Marsa Maroc" className="logo-entete" />
            <button className="secondaire" onClick={deconnexion}>
              Deconnexion
            </button>
          </div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>

      {/* Assistant accessible depuis tous les ecrans. */}
      <BulleAssistant />
    </div>
  );
}
