import axios from "axios";

// Par defaut on passe par le proxy de Vite (voir vite.config.js) : le front
// appelle "/api" sur sa propre origine, ce qui evite CORS et les surprises de
// resolution IPv4/IPv6 de "localhost" sous Windows.
export const BASE_URL = import.meta.env.VITE_API_URL || "/api";

const api = axios.create({ baseURL: BASE_URL });

export const jetons = {
  get access() {
    return localStorage.getItem("access");
  },
  get refresh() {
    return localStorage.getItem("refresh");
  },
  enregistrer(access, refresh) {
    localStorage.setItem("access", access);
    if (refresh) localStorage.setItem("refresh", refresh);
  },
  effacer() {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    localStorage.removeItem("utilisateur");
  },
};

api.interceptors.request.use((config) => {
  if (jetons.access) config.headers.Authorization = `Bearer ${jetons.access}`;
  return config;
});

// Sur 401, on tente un rafraichissement du jeton une seule fois.
api.interceptors.response.use(
  (reponse) => reponse,
  async (erreur) => {
    const requete = erreur.config;
    const estAuth = requete?.url?.includes("/auth/");
    if (erreur.response?.status === 401 && !requete._retente && !estAuth && jetons.refresh) {
      requete._retente = true;
      try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh/`, {
          refresh: jetons.refresh,
        });
        jetons.enregistrer(data.access, data.refresh);
        requete.headers.Authorization = `Bearer ${data.access}`;
        return api(requete);
      } catch {
        jetons.effacer();
        window.location.href = "/login";
      }
    }
    return Promise.reject(erreur);
  }
);

/** Message d'erreur lisible a partir d'une reponse DRF. */
export function messageErreur(erreur, defaut = "Une erreur est survenue.") {
  const data = erreur?.response?.data;
  if (!data) return erreur?.message || defaut;
  if (typeof data === "string") return data;
  if (data.detail) return data.detail;
  if (Array.isArray(data.non_field_errors)) return data.non_field_errors.join(" ");
  const premier = Object.entries(data)[0];
  if (!premier) return defaut;
  const [champ, valeur] = premier;
  return `${champ} : ${Array.isArray(valeur) ? valeur.join(" ") : valeur}`;
}

/** Telecharge un fichier binaire (Excel / PDF) depuis l'API. */
export async function telecharger(url, nomFichier) {
  const { data, headers } = await api.get(url, { responseType: "blob" });
  const type = headers["content-type"] || "application/octet-stream";
  const lien = document.createElement("a");
  lien.href = window.URL.createObjectURL(new Blob([data], { type }));
  lien.download = nomFichier;
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  window.URL.revokeObjectURL(lien.href);
}

export default api;
