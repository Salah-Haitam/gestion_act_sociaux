import { useEffect, useState } from "react";
import api, { messageErreur, telecharger } from "../api/client";
import { Chargement, Message, Tableau, Tuile, formatMAD } from "../components/ui";

export default function Recommandations() {
  const [activites, setActivites] = useState([]);
  const [departements, setDepartements] = useState([]);
  const [service, setService] = useState("");
  const [departement, setDepartement] = useState("");
  const [limite, setLimite] = useState(20);
  const [eligibles, setEligibles] = useState(true);

  const [resultat, setResultat] = useState(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    api.get("/activites/", { params: { page_size: 100 } }).then(({ data }) => {
      setActivites(data.results);
      if (data.results.length) setService(String(data.results[0].id_activitee));
    });
    api.get("/personnel/departements/").then(({ data }) => setDepartements(data));
  }, []);

  useEffect(() => {
    if (!service) return;
    setChargement(true);
    setErreur("");
    api
      .get("/ia/recommandations/", {
        params: {
          id_activitee: service,
          limite,
          eligibles: eligibles ? "true" : "false",
          departement: departement || undefined,
        },
      })
      .then(({ data }) => setResultat(data))
      .catch((err) => setErreur(messageErreur(err)))
      .finally(() => setChargement(false));
  }, [service, limite, eligibles, departement]);

  const exporter = (format) => {
    const params = new URLSearchParams({
      format,
      id_activitee: service,
      limite,
      eligibles: eligibles ? "true" : "false",
    });
    if (departement) params.set("departement", departement);
    telecharger(
      `/ia/recommandations/export/?${params}`,
      `priorisation.${format === "pdf" ? "pdf" : "xlsx"}`
    ).catch((err) => setErreur(messageErreur(err)));
  };

  return (
    <>
      {erreur && <Message type="erreur">{erreur}</Message>}

      <Message type="info">
        <strong>Comment le score est calcule.</strong> Chaque employe recoit une note sur 100
        combinant : n'avoir jamais beneficie du service vise (poids dominant), le faible nombre
        d'aides recues toutes categories confondues, le faible montant deja percu, l'anciennete et la
        charge familiale. La ponderation s'adapte a la nature du service (une aide scolaire pese
        davantage le nombre d'enfants, un pelerinage pese l'anciennete).
      </Message>

      <section className="carte">
        <header>
          <div>
            <h2>Priorisation des beneficiaires</h2>
            <p>Classement decroissant par score d'equite pour le service selectionne.</p>
          </div>
          <div className="actions">
            <button className="secondaire" onClick={() => exporter("excel")} disabled={!resultat}>
              Export Excel
            </button>
            <button className="secondaire" onClick={() => exporter("pdf")} disabled={!resultat}>
              Export PDF
            </button>
          </div>
        </header>

        <div className="barre-filtres">
          <div className="large">
            <label htmlFor="svc">Service a attribuer</label>
            <select id="svc" value={service} onChange={(e) => setService(e.target.value)}>
              {activites.map((a) => (
                <option key={a.id_activitee} value={a.id_activitee}>
                  {a.service}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="dep">Departement</label>
            <select id="dep" value={departement} onChange={(e) => setDepartement(e.target.value)}>
              <option value="">Tous</option>
              {departements.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="lim">Nombre de propositions</label>
            <select id="lim" value={limite} onChange={(e) => setLimite(Number(e.target.value))}>
              {[10, 20, 50, 100].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div style={{ minWidth: 210 }}>
            <label>Filtre</label>
            <label className="petit" style={{ fontWeight: 500, display: "flex", gap: 7, alignItems: "center" }}>
              <input type="checkbox" checked={eligibles} onChange={(e) => setEligibles(e.target.checked)} />
              Masquer les employes deja servis
            </label>
          </div>
        </div>

        {chargement || !resultat ? (
          <Chargement />
        ) : (
          <>
            <div className="grille k3" style={{ marginBottom: 18 }}>
              <Tuile etiquette="Montant standard" valeur={formatMAD(resultat.montantSC)} />
              <Tuile
                etiquette="Budget restant"
                valeur={formatMAD(resultat.budget_restant)}
                variante={Number(resultat.budget_restant) <= 0 ? "alerte" : "ok"}
              />
              <Tuile
                etiquette="Beneficiaires finançables"
                valeur={resultat.beneficiaires_financables}
                note="Au montant standard, avec le budget restant"
                variante="info"
              />
            </div>

            {Number(resultat.budget_restant) <= 0 && (
              <Message type="attention">
                L'enveloppe de « {resultat.service} » est epuisee : aucune nouvelle attribution ne
                peut etre financee sans rallonge budgetaire.
              </Message>
            )}

            <Tableau
              colonnes={[
                { cle: "rang", titre: "Rang", num: true },
                {
                  cle: "score",
                  titre: "Score d'equite",
                  rendu: (l) => (
                    <div className="barre-score">
                      <div className="piste">
                        <span style={{ width: `${Math.min(l.score, 100)}%` }} />
                      </div>
                      <span className="chiffre">{l.score}</span>
                    </div>
                  ),
                },
                { cle: "matricule", titre: "Matricule" },
                { cle: "nom", titre: "Employe", rendu: (l) => `${l.nom} ${l.prenom}` },
                { cle: "departement", titre: "Departement" },
                { cle: "anciennete", titre: "Anciennete", num: true, rendu: (l) => `${l.anciennete} ans` },
                { cle: "nb_enfants", titre: "Enfants", num: true },
                {
                  cle: "nb_aides_total",
                  titre: "Aides recues",
                  num: true,
                  rendu: (l) =>
                    l.nb_aides_total === 0 ? <span className="badge critique">Aucune</span> : l.nb_aides_total,
                },
                { cle: "total_percu", titre: "Total percu", num: true, rendu: (l) => formatMAD(l.total_percu) },
                {
                  cle: "justifications",
                  titre: "Justification",
                  rendu: (l) => (
                    <ul className="liste-puces">
                      {l.justifications.map((j) => (
                        <li key={j}>{j}</li>
                      ))}
                    </ul>
                  ),
                },
              ]}
              lignes={resultat.resultats}
              cleLigne={(l) => l.matricule}
              vide="Aucun employe eligible pour ce service."
            />
          </>
        )}
      </section>
    </>
  );
}
