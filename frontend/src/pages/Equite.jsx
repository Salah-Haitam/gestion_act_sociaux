import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { messageErreur, telecharger } from "../api/client";
import { GrapheBarresH } from "../components/graphes";
import {
  Chargement,
  Message,
  Tableau,
  Tuile,
  formatDate,
  formatMAD,
} from "../components/ui";

export default function Equite() {
  const [activites, setActivites] = useState([]);
  const [annees, setAnnees] = useState([]);
  const [departements, setDepartements] = useState([]);
  const [couverture, setCouverture] = useState(null);

  const [service, setService] = useState("");
  const [annee, setAnnee] = useState("");
  const [departement, setDepartement] = useState("");
  const [onglet, setOnglet] = useState("non"); // "non" | "oui"

  const [nonBeneficiaires, setNonBeneficiaires] = useState(null);
  const [beneficiaires, setBeneficiaires] = useState(null);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    api.get("/activites/", { params: { page_size: 100 } }).then(({ data }) => {
      setActivites(data.results);
      if (data.results.length) setService(String(data.results[0].id_activitee));
    });
    api.get("/transactions/annees/").then(({ data }) => setAnnees(data));
    api.get("/personnel/departements/").then(({ data }) => setDepartements(data));
  }, []);

  useEffect(() => {
    api
      .get("/stats/couverture/", { params: annee ? { annee } : {} })
      .then(({ data }) => setCouverture(data))
      .catch(() => {});
  }, [annee]);

  useEffect(() => {
    if (!service) return;
    setChargement(true);
    setErreur("");
    const params = {};
    if (annee) params.annee = annee;
    if (departement) params.departement = departement;
    Promise.all([
      api.get(`/activites/${service}/non-beneficiaires/`, { params }),
      api.get(`/activites/${service}/beneficiaires/`, { params: annee ? { annee } : {} }),
    ])
      .then(([non, oui]) => {
        setNonBeneficiaires(non.data);
        setBeneficiaires(oui.data);
      })
      .catch((err) => setErreur(messageErreur(err)))
      .finally(() => setChargement(false));
  }, [service, annee, departement]);

  const exporter = (format) => {
    const params = new URLSearchParams({ format });
    if (annee) params.set("annee", annee);
    if (departement) params.set("departement", departement);
    telecharger(
      `/activites/${service}/export-non-beneficiaires/?${params}`,
      `non_beneficiaires.${format === "pdf" ? "pdf" : "xlsx"}`
    ).catch((err) => setErreur(messageErreur(err)));
  };

  const serviceChoisi = activites.find((a) => String(a.id_activitee) === String(service));

  return (
    <>
      {erreur && <Message type="erreur">{erreur}</Message>}

      <Message type="info">
        <strong>Objectif : ne rater aucune opportunite.</strong> Pour chaque service, la plateforme
        separe les employes deja servis de ceux qui ne l'ont jamais ete — ces derniers sont les
        beneficiaires a cibler en priorite.
      </Message>

      <section className="carte">
        <header>
          <div>
            <h2>Taux de couverture par service</h2>
            <p>
              Part de l'effectif ayant beneficie de chaque action sociale
              {annee ? ` en ${annee}` : ""}. Les services sous 25 % sont mis en evidence.
            </p>
          </div>
        </header>
        {couverture ? (
          <>
            <GrapheBarresH
              donnees={couverture.resultats.map((r) => ({
                service: r.service,
                taux: r.taux_couverture,
              }))}
              cleX="service"
              cleY="taux"
              nom="Taux de couverture"
              unite="%"
              seuilFaible={25}
            />
            <div className="legende">
              <span className="item">
                <span className="pastille" style={{ background: "#2a78d6" }} />
                Couverture ≥ 25 %
              </span>
              <span className="item">
                <span className="pastille" style={{ background: "#eb6834" }} />
                Couverture &lt; 25 % — service sous-distribue
              </span>
            </div>
          </>
        ) : (
          <Chargement />
        )}
      </section>

      <section className="carte">
        <header>
          <div>
            <h2>Analyse service par service</h2>
            <p>Selectionnez un service pour voir qui en a beneficie et qui a ete oublie.</p>
          </div>
          <div className="actions">
            <button className="secondaire" onClick={() => exporter("excel")} disabled={!service}>
              Export Excel (oublies)
            </button>
            <button className="secondaire" onClick={() => exporter("pdf")} disabled={!service}>
              Export PDF (oublies)
            </button>
          </div>
        </header>

        <div className="barre-filtres">
          <div className="large">
            <label htmlFor="svc">Service</label>
            <select id="svc" value={service} onChange={(e) => setService(e.target.value)}>
              {activites.map((a) => (
                <option key={a.id_activitee} value={a.id_activitee}>
                  {a.service}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="an">Exercice</label>
            <select id="an" value={annee} onChange={(e) => setAnnee(e.target.value)}>
              <option value="">Depuis toujours</option>
              {annees.map((a) => (
                <option key={a} value={a}>
                  {a}
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
        </div>

        {chargement || !nonBeneficiaires || !beneficiaires ? (
          <Chargement />
        ) : (
          <>
            <div className="grille k3" style={{ marginBottom: 18 }}>
              <Tuile etiquette="Effectif total" valeur={nonBeneficiaires.effectif_total} />
              <Tuile
                etiquette="Deja beneficiaires"
                valeur={nonBeneficiaires.effectif_total - nonBeneficiaires.total}
                note={`${nonBeneficiaires.taux_couverture} % de couverture`}
                variante="ok"
              />
              <Tuile
                etiquette="Jamais beneficiaires"
                valeur={nonBeneficiaires.total}
                note="Opportunites manquees"
                variante={nonBeneficiaires.total > 0 ? "alerte" : "ok"}
              />
            </div>

            <div className="actions" style={{ marginBottom: 14 }}>
              <button
                className={onglet === "non" ? "" : "secondaire"}
                onClick={() => setOnglet("non")}
              >
                Non beneficiaires ({nonBeneficiaires.total})
              </button>
              <button
                className={onglet === "oui" ? "" : "secondaire"}
                onClick={() => setOnglet("oui")}
              >
                Deja servis ({beneficiaires.total})
              </button>
            </div>

            {onglet === "non" ? (
              <>
                <p className="muet petit" style={{ marginTop: 0 }}>
                  Requete equivalente : <code>LEFT JOIN transaction … WHERE transaction IS NULL</code>{" "}
                  sur le service « {serviceChoisi?.service} »{annee ? ` et l'annee ${annee}` : ""}.
                </p>
                <Tableau
                  colonnes={[
                    { cle: "matricule", titre: "Matricule" },
                    { cle: "nom", titre: "Nom", rendu: (l) => `${l.nom} ${l.prenom}` },
                    { cle: "departement", titre: "Departement" },
                    {
                      cle: "date_recrutement",
                      titre: "Recrute le",
                      rendu: (l) => `${formatDate(l.date_recrutement)} (${l.anciennete} ans)`,
                    },
                    { cle: "nb_enfants", titre: "Enfants", num: true },
                    {
                      cle: "nb_aides_total",
                      titre: "Aides recues (tous services)",
                      num: true,
                      rendu: (l) =>
                        l.nb_aides_total === 0 ? (
                          <span className="badge critique">Aucune</span>
                        ) : (
                          l.nb_aides_total
                        ),
                    },
                    {
                      cle: "total_percu",
                      titre: "Total percu",
                      num: true,
                      rendu: (l) => formatMAD(l.total_percu),
                    },
                  ]}
                  lignes={nonBeneficiaires.resultats}
                  cleLigne={(l) => l.matricule}
                  vide="Tout le personnel a deja beneficie de ce service."
                />
                <p className="petit" style={{ marginBottom: 0 }}>
                  <Link to="/recommandations">
                    Classer ces employes par score d'equite (priorisation IA) →
                  </Link>
                </p>
              </>
            ) : (
              <Tableau
                colonnes={[
                  { cle: "matricule", titre: "Matricule" },
                  { cle: "nom", titre: "Nom", rendu: (l) => `${l.nom} ${l.prenom}` },
                  { cle: "departement", titre: "Departement" },
                  { cle: "nb_enfants", titre: "Enfants", num: true },
                  { cle: "montantTR", titre: "Montant recu", num: true, rendu: (l) => formatMAD(l.montantTR) },
                  { cle: "date_transaction", titre: "Date", rendu: (l) => formatDate(l.date_transaction) },
                  { cle: "annee", titre: "Annee", num: true },
                ]}
                lignes={beneficiaires.resultats}
                cleLigne={(l) => l.id_transaction}
                vide="Personne n'a encore beneficie de ce service."
              />
            )}
          </>
        )}
      </section>
    </>
  );
}
