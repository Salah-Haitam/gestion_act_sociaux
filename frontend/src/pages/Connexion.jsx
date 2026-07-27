import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { messageErreur } from "../api/client";
import { Message } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function Connexion() {
  const { connexion, utilisateur } = useAuth();
  const navigate = useNavigate();
  const [identifiants, setIdentifiants] = useState({ username: "", password: "" });
  const [erreur, setErreur] = useState("");
  const [enCours, setEnCours] = useState(false);

  if (utilisateur) return <Navigate to="/" replace />;

  const soumettre = async (e) => {
    e.preventDefault();
    setErreur("");
    setEnCours(true);
    try {
      await connexion(identifiants.username, identifiants.password);
      navigate("/", { replace: true });
    } catch (err) {
      setErreur(
        err?.response?.status === 401
          ? "Identifiant ou mot de passe incorrect."
          : messageErreur(err, "Connexion impossible. Le serveur est-il demarre ?")
      );
    } finally {
      setEnCours(false);
    }
  };

  return (
    <div className="ecran-connexion">
      <form className="boite-connexion" onSubmit={soumettre}>
        <div className="marque-connexion">
          <img src="/logo-marsasocial.png" alt="" />
          <div>
            <h1>MarsaSocial</h1>
            <p className="muet petit">Gestion des actions sociales</p>
          </div>
        </div>
        <h2 style={{ marginBottom: 4 }}>Espace administrateur</h2>
        <p className="muet petit" style={{ marginTop: 0, marginBottom: 22 }}>
          Connexion reservee a la Direction des Ressources Humaines.
        </p>

        {erreur && <Message type="erreur">{erreur}</Message>}

        <div className="champ">
          <label htmlFor="username">Identifiant</label>
          <input
            id="username"
            autoFocus
            autoComplete="username"
            value={identifiants.username}
            onChange={(e) => setIdentifiants({ ...identifiants, username: e.target.value })}
            required
          />
        </div>
        <div className="champ">
          <label htmlFor="password">Mot de passe</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={identifiants.password}
            onChange={(e) => setIdentifiants({ ...identifiants, password: e.target.value })}
            required
          />
        </div>

        <button type="submit" style={{ width: "100%", justifyContent: "center" }} disabled={enCours}>
          {enCours ? "Connexion…" : "Se connecter"}
        </button>

        <div className="indice">
          Compte de demonstration : <strong>admin</strong> / <strong>admin123</strong>
        </div>

        <div className="signature">
          <img src="/logo-marsa-maroc.png" alt="Marsa Maroc" />
        </div>
      </form>
    </div>
  );
}
