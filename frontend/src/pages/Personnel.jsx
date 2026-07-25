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

const VIDE = {
  matricule: "",
  nom: "",
  prenom: "",
  sexe: "",
  departement: "",
  date_recrutement: "",
  nb_enfants: 0,
};

const SEXES = [
  { code: "", libelle: "Non renseigne" },
  { code: "H", libelle: "Homme" },
  { code: "F", libelle: "Femme" },
];

export default function Personnel() {
  const [donnees, setDonnees] = useState({ results: [], count: 0 });
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState("");
  const [succes, setSucces] = useState("");

  const [recherche, setRecherche] = useState("");
  const [departement, setDepartement] = useState("");
  const [sexe, setSexe] = useState("");
  const [sansAide, setSansAide] = useState(false);
  const [tri, setTri] = useState("nom");
  const [page, setPage] = useState(1);
  const [departements, setDepartements] = useState([]);

  const [edition, setEdition] = useState(null); // { ...personnel, creation: bool }
  const [suppression, setSuppression] = useState(null);
  const [detail, setDetail] = useState(null); // { employe, transactions }
  const [enCours, setEnCours] = useState(false);
  const [erreurForm, setErreurForm] = useState("");

  useEffect(() => {
    api.get("/personnel/departements/").then(({ data }) => setDepartements(data)).catch(() => {});
  }, []);

  const charger = useCallback(() => {
    setChargement(true);
    const params = { page, ordering: tri };
    if (recherche) params.search = recherche;
    if (departement) params.departement = departement;
    if (sexe) params.sexe = sexe;
    const url = sansAide ? "/personnel/sans-aucune-aide/" : "/personnel/";
    api
      .get(url, { params })
      .then(({ data }) => setDonnees(data))
      .catch((err) => setErreur(messageErreur(err)))
      .finally(() => setChargement(false));
  }, [page, tri, recherche, departement, sexe, sansAide]);

  useEffect(() => {
    const minuteur = setTimeout(charger, recherche ? 300 : 0);
    return () => clearTimeout(minuteur);
  }, [charger, recherche]);

  useEffect(() => setPage(1), [recherche, departement, sexe, sansAide, tri]);

  const enregistrer = async () => {
    setEnCours(true);
    setErreurForm("");
    try {
      if (edition.creation) {
        await api.post("/personnel/", edition);
        setSucces(`Employe ${edition.matricule} ajoute.`);
      } else {
        await api.put(`/personnel/${edition.matricule}/`, edition);
        setSucces(`Employe ${edition.matricule} modifie.`);
      }
      setEdition(null);
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
      await api.delete(`/personnel/${suppression.matricule}/`);
      setSucces(`Employe ${suppression.matricule} supprime.`);
      setSuppression(null);
      charger();
    } catch (err) {
      setErreur(messageErreur(err));
      setSuppression(null);
    } finally {
      setEnCours(false);
    }
  };

  const voirDetail = async (employe) => {
    const { data } = await api.get(`/personnel/${employe.matricule}/transactions/`);
    setDetail({ employe, transactions: data });
  };

  const exporter = (format) => {
    const params = new URLSearchParams({ format, ordering: tri });
    if (recherche) params.set("search", recherche);
    if (departement) params.set("departement", departement);
    if (sexe) params.set("sexe", sexe);
    telecharger(
      `/personnel/export/?${params}`,
      `personnel.${format === "pdf" ? "pdf" : "xlsx"}`
    ).catch((err) => setErreur(messageErreur(err)));
  };

  return (
    <>
      {erreur && <Message type="erreur">{erreur}</Message>}
      {succes && <Message type="succes">{succes}</Message>}

      <section className="carte">
        <header>
          <div>
            <h2>Personnel</h2>
            <p>{donnees.count} employe(s) — services dont chacun a beneficie.</p>
          </div>
          <div className="actions">
            <button className="secondaire" onClick={() => exporter("excel")}>
              Export Excel
            </button>
            <button className="secondaire" onClick={() => exporter("pdf")}>
              Export PDF
            </button>
            <button onClick={() => { setEdition({ ...VIDE, creation: true }); setErreurForm(""); }}>
              + Ajouter un employe
            </button>
          </div>
        </header>

        <div className="barre-filtres">
          <div className="large">
            <label htmlFor="q">Recherche</label>
            <input
              id="q"
              placeholder="Nom, prenom ou matricule…"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
            />
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
            <label htmlFor="sexe">Sexe</label>
            <select id="sexe" value={sexe} onChange={(e) => setSexe(e.target.value)}>
              <option value="">Tous</option>
              <option value="H">Hommes</option>
              <option value="F">Femmes</option>
            </select>
          </div>
          <div style={{ minWidth: 210 }}>
            <label>Filtre d'equite</label>
            <label className="petit" style={{ fontWeight: 500, display: "flex", gap: 7, alignItems: "center" }}>
              <input type="checkbox" checked={sansAide} onChange={(e) => setSansAide(e.target.checked)} />
              N'ayant jamais rien recu
            </label>
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
                { cle: "matricule", titre: "Matricule", tri: "matricule" },
                { cle: "nom", titre: "Nom", tri: "nom" },
                { cle: "prenom", titre: "Prenom", tri: "prenom" },
                {
                  cle: "sexe",
                  titre: "Sexe",
                  tri: "sexe",
                  rendu: (l) =>
                    l.sexe ? l.sexe_libelle : <span className="muet petit">Non renseigne</span>,
                },
                { cle: "departement", titre: "Departement", tri: "departement" },
                {
                  cle: "date_recrutement",
                  titre: "Recrute le",
                  tri: "date_recrutement",
                  rendu: (l) => `${formatDate(l.date_recrutement)} (${l.anciennete} ans)`,
                },
                { cle: "nb_enfants", titre: "Enfants", num: true, tri: "nb_enfants" },
                {
                  cle: "services_beneficies",
                  titre: "Services beneficies",
                  rendu: (l) =>
                    l.services_beneficies.length === 0 ? (
                      <span className="badge critique">Jamais servi</span>
                    ) : (
                      <span style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {l.services_beneficies.map((s) => (
                          <span className="badge accent" key={s}>
                            {s}
                          </span>
                        ))}
                      </span>
                    ),
                },
                {
                  cle: "total_percu",
                  titre: "Total percu",
                  num: true,
                  rendu: (l) => formatMAD(l.total_percu),
                },
                {
                  cle: "actions",
                  titre: "Actions",
                  rendu: (l) => (
                    <div className="actions">
                      <button className="discret" onClick={() => voirDetail(l)}>
                        Detail
                      </button>
                      <button
                        className="discret"
                        onClick={() => { setEdition({ ...l, creation: false }); setErreurForm(""); }}
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
              cleLigne={(l) => l.matricule}
              vide="Aucun employe ne correspond aux criteres."
            />
            <Pagination page={page} setPage={setPage} total={donnees.count} />
          </>
        )}
      </section>

      {edition && (
        <Modale
          titre={edition.creation ? "Nouvel employe" : `Modifier ${edition.matricule}`}
          onFermer={() => setEdition(null)}
          onValider={enregistrer}
          enCours={enCours}
        >
          {erreurForm && <Message type="erreur">{erreurForm}</Message>}
          <div className="champ">
            <label htmlFor="mat">Matricule</label>
            <input
              id="mat"
              value={edition.matricule}
              disabled={!edition.creation}
              onChange={(e) => setEdition({ ...edition, matricule: e.target.value })}
            />
          </div>
          <div className="ligne-champs">
            <div className="champ">
              <label htmlFor="nom">Nom</label>
              <input id="nom" value={edition.nom} onChange={(e) => setEdition({ ...edition, nom: e.target.value })} />
            </div>
            <div className="champ">
              <label htmlFor="prenom">Prenom</label>
              <input
                id="prenom"
                value={edition.prenom}
                onChange={(e) => setEdition({ ...edition, prenom: e.target.value })}
              />
            </div>
          </div>
          <div className="champ">
            <label htmlFor="sexeform">Sexe</label>
            <select
              id="sexeform"
              value={edition.sexe || ""}
              onChange={(e) => setEdition({ ...edition, sexe: e.target.value })}
            >
              {SEXES.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.libelle}
                </option>
              ))}
            </select>
          </div>
          <div className="champ">
            <label htmlFor="depform">Departement</label>
            <input
              id="depform"
              list="liste-departements"
              value={edition.departement}
              onChange={(e) => setEdition({ ...edition, departement: e.target.value })}
            />
            <datalist id="liste-departements">
              {departements.map((d) => (
                <option key={d} value={d} />
              ))}
            </datalist>
          </div>
          <div className="ligne-champs">
            <div className="champ">
              <label htmlFor="rec">Date de recrutement</label>
              <input
                id="rec"
                type="date"
                value={edition.date_recrutement}
                onChange={(e) => setEdition({ ...edition, date_recrutement: e.target.value })}
              />
            </div>
            <div className="champ">
              <label htmlFor="enf">Nombre d'enfants</label>
              <input
                id="enf"
                type="number"
                min="0"
                value={edition.nb_enfants}
                onChange={(e) => setEdition({ ...edition, nb_enfants: Number(e.target.value) })}
              />
            </div>
          </div>
        </Modale>
      )}

      {detail && (
        <Modale titre={`${detail.employe.nom} ${detail.employe.prenom}`} onFermer={() => setDetail(null)}>
          <p className="muet petit" style={{ marginTop: 0 }}>
            {detail.employe.matricule} — {detail.employe.sexe_libelle} —{" "}
            {detail.employe.departement} — {detail.employe.anciennete} ans d'anciennete —{" "}
            {detail.employe.nb_enfants} enfant(s)
          </p>
          {detail.transactions.length === 0 ? (
            <Message type="attention">
              Cet employe n'a jamais beneficie d'une action sociale. Il est prioritaire.
            </Message>
          ) : (
            <Tableau
              colonnes={[
                { cle: "service", titre: "Service" },
                { cle: "annee", titre: "Annee", num: true },
                { cle: "montantTR", titre: "Montant", num: true, rendu: (l) => formatMAD(l.montantTR) },
                { cle: "date_transaction", titre: "Date", rendu: (l) => formatDate(l.date_transaction) },
              ]}
              lignes={detail.transactions}
              cleLigne={(l) => l.id_transaction}
            />
          )}
        </Modale>
      )}

      {suppression && (
        <Confirmation
          titre="Supprimer l'employe"
          message={`Supprimer ${suppression.nom} ${suppression.prenom} (${suppression.matricule}) ? Toutes ses transactions seront egalement supprimees.`}
          onFermer={() => setSuppression(null)}
          onConfirmer={supprimer}
          enCours={enCours}
        />
      )}
    </>
  );
}
