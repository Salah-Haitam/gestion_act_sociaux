import { useEffect, useState } from "react";
import api, { messageErreur } from "../api/client";
import { GrapheBarresH } from "../components/graphes";
import { Chargement, Message, Tableau, formatMAD } from "../components/ui";

export default function Clusters() {
  const [n, setN] = useState(4);
  const [donnees, setDonnees] = useState(null);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState("");
  const [groupeChoisi, setGroupeChoisi] = useState(null);

  useEffect(() => {
    setChargement(true);
    api
      .get("/ia/clusters/", { params: { n } })
      .then(({ data }) => {
        setDonnees(data);
        setGroupeChoisi(null);
      })
      .catch((err) => setErreur(messageErreur(err)))
      .finally(() => setChargement(false));
  }, [n]);

  if (erreur) return <Message type="erreur">{erreur}</Message>;
  if (chargement || !donnees) return <Chargement />;
  if (donnees.erreur) return <Message type="attention">{donnees.erreur}</Message>;

  const membres = donnees.employes.filter(
    (e) => groupeChoisi === null || e.cluster === groupeChoisi
  );

  return (
    <>
      <Message type="info">
        <strong>Segmentation K-Means.</strong> Le personnel est regroupe en profils similaires a
        partir de quatre variables normalisees : anciennete, nombre d'enfants, nombre d'aides recues
        et montant cumule percu. Les groupes dont la moyenne d'aides est nettement inferieure a la
        moyenne generale signalent un desequilibre de distribution.
      </Message>

      <section className="carte">
        <header>
          <div>
            <h2>Profils du personnel</h2>
            <p>{donnees.employes.length} employes repartis en {donnees.n_clusters} groupes.</p>
          </div>
          <div>
            <label htmlFor="n">Nombre de groupes</label>
            <select id="n" value={n} onChange={(e) => setN(Number(e.target.value))} style={{ minWidth: 120 }}>
              {[2, 3, 4, 5, 6].map((v) => (
                <option key={v} value={v}>
                  {v} groupes
                </option>
              ))}
            </select>
          </div>
        </header>

        <GrapheBarresH
          donnees={donnees.clusters.map((c) => ({
            profil: `Groupe ${c.cluster} — ${c.profil}`,
            aides: c.aides_moyennes,
          }))}
          cleX="profil"
          cleY="aides"
          nom="Aides recues (moyenne)"
        />

        <Tableau
          colonnes={[
            { cle: "cluster", titre: "Groupe", rendu: (l) => `Groupe ${l.cluster}` },
            { cle: "profil", titre: "Profil" },
            { cle: "effectif", titre: "Effectif", num: true },
            { cle: "anciennete_moyenne", titre: "Anciennete moy.", num: true, rendu: (l) => `${l.anciennete_moyenne} ans` },
            { cle: "enfants_moyen", titre: "Enfants moy.", num: true },
            { cle: "aides_moyennes", titre: "Aides moy.", num: true },
            { cle: "montant_moyen", titre: "Montant moy.", num: true, rendu: (l) => formatMAD(l.montant_moyen) },
            {
              cle: "actions",
              titre: "",
              rendu: (l) => (
                <button
                  className="discret"
                  onClick={() => setGroupeChoisi(groupeChoisi === l.cluster ? null : l.cluster)}
                >
                  {groupeChoisi === l.cluster ? "Masquer" : "Voir les membres"}
                </button>
              ),
            },
          ]}
          lignes={donnees.clusters}
          cleLigne={(l) => l.cluster}
        />
      </section>

      <section className="carte">
        <header>
          <div>
            <h2>
              {groupeChoisi === null ? "Tout le personnel" : `Membres du groupe ${groupeChoisi}`}
            </h2>
            <p>{membres.length} employe(s).</p>
          </div>
          {groupeChoisi !== null && (
            <button className="secondaire" onClick={() => setGroupeChoisi(null)}>
              Afficher tout le personnel
            </button>
          )}
        </header>
        <Tableau
          colonnes={[
            { cle: "matricule", titre: "Matricule" },
            { cle: "nom", titre: "Employe", rendu: (l) => `${l.nom} ${l.prenom}` },
            { cle: "departement", titre: "Departement" },
            { cle: "anciennete", titre: "Anciennete", num: true, rendu: (l) => `${l.anciennete} ans` },
            { cle: "nb_enfants", titre: "Enfants", num: true },
            { cle: "nb_aides", titre: "Aides recues", num: true },
            { cle: "total_percu", titre: "Total percu", num: true, rendu: (l) => formatMAD(l.total_percu) },
            { cle: "cluster", titre: "Groupe", rendu: (l) => <span className="badge accent">Groupe {l.cluster}</span> },
          ]}
          lignes={membres}
          cleLigne={(l) => l.matricule}
        />
      </section>
    </>
  );
}
