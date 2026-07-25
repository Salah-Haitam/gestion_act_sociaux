import { createContext, useContext, useEffect, useMemo, useState } from "react";
import api, { jetons } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [utilisateur, setUtilisateur] = useState(() => {
    const brut = localStorage.getItem("utilisateur");
    return brut ? JSON.parse(brut) : null;
  });
  const [chargement, setChargement] = useState(Boolean(jetons.access));

  // Au demarrage, on verifie que le jeton stocke est toujours valable.
  useEffect(() => {
    if (!jetons.access) return setChargement(false);
    api
      .get("/auth/me/")
      .then(({ data }) => {
        setUtilisateur(data);
        localStorage.setItem("utilisateur", JSON.stringify(data));
      })
      .catch(() => {
        jetons.effacer();
        setUtilisateur(null);
      })
      .finally(() => setChargement(false));
  }, []);

  const valeur = useMemo(
    () => ({
      utilisateur,
      chargement,
      async connexion(username, password) {
        const { data } = await api.post("/auth/login/", { username, password });
        jetons.enregistrer(data.access, data.refresh);
        setUtilisateur(data.utilisateur);
        localStorage.setItem("utilisateur", JSON.stringify(data.utilisateur));
        return data.utilisateur;
      },
      async deconnexion() {
        try {
          await api.post("/auth/logout/");
        } catch {
          // La session serveur peut deja etre expiree : on nettoie quand meme.
        }
        jetons.effacer();
        setUtilisateur(null);
      },
    }),
    [utilisateur, chargement]
  );

  return <AuthContext.Provider value={valeur}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const contexte = useContext(AuthContext);
  if (!contexte) throw new Error("useAuth doit etre utilise dans AuthProvider");
  return contexte;
}
