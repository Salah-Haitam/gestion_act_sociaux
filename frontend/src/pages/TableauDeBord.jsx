import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { messageErreur } from "../api/client";
import { GrapheBarres, GrapheLignes } from "../components/graphes";
import { Chargement, Message, Tableau, Tuile, formatMAD, statutBudget } from "../components/ui";

export default function TableauDeBord() {
  const [stats, setStats] = useState(null);
  const [budget, setBudget] = useState(null);
  const [annee, setAnnee] = useState("");
  const [annees, setAnnees] = useState([]);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    api.get("/transactions/annees/").then(({ data }) => setAnnees(data)).catch(() => {});
  }, []);

  useEffect(() => {
    setErreur("");
    const params = annee ? { annee } : {};
    Promise.all([
      api.get("/stats/", { params }),
      api.get("/activites/budget/", { params }),
    ])
      .then(([s, b]) => {
        setStats(s.data);
        setBudget(b.data);
      })
      .catch((err) => setErreur(messageErreur(err)));
  }, [annee]);

  if (erreur) return <Message type="erreur">{erreur}</Message>;
  if (!stats || !budget) return <Chargement />;

  const alertes = budget.resultats.filter((l) => ["seuil_atteint", "depassement"].includes(l.alerte));
  const serviceOublie = [...stats.par_service].sort((a, b) => a.taux_couverture - b.taux_couverture)[0];

  return (
    <>
      <div className="barre-filtres">
        <div>
          <label htmlFor="annee">Exercice</label>
          <select id="annee" value={annee} onChange={(e) => setAnnee(e.target.value)}>
            <option value="">Toutes les annees</option>
            {annees.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grille k4" style={{ marginBottom: 18 }}>
        <Tuile etiquette="Effectif" valeur={stats.effectif} note={`${stats.nb_activites} services proposes`} />
        <Tuile
          etiquette="Beneficiaires"
          valeur={stats.nb_beneficiaires}
          note={`${stats.taux_couverture_global} % de couverture`}
          variante="ok"
        />
        <Tuile
          etiquette="Jamais servis"
          valeur={stats.nb_jamais_servis}
          note="Opportunites manquees a traiter"
          variante={stats.nb_jamais_servis > 0 ? "alerte" : "ok"}
        />
        <Tuile
          etiquette="Montant distribue"
          valeur={formatMAD(stats.total_distribue)}
          note={`${stats.nb_transactions} transactions — moyenne ${formatMAD(stats.montant_moyen)}`}
          variante="info"
        />
      </div>

      {stats.nb_jamais_servis > 0 && (
        <Message type="attention">
          <strong>{stats.nb_jamais_servis} employe(s) n'ont jamais beneficie d'aucune action sociale.</strong>{" "}
          Le service le moins couvert est « {serviceOublie?.service} » ({serviceOublie?.taux_couverture} %).{" "}
          <Link to="/equite">Voir la liste des non-beneficiaires →</Link>
        </Message>
      )}

      {alertes.length > 0 && (
        <Message type="erreur">
          <strong>Budget :</strong> {alertes.length} service(s) au-dela du seuil d'alerte (
          {budget.seuil_alerte} %) — {alertes.map((a) => a.service).join(", ")}.{" "}
          <Link to="/budget">Consulter le suivi budgetaire →</Link>
        </Message>
      )}

      <div className="grille k2">
        <section className="carte">
          <header>
            <div>
              <h2>Montant distribue par service</h2>
              <p>{annee ? `Exercice ${annee}` : "Tous exercices confondus"}, en dirhams.</p>
            </div>
          </header>
          <GrapheBarres
            donnees={stats.par_service.map((s) => ({
              service: s.service,
              total: Number(s.total),
            }))}
            cleX="service"
            cleY="total"
            nom="Montant distribue"
            unite="MAD"
            formateur={(v) => Number(v).toLocaleString("fr-FR")}
          />
        </section>

        <section className="carte">
          <header>
            <div>
              <h2>Evolution annuelle des depenses</h2>
              <p>Total verse et nombre de transactions par exercice.</p>
            </div>
          </header>
          <GrapheLignes
            donnees={stats.par_annee.map((a) => ({
              annee: String(a.annee),
              total: Number(a.total),
            }))}
            cleX="annee"
            series={[{ cle: "total", nom: "Montant verse (MAD)" }]}
            formateur={(v) => Number(v).toLocaleString("fr-FR")}
          />
        </section>
      </div>

      <section className="carte">
        <header>
          <div>
            <h2>Couverture par service</h2>
            <p>Part de l'effectif ayant beneficie de chaque action sociale.</p>
          </div>
          <Link className="petit" to="/equite">
            Analyser l'equite →
          </Link>
        </header>
        <Tableau
          colonnes={[
            { cle: "service", titre: "Service" },
            { cle: "nb_beneficiaires", titre: "Beneficiaires", num: true },
            {
              cle: "non",
              titre: "Non servis",
              num: true,
              rendu: (l) => stats.effectif - l.nb_beneficiaires,
            },
            { cle: "nb_transactions", titre: "Transactions", num: true },
            {
              cle: "total",
              titre: "Montant",
              num: true,
              rendu: (l) => formatMAD(l.total),
            },
            {
              cle: "taux_couverture",
              titre: "Taux de couverture",
              rendu: (l) => (
                <div className="barre-score">
                  <div className="piste">
                    <span style={{ width: `${Math.min(l.taux_couverture, 100)}%` }} />
                  </div>
                  <span className="chiffre">{l.taux_couverture} %</span>
                </div>
              ),
            },
          ]}
          lignes={[...stats.par_service].sort((a, b) => a.taux_couverture - b.taux_couverture)}
          cleLigne={(l) => l.id_activitee}
        />
      </section>

      <section className="carte">
        <header>
          <div>
            <h2>Repartition par departement</h2>
            <p>Effectif servi et montants verses, par entite.</p>
          </div>
        </header>
        <Tableau
          colonnes={[
            { cle: "departement", titre: "Departement" },
            { cle: "effectif", titre: "Effectif", num: true },
            { cle: "nb_beneficiaires", titre: "Servis", num: true },
            {
              cle: "taux_couverture",
              titre: "Couverture",
              num: true,
              rendu: (l) => `${l.taux_couverture} %`,
            },
            { cle: "total", titre: "Montant", num: true, rendu: (l) => formatMAD(l.total) },
          ]}
          lignes={stats.par_departement}
          cleLigne={(l) => l.departement}
        />
      </section>

      <section className="carte">
        <header>
          <div>
            <h2>Consommation budgetaire</h2>
            <p>Seuil d'alerte a {budget.seuil_alerte} % du budget alloue.</p>
          </div>
          <Link className="petit" to="/budget">
            Detail du budget →
          </Link>
        </header>
        <Tableau
          colonnes={[
            { cle: "service", titre: "Service" },
            { cle: "budget_alloue", titre: "Alloue", num: true, rendu: (l) => formatMAD(l.budget_alloue) },
            { cle: "consomme", titre: "Consomme", num: true, rendu: (l) => formatMAD(l.consomme) },
            { cle: "restant", titre: "Restant", num: true, rendu: (l) => formatMAD(l.restant) },
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
          ]}
          lignes={budget.resultats}
          cleLigne={(l) => l.id_activitee}
        />
      </section>
    </>
  );
}
