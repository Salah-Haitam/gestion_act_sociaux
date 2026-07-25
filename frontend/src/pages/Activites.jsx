import { useCallback, useEffect, useState } from "react";
import api, { messageErreur, telecharger } from "../api/client";
import {
  Chargement,
  Confirmation,
  Message,
  Modale,
  Tableau,
  formatMAD,
  statutBudget,
} from "../components/ui";

const VIDE = {
  service: "",
  montantSC: "",
  budget_alloue: "",
  description: "",
  unique_par_employe: false,
};

export default function Activites() {
  const [lignes, setLignes] = useState([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState("");
  const [succes, setSucces] = useState("");
  const [recherche, setRecherche] = useState("");
  const [tri, setTri] = useState("service");

  const [edition, setEdition] = useState(null);
  const [suppression, setSuppression] = useState(null);
  const [enCours, setEnCours] = useState(false);
  const [erreurForm, setErreurForm] = useState("");

  const charger = useCallback(() => {
    setChargement(true);
    api
      .get("/activites/", { params: { ordering: tri, search: recherche || undefined, page_size: 100 } })
      .then(({ data }) => setLignes(data.results))
      .catch((err) => setErreur(messageErreur(err)))
      .finally(() => setChargement(false));
  }, [tri, recherche]);

  useEffect(() => {
    const minuteur = setTimeout(charger, recherche ? 300 : 0);
    return () => clearTimeout(minuteur);
  }, [charger, recherche]);

  const enregistrer = async () => {
    setEnCours(true);
    setErreurForm("");
    const corps = {
      service: edition.service,
      montantSC: edition.montantSC,
      budget_alloue: edition.budget_alloue || 0,
      description: edition.description || "",
      unique_par_employe: edition.unique_par_employe,
    };
    try {
      if (edition.creation) {
        await api.post("/activites/", corps);
        setSucces(`Activite « ${corps.service} » creee.`);
      } else {
        await api.put(`/activites/${edition.id_activitee}/`, corps);
        setSucces(`Activite « ${corps.service} » modifiee.`);
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
      await api.delete(`/activites/${suppression.id_activitee}/`);
      setSucces("Activite supprimee.");
      setSuppression(null);
      charger();
    } catch (err) {
      setErreur(
        err?.response?.status === 500 || err?.response?.status === 400
          ? "Impossible de supprimer : des transactions sont rattachees a cette activite."
          : messageErreur(err)
      );
      setSuppression(null);
    } finally {
      setEnCours(false);
    }
  };

  return (
    <>
      {erreur && <Message type="erreur">{erreur}</Message>}
      {succes && <Message type="succes">{succes}</Message>}

      <section className="carte">
        <header>
          <div>
            <h2>Activites sociales</h2>
            <p>Catalogue des services proposes, montant standard et budget alloue.</p>
          </div>
          <div className="actions">
            <button
              className="secondaire"
              onClick={() => telecharger("/activites/export/?format=excel", "activites.xlsx")}
            >
              Export Excel
            </button>
            <button onClick={() => { setEdition({ ...VIDE, creation: true }); setErreurForm(""); }}>
              + Ajouter une activite
            </button>
          </div>
        </header>

        <div className="barre-filtres">
          <div className="large">
            <label htmlFor="q">Recherche</label>
            <input
              id="q"
              placeholder="Nom du service…"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
            />
          </div>
        </div>

        {chargement ? (
          <Chargement />
        ) : (
          <Tableau
            tri={tri}
            onTri={setTri}
            colonnes={[
              {
                cle: "service",
                titre: "Service",
                tri: "service",
                rendu: (l) => (
                  <div>
                    <div className="gras">{l.service}</div>
                    {l.description && <div className="muet petit">{l.description}</div>}
                  </div>
                ),
              },
              {
                cle: "unique_par_employe",
                titre: "Renouvelable",
                rendu: (l) =>
                  l.unique_par_employe ? (
                    <span className="badge attention">Une seule fois</span>
                  ) : (
                    <span className="badge">Chaque annee</span>
                  ),
              },
              { cle: "montantSC", titre: "Montant standard", num: true, tri: "montantSC", rendu: (l) => formatMAD(l.montantSC) },
              { cle: "budget_alloue", titre: "Budget alloue", num: true, tri: "budget_alloue", rendu: (l) => formatMAD(l.budget_alloue) },
              { cle: "montant_consomme", titre: "Consomme", num: true, rendu: (l) => formatMAD(l.montant_consomme) },
              {
                cle: "taux_consommation",
                titre: "Consommation",
                rendu: (l) => (
                  <div className="barre-score">
                    <div className={`jauge ${statutBudget(l.taux_consommation)}`} style={{ flex: 1 }}>
                      <span style={{ width: `${Math.min(l.taux_consommation ?? 0, 100)}%` }} />
                    </div>
                    <span className="chiffre">
                      {l.taux_consommation === null ? "—" : `${l.taux_consommation} %`}
                    </span>
                  </div>
                ),
              },
              { cle: "nb_beneficiaires", titre: "Beneficiaires", num: true },
              {
                cle: "actions",
                titre: "Actions",
                rendu: (l) => (
                  <div className="actions">
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
            lignes={lignes}
            cleLigne={(l) => l.id_activitee}
            vide="Aucune activite enregistree."
          />
        )}
      </section>

      {edition && (
        <Modale
          titre={edition.creation ? "Nouvelle activite" : `Modifier « ${edition.service} »`}
          onFermer={() => setEdition(null)}
          onValider={enregistrer}
          enCours={enCours}
        >
          {erreurForm && <Message type="erreur">{erreurForm}</Message>}
          <div className="champ">
            <label htmlFor="svc">Service</label>
            <input
              id="svc"
              value={edition.service}
              onChange={(e) => setEdition({ ...edition, service: e.target.value })}
              placeholder="Aide scolaire, Hajj, Mariage…"
            />
          </div>
          <div className="ligne-champs">
            <div className="champ">
              <label htmlFor="msc">Montant standard (MAD)</label>
              <input
                id="msc"
                type="number"
                step="0.01"
                min="0"
                value={edition.montantSC}
                onChange={(e) => setEdition({ ...edition, montantSC: e.target.value })}
              />
            </div>
            <div className="champ">
              <label htmlFor="bud">Budget alloue (MAD)</label>
              <input
                id="bud"
                type="number"
                step="0.01"
                min="0"
                value={edition.budget_alloue}
                onChange={(e) => setEdition({ ...edition, budget_alloue: e.target.value })}
              />
            </div>
          </div>
          <div className="champ">
            <label htmlFor="desc">Description</label>
            <textarea
              id="desc"
              rows="2"
              value={edition.description}
              onChange={(e) => setEdition({ ...edition, description: e.target.value })}
            />
          </div>
          <label className="petit" style={{ fontWeight: 500, display: "flex", gap: 8, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={edition.unique_par_employe}
              onChange={(e) => setEdition({ ...edition, unique_par_employe: e.target.checked })}
            />
            Service non renouvelable — un employe ne peut en beneficier qu'une seule fois
          </label>
        </Modale>
      )}

      {suppression && (
        <Confirmation
          titre="Supprimer l'activite"
          message={`Supprimer « ${suppression.service} » ? L'operation echouera si des transactions y sont rattachees.`}
          onFermer={() => setSuppression(null)}
          onConfirmer={supprimer}
          enCours={enCours}
        />
      )}
    </>
  );
}
