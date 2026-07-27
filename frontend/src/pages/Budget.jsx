import { useEffect, useState } from "react";
import api, { messageErreur } from "../api/client";
import { GrapheBarres } from "../components/graphes";
import { Chargement, Message, Tableau, Tuile, formatMAD, statutBudget } from "../components/ui";

const LIBELLES = {
  ok: { texte: "Sous controle", classe: "bon" },
  seuil_atteint: { texte: "Seuil atteint", classe: "attention" },
  depassement: { texte: "Depassement", classe: "critique" },
  budget_non_defini: { texte: "Budget non defini", classe: "" },
};

export default function Budget() {
  const [budget, setBudget] = useState(null);
  const [annees, setAnnees] = useState([]);
  const [annee, setAnnee] = useState("");
  const [seuil, setSeuil] = useState(80);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    api.get("/transactions/annees/").then(({ data }) => setAnnees(data)).catch(() => {});
  }, []);

  useEffect(() => {
    const params = { seuil };
    if (annee) params.annee = annee;
    api
      .get("/activites/budget/", { params })
      .then(({ data }) => setBudget(data))
      .catch((err) => setErreur(messageErreur(err)));
  }, [annee, seuil]);

  if (erreur) return <Message type="erreur">{erreur}</Message>;
  if (!budget) return <Chargement />;

  const enAlerte = budget.resultats.filter((l) =>
    ["seuil_atteint", "depassement"].includes(l.alerte)
  );

  return (
    <>
      <div className="barre-filtres">
        <div>
          <label htmlFor="an">Exercice</label>
          <select id="an" value={annee} onChange={(e) => setAnnee(e.target.value)}>
            <option value="">Tous exercices</option>
            {annees.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="seuil">Seuil d'alerte (%)</label>
          <input
            id="seuil"
            type="number"
            min="1"
            max="100"
            value={seuil}
            onChange={(e) => setSeuil(Number(e.target.value) || 80)}
          />
        </div>
      </div>

      <div className="grille k4" style={{ marginBottom: 18 }}>
        <Tuile etiquette="Budget alloue" valeur={formatMAD(budget.total_alloue)} />
        <Tuile
          etiquette="Consomme"
          valeur={formatMAD(budget.total_consomme)}
          note={budget.taux_global !== null ? `${budget.taux_global} % de l'enveloppe` : null}
          variante="info"
        />
        <Tuile
          etiquette="Restant"
          valeur={formatMAD(budget.total_restant)}
          variante={budget.total_restant < 0 ? "alerte" : "ok"}
        />
        <Tuile
          etiquette="Services en alerte"
          valeur={enAlerte.length}
          note={`Seuil fixe a ${budget.seuil_alerte} %`}
          variante={enAlerte.length ? "alerte" : "ok"}
        />
      </div>

      {enAlerte.length > 0 && (
        <Message type="attention">
          <strong>Attention :</strong> {enAlerte.length} service(s) atteignent ou depassent le seuil
          de {budget.seuil_alerte} % —{" "}
          {enAlerte.map((l) => `${l.service} (${l.taux_consommation} %)`).join(", ")}.
        </Message>
      )}

      <section className="carte">
        <header>
          <div>
            <h2>Consommation par service</h2>
            <p>Montant deja verse rapporte a l'enveloppe allouee.</p>
          </div>
        </header>
        <GrapheBarres
          donnees={budget.resultats.map((l) => ({
            service: l.service,
            consomme: Number(l.consomme),
          }))}
          cleX="service"
          cleY="consomme"
          nom="Consomme"
          unite="MAD"
          formateur={(v) => Number(v).toLocaleString("fr-FR")}
        />
      </section>

      <section className="carte">
        <header>
          <div>
            <h2>Detail budgetaire</h2>
            <p>
              Etat de chaque enveloppe{annee ? ` pour l'exercice ${annee}` : ""}. Le statut est
              indique par un libelle, jamais par la couleur seule.
            </p>
          </div>
        </header>
        <Tableau
          colonnes={[
            { cle: "service", titre: "Service" },
            { cle: "montantSC", titre: "Montant standard", num: true, rendu: (l) => formatMAD(l.montantSC) },
            { cle: "budget_alloue", titre: "Alloue", num: true, rendu: (l) => formatMAD(l.budget_alloue) },
            { cle: "consomme", titre: "Consomme", num: true, rendu: (l) => formatMAD(l.consomme) },
            {
              cle: "restant",
              titre: "Restant",
              num: true,
              rendu: (l) => (
                <span className={l.restant < 0 ? "gras" : ""} style={l.restant < 0 ? { color: "#9c2020" } : {}}>
                  {formatMAD(l.restant)}
                </span>
              ),
            },
            { cle: "nb_transactions", titre: "Transactions", num: true },
            {
              cle: "taux_consommation",
              titre: "Consommation",
              rendu: (l) => (
                <div className="barre-score">
                  <div
                    className={`jauge ${statutBudget(l.taux_consommation, budget.seuil_alerte)}`}
                    style={{ flex: 1 }}
                  >
                    <span style={{ width: `${Math.min(l.taux_consommation ?? 0, 100)}%` }} />
                  </div>
                  <span className="chiffre">
                    {l.taux_consommation === null ? "—" : `${l.taux_consommation} %`}
                  </span>
                </div>
              ),
            },
            {
              cle: "alerte",
              titre: "Statut",
              rendu: (l) => (
                <span className={`badge ${LIBELLES[l.alerte].classe}`}>{LIBELLES[l.alerte].texte}</span>
              ),
            },
          ]}
          lignes={budget.resultats}
          cleLigne={(l) => l.id_activitee}
        />
      </section>
    </>
  );
}
