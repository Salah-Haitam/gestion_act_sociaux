import { useCallback, useEffect, useState } from "react";
import api, { messageErreur, telecharger } from "../api/client";
import {
  Chargement,
  Confirmation,
  Message,
  Modale,
  Pagination,
  Tableau,
  formatDate,
  formatMAD,
} from "../components/ui";

const aujourdhui = new Date().toISOString().slice(0, 10);
const VIDE = {
  matricule: "",
  id_activitee: "",
  montantTR: "",
  duree: 0,
  date_transaction: aujourdhui,
};

export default function Transactions() {
  const [donnees, setDonnees] = useState({ results: [], count: 0 });
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState("");
  const [succes, setSucces] = useState("");

  const [recherche, setRecherche] = useState("");
  const [service, setService] = useState("");
  const [annee, setAnnee] = useState("");
  const [departement, setDepartement] = useState("");
  const [tri, setTri] = useState("-date_transaction");
  const [page, setPage] = useState(1);

  const [activites, setActivites] = useState([]);
  const [annees, setAnnees] = useState([]);
  const [departements, setDepartements] = useState([]);
  const [employes, setEmployes] = useState([]);

  const [edition, setEdition] = useState(null);
  const [suppression, setSuppression] = useState(null);
  const [enCours, setEnCours] = useState(false);
  const [erreurForm, setErreurForm] = useState("");
  const [verification, setVerification] = useState(null); // alerte doublon

  useEffect(() => {
    api.get("/activites/", { params: { page_size: 100 } }).then(({ data }) => setActivites(data.results));
    api.get("/transactions/annees/").then(({ data }) => setAnnees(data));
    api.get("/personnel/departements/").then(({ data }) => setDepartements(data));
    api
      .get("/personnel/", { params: { page_size: 500, ordering: "nom" } })
      .then(({ data }) => setEmployes(data.results));
  }, []);

  const charger = useCallback(() => {
    setChargement(true);
    const params = { page, ordering: tri };
    if (recherche) params.search = recherche;
    if (service) params.id_activitee = service;
    if (annee) params.annee = annee;
    if (departement) params.departement = departement;
    api
      .get("/transactions/", { params })
      .then(({ data }) => setDonnees(data))
      .catch((err) => setErreur(messageErreur(err)))
      .finally(() => setChargement(false));
  }, [page, tri, recherche, service, annee, departement]);

  useEffect(() => {
    const minuteur = setTimeout(charger, recherche ? 300 : 0);
    return () => clearTimeout(minuteur);
  }, [charger, recherche]);

  useEffect(() => setPage(1), [recherche, service, annee, departement, tri]);

  // Controle de doublon des que l'admin a choisi un employe, un service et une date.
  useEffect(() => {
    if (!edition?.matricule || !edition?.id_activitee) return setVerification(null);
    const anneeSaisie = edition.date_transaction?.slice(0, 4);
    api
      .get("/transactions/verifier-doublon/", {
        params: {
          matricule: edition.matricule,
          id_activitee: edition.id_activitee,
          annee: anneeSaisie,
        },
      })
      .then(({ data }) => setVerification(data))
      .catch(() => setVerification(null));
  }, [edition?.matricule, edition?.id_activitee, edition?.date_transaction]);

  const choisirActivite = (id) => {
    const activite = activites.find((a) => String(a.id_activitee) === String(id));
    setEdition((e) => ({
      ...e,
      id_activitee: id,
      // Pre-remplit avec le montant standard du service choisi.
      montantTR: activite && !e.montantTR ? activite.montantSC : e.montantTR,
    }));
  };

  const enregistrer = async () => {
    setEnCours(true);
    setErreurForm("");
    const corps = {
      matricule: edition.matricule,
      id_activitee: edition.id_activitee,
      montantTR: edition.montantTR,
      duree: edition.duree || 0,
      date_transaction: edition.date_transaction,
    };
    try {
      if (edition.creation) {
        await api.post("/transactions/", corps);
        setSucces("Transaction enregistree.");
      } else {
        await api.put(`/transactions/${edition.id_transaction}/`, corps);
        setSucces("Transaction modifiee.");
      }
      setEdition(null);
      setVerification(null);
      charger();
    } catch (err) {
      setErreurForm(messageErreur(err));
    } finally {
      setEnCours(false);
    }
  };

  const supprimer = async () => {
    setEnCours(true);
    try {
      await api.delete(`/transactions/${suppression.id_transaction}/`);
      setSucces("Transaction supprimee.");
      setSuppression(null);
      charger();
    } catch (err) {
      setErreur(messageErreur(err));
      setSuppression(null);
    } finally {
      setEnCours(false);
    }
  };

  const exporter = (format) => {
    const params = new URLSearchParams({ format, ordering: tri });
    if (recherche) params.set("search", recherche);
    if (service) params.set("id_activitee", service);
    if (annee) params.set("annee", annee);
    if (departement) params.set("departement", departement);
    telecharger(`/transactions/export/?${params}`, `transactions.${format === "pdf" ? "pdf" : "xlsx"}`).catch(
      (err) => setErreur(messageErreur(err))
    );
  };

  return (
    <>
      {erreur && <Message type="erreur">{erreur}</Message>}
      {succes && <Message type="succes">{succes}</Message>}

      <section className="carte">
        <header>
          <div>
            <h2>Transactions</h2>
            <p>{donnees.count} attribution(s) — qui a beneficie de quoi, pour quel montant.</p>
          </div>
          <div className="actions">
            <button className="secondaire" onClick={() => exporter("excel")}>
              Export Excel
            </button>
            <button className="secondaire" onClick={() => exporter("pdf")}>
              Export PDF
            </button>
            <button
              onClick={() => {
                setEdition({ ...VIDE, creation: true });
                setErreurForm("");
                setVerification(null);
              }}
            >
              + Attribuer un service
            </button>
          </div>
        </header>

        <div className="barre-filtres">
          <div className="large">
            <label htmlFor="q">Recherche</label>
            <input
              id="q"
              placeholder="Nom, prenom, matricule ou service…"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="svc">Service</label>
            <select id="svc" value={service} onChange={(e) => setService(e.target.value)}>
              <option value="">Tous</option>
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
            <label htmlFor="an">Annee</label>
            <select id="an" value={annee} onChange={(e) => setAnnee(e.target.value)}>
              <option value="">Toutes</option>
              {annees.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
        </div>

        {chargement ? (
          <Chargement />
        ) : (
          <>
            <Tableau
              tri={tri}
              onTri={setTri}
              colonnes={[
                { cle: "id_transaction", titre: "N°", num: true, tri: "id_transaction" },
                { cle: "matricule", titre: "Matricule" },
                {
                  cle: "nom",
                  titre: "Employe",
                  tri: "matricule__nom",
                  rendu: (l) => `${l.nom} ${l.prenom}`,
                },
                { cle: "departement", titre: "Departement" },
                { cle: "service", titre: "Service", tri: "id_activitee__service" },
                { cle: "montantTR", titre: "Montant", num: true, tri: "montantTR", rendu: (l) => formatMAD(l.montantTR) },
                { cle: "duree", titre: "Duree", num: true, rendu: (l) => (l.duree ? `${l.duree} j` : "—") },
                {
                  cle: "date_transaction",
                  titre: "Date",
                  tri: "date_transaction",
                  rendu: (l) => formatDate(l.date_transaction),
                },
                { cle: "annee", titre: "Annee", num: true, tri: "annee" },
                {
                  cle: "actions",
                  titre: "Actions",
                  rendu: (l) => (
                    <div className="actions">
                      <button
                        className="discret"
                        onClick={() =>
                          telecharger(
                            `/transactions/${l.id_transaction}/attestation/`,
                            `attestation_${l.matricule}_${l.id_transaction}.pdf`
                          )
                        }
                      >
                        Attestation
                      </button>
                      <button
                        className="discret"
                        onClick={() => {
                          setEdition({ ...l, creation: false });
                          setErreurForm("");
                        }}
                      >
                        Modifier
                      </button>
                      <button className="discret rouge" onClick={() => setSuppression(l)}>
                        Supprimer
                      </button>
                    </div>
                  ),
                },
              ]}
              lignes={donnees.results}
              cleLigne={(l) => l.id_transaction}
              vide="Aucune transaction ne correspond aux criteres."
            />
            <Pagination page={page} setPage={setPage} total={donnees.count} />
          </>
        )}
      </section>

      {edition && (
        <Modale
          titre={edition.creation ? "Attribuer un service" : `Modifier la transaction n°${edition.id_transaction}`}
          onFermer={() => {
            setEdition(null);
            setVerification(null);
          }}
          onValider={enregistrer}
          enCours={enCours}
        >
          {erreurForm && <Message type="erreur">{erreurForm}</Message>}

          {/* Alerte automatique : l'employe a-t-il deja beneficie de ce service ? */}
          {verification && (
            <Message
              type={verification.bloquant ? "erreur" : verification.historique.length ? "attention" : "succes"}
            >
              {verification.message}
              {verification.historique.length > 0 && (
                <ul className="liste-puces">
                  {verification.historique.map((h) => (
                    <li key={h.id_transaction}>
                      {h.annee} — {formatMAD(h.montantTR)} le {formatDate(h.date_transaction)}
                    </li>
                  ))}
                </ul>
              )}
            </Message>
          )}

          <div className="champ">
            <label htmlFor="emp">Employe</label>
            <select
              id="emp"
              value={edition.matricule}
              onChange={(e) => setEdition({ ...edition, matricule: e.target.value })}
            >
              <option value="">— Choisir un employe —</option>
              {employes.map((p) => (
                <option key={p.matricule} value={p.matricule}>
                  {p.matricule} — {p.nom} {p.prenom} ({p.departement})
                </option>
              ))}
            </select>
          </div>

          <div className="champ">
            <label htmlFor="act">Service</label>
            <select id="act" value={edition.id_activitee} onChange={(e) => choisirActivite(e.target.value)}>
              <option value="">— Choisir un service —</option>
              {activites.map((a) => (
                <option key={a.id_activitee} value={a.id_activitee}>
                  {a.service} — {formatMAD(a.montantSC)}
                  {a.unique_par_employe ? " (non renouvelable)" : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="ligne-champs">
            <div className="champ">
              <label htmlFor="mt">Montant verse (MAD)</label>
              <input
                id="mt"
                type="number"
                step="0.01"
                min="0"
                value={edition.montantTR}
                onChange={(e) => setEdition({ ...edition, montantTR: e.target.value })}
              />
            </div>
            <div className="champ">
              <label htmlFor="dur">Duree (jours)</label>
              <input
                id="dur"
                type="number"
                min="0"
                value={edition.duree}
                onChange={(e) => setEdition({ ...edition, duree: Number(e.target.value) })}
              />
            </div>
            <div className="champ">
              <label htmlFor="dt">Date</label>
              <input
                id="dt"
                type="date"
                value={edition.date_transaction}
                onChange={(e) => setEdition({ ...edition, date_transaction: e.target.value })}
              />
            </div>
          </div>
          <p className="muet petit" style={{ margin: 0 }}>
            L'annee de l'exercice est deduite automatiquement de la date saisie.
          </p>
        </Modale>
      )}

      {suppression && (
        <Confirmation
          titre="Supprimer la transaction"
          message={`Supprimer l'attribution « ${suppression.service} » a ${suppression.nom} ${suppression.prenom} (${formatMAD(
            suppression.montantTR
          )}) ?`}
          onFermer={() => setSuppression(null)}
          onConfirmer={supprimer}
          enCours={enCours}
        />
      )}
    </>
  );
}
