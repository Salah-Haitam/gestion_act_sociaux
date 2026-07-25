import { useEffect } from "react";

/* ---------- Formatage --------------------------------------------------- */

export const formatMAD = (valeur) =>
  `${Number(valeur || 0).toLocaleString("fr-FR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} MAD`;

export const formatCourt = (valeur) => {
  const n = Number(valeur || 0);
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} M`;
  if (Math.abs(n) >= 1_000) return `${Math.round(n / 1000)} k`;
  return String(Math.round(n));
};

export const formatDate = (valeur) =>
  valeur ? new Date(valeur).toLocaleDateString("fr-FR") : "—";

/* ---------- Briques ----------------------------------------------------- */

export function Tuile({ etiquette, valeur, note, variante = "" }) {
  return (
    <div className={`tuile ${variante}`}>
      <div className="etiquette">{etiquette}</div>
      <div className="valeur">{valeur}</div>
      {note && <div className="note">{note}</div>}
    </div>
  );
}

export function Message({ type = "info", children }) {
  const icones = { info: "i", succes: "✓", attention: "!", erreur: "✕" };
  return (
    <div className={`message ${type}`} role={type === "erreur" ? "alert" : "status"}>
      <span className="icone" aria-hidden="true">
        {icones[type]}
      </span>
      <div>{children}</div>
    </div>
  );
}

export function Chargement({ texte = "Chargement…" }) {
  return <div className="chargement">{texte}</div>;
}

export function Modale({ titre, onFermer, onValider, texteValider = "Enregistrer", enCours, children }) {
  useEffect(() => {
    const echap = (e) => e.key === "Escape" && onFermer();
    window.addEventListener("keydown", echap);
    return () => window.removeEventListener("keydown", echap);
  }, [onFermer]);

  return (
    <div className="voile" onMouseDown={(e) => e.target === e.currentTarget && onFermer()}>
      <div className="modale" role="dialog" aria-modal="true" aria-label={titre}>
        <header>
          <h2>{titre}</h2>
          <button className="fermer" onClick={onFermer} aria-label="Fermer">
            ×
          </button>
        </header>
        <div className="corps">{children}</div>
        {onValider && (
          <footer>
            <button className="secondaire" onClick={onFermer}>
              Annuler
            </button>
            <button onClick={onValider} disabled={enCours}>
              {enCours ? "Enregistrement…" : texteValider}
            </button>
          </footer>
        )}
      </div>
    </div>
  );
}

/** Confirmation avant une suppression. */
export function Confirmation({ titre, message, onFermer, onConfirmer, enCours }) {
  return (
    <div className="voile" onMouseDown={(e) => e.target === e.currentTarget && onFermer()}>
      <div className="modale" style={{ maxWidth: 420 }} role="alertdialog" aria-modal="true">
        <header>
          <h2>{titre}</h2>
          <button className="fermer" onClick={onFermer} aria-label="Fermer">
            ×
          </button>
        </header>
        <div className="corps">{message}</div>
        <footer>
          <button className="secondaire" onClick={onFermer}>
            Annuler
          </button>
          <button className="danger" onClick={onConfirmer} disabled={enCours}>
            {enCours ? "Suppression…" : "Supprimer"}
          </button>
        </footer>
      </div>
    </div>
  );
}

/**
 * Tableau generique, tri par en-tete.
 * colonnes : [{ cle, titre, num?, tri? (clef d'ordering API), rendu?(ligne) }]
 */
export function Tableau({ colonnes, lignes, cleLigne, tri, onTri, vide = "Aucun resultat." }) {
  // Un clic trie en ascendant, un second inverse le sens.
  const basculer = (colonne) => {
    if (!onTri || !colonne.tri) return;
    onTri(tri === colonne.tri ? `-${colonne.tri}` : colonne.tri);
  };

  return (
    <div className="tableau-conteneur">
      <table>
        <thead>
          <tr>
            {colonnes.map((c) => {
              // Une colonne sans clef de tri n'est jamais active, meme quand le
              // tableau est utilise sans tri du tout (tri et c.tri indefinis).
              const actif = Boolean(c.tri) && (tri === c.tri || tri === `-${c.tri}`);
              const descendant = actif && tri.startsWith("-");
              return (
                <th
                  key={c.cle}
                  className={`${c.num ? "num" : ""} ${c.tri && onTri ? "triable" : ""}`}
                  onClick={() => basculer(c)}
                  aria-sort={actif ? (descendant ? "descending" : "ascending") : undefined}
                >
                  {c.titre}
                  {actif && <span className="fleche">{descendant ? "▼" : "▲"}</span>}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {lignes.length === 0 ? (
            <tr>
              <td colSpan={colonnes.length} className="vide">
                {vide}
              </td>
            </tr>
          ) : (
            lignes.map((ligne, i) => (
              <tr key={cleLigne ? cleLigne(ligne, i) : i}>
                {colonnes.map((c) => (
                  <td key={c.cle} className={c.num ? "num" : ""}>
                    {c.rendu ? c.rendu(ligne) : ligne[c.cle] ?? "—"}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ page, setPage, total, taille = 25 }) {
  const pages = Math.max(1, Math.ceil(total / taille));
  if (total === 0) return null;
  return (
    <div className="pagination">
      <span>
        {total} resultat{total > 1 ? "s" : ""} — page {page} / {pages}
      </span>
      <div className="actions">
        <button className="secondaire" onClick={() => setPage(page - 1)} disabled={page <= 1}>
          ‹ Precedent
        </button>
        <button className="secondaire" onClick={() => setPage(page + 1)} disabled={page >= pages}>
          Suivant ›
        </button>
      </div>
    </div>
  );
}

/** Etat d'un budget -> classe de statut (palette de statut reservee). */
export function statutBudget(taux) {
  if (taux === null || taux === undefined) return "";
  if (taux >= 100) return "critique";
  if (taux >= 90) return "serieux";
  if (taux >= 80) return "attention";
  return "";
}
