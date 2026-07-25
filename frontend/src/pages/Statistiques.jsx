import { useEffect, useMemo, useState } from "react";
import api, { messageErreur, telecharger } from "../api/client";
import { GrapheBarres, GrapheBarresH, GrapheLignes, SERIES } from "../components/graphes";
import { Chargement, Message, Tableau, Tuile, formatMAD } from "../components/ui";

export default function Statistiques() {
  const [stats, setStats] = useState(null);
  const [annees, setAnnees] = useState([]);
  const [annee, setAnnee] = useState("");
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    api.get("/transactions/annees/").then(({ data }) => setAnnees(data)).catch(() => {});
  }, []);

  useEffect(() => {
    api
      .get("/stats/", { params: annee ? { annee } : {} })
      .then(({ data }) => setStats(data))
      .catch((err) => setErreur(messageErreur(err)));
  }, [annee]);

  // Les trois services les plus dotes, suivis annee par annee.
  const evolutionTop3 = useMemo(() => {
    if (!stats) return { donnees: [], series: [] };
    const top = [...stats.par_service]
      .sort((a, b) => Number(b.total) - Number(a.total))
      .slice(0, 3)
      .map((s) => s.service);
    const parAnnee = {};
    stats.evolution.forEach(({ annee: an, service, total }) => {
      if (!top.includes(service)) return;
      parAnnee[an] = parAnnee[an] || { annee: String(an) };
      parAnnee[an][service] = Number(total);
    });
    const donnees = Object.values(parAnnee).sort((a, b) => a.annee.localeCompare(b.annee));
    donnees.forEach((d) => top.forEach((s) => (d[s] = d[s] || 0)));
    return { donnees, series: top.map((s, i) => ({ cle: s, nom: s, couleur: SERIES[i] })) };
  }, [stats]);

  if (erreur) return <Message type="erreur">{erreur}</Message>;
  if (!stats) return <Chargement />;

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
        <div style={{ alignSelf: "flex-end" }}>
          <div className="actions">
            <button
              className="secondaire"
              onClick={() =>
                telecharger(
                  `/stats/rapport-annuel/?annee=${annee || new Date().getFullYear()}&format=excel`,
                  `rapport_annuel_${annee || new Date().getFullYear()}.xlsx`
                )
              }
            >
              Rapport annuel (Excel)
            </button>
            <button
              className="secondaire"
              onClick={() =>
                telecharger(
                  `/stats/rapport-annuel/?annee=${annee || new Date().getFullYear()}&format=pdf`,
                  `rapport_annuel_${annee || new Date().getFullYear()}.pdf`
                )
              }
            >
              Rapport annuel (PDF)
            </button>
          </div>
        </div>
      </div>

      <div className="grille k4" style={{ marginBottom: 18 }}>
        <Tuile etiquette="Montant distribue" valeur={formatMAD(stats.total_distribue)} variante="info" />
        <Tuile etiquette="Transactions" valeur={stats.nb_transactions} note={`Moyenne ${formatMAD(stats.montant_moyen)}`} />
        <Tuile
          etiquette="Couverture globale"
          valeur={`${stats.taux_couverture_global} %`}
          note={`${stats.nb_beneficiaires} / ${stats.effectif} employes servis`}
          variante="ok"
        />
        <Tuile etiquette="Jamais servis" valeur={stats.nb_jamais_servis} variante={stats.nb_jamais_servis ? "alerte" : "ok"} />
      </div>

      <div className="grille k2">
        <section className="carte">
          <header>
            <div>
              <h2>Montant distribue par service</h2>
              <p>{annee ? `Exercice ${annee}` : "Cumul de tous les exercices"}.</p>
            </div>
          </header>
          <GrapheBarres
            donnees={stats.par_service.map((s) => ({ service: s.service, total: Number(s.total) }))}
            cleX="service"
            cleY="total"
            nom="Montant"
            unite="MAD"
            formateur={(v) => Number(v).toLocaleString("fr-FR")}
          />
        </section>

        <section className="carte">
          <header>
            <div>
              <h2>Nombre de beneficiaires par service</h2>
              <p>Employes distincts servis au moins une fois.</p>
            </div>
          </header>
          <GrapheBarresH
            donnees={[...stats.par_service]
              .sort((a, b) => b.nb_beneficiaires - a.nb_beneficiaires)
              .map((s) => ({ service: s.service, beneficiaires: s.nb_beneficiaires }))}
            cleX="service"
            cleY="beneficiaires"
            nom="Beneficiaires"
          />
        </section>
      </div>

      <section className="carte">
        <header>
          <div>
            <h2>Evolution des depenses</h2>
            <p>Montant total verse par exercice, tous services confondus.</p>
          </div>
        </header>
        <GrapheLignes
          donnees={stats.par_annee.map((a) => ({ annee: String(a.annee), total: Number(a.total) }))}
          cleX="annee"
          series={[{ cle: "total", nom: "Montant verse (MAD)" }]}
          formateur={(v) => Number(v).toLocaleString("fr-FR")}
        />
      </section>

      {evolutionTop3.series.length > 1 && (
        <section className="carte">
          <header>
            <div>
              <h2>Evolution des trois principaux services</h2>
              <p>Montant verse par exercice pour les services les plus dotes.</p>
            </div>
          </header>
          <GrapheLignes
            donnees={evolutionTop3.donnees}
            cleX="annee"
            series={evolutionTop3.series}
            formateur={(v) => Number(v).toLocaleString("fr-FR")}
          />
        </section>
      )}

      <section className="carte">
        <header>
          <div>
            <h2>Detail par service</h2>
            <p>Montants, beneficiaires et taux de couverture.</p>
          </div>
        </header>
        <Tableau
          colonnes={[
            { cle: "service", titre: "Service" },
            { cle: "nb_beneficiaires", titre: "Beneficiaires", num: true },
            { cle: "nb_transactions", titre: "Transactions", num: true },
            { cle: "total", titre: "Montant distribue", num: true, rendu: (l) => formatMAD(l.total) },
            { cle: "budget_alloue", titre: "Budget alloue", num: true, rendu: (l) => formatMAD(l.budget_alloue) },
            {
              cle: "taux_couverture",
              titre: "Taux de couverture",
              num: true,
              rendu: (l) => `${l.taux_couverture} %`,
            },
          ]}
          lignes={[...stats.par_service].sort((a, b) => Number(b.total) - Number(a.total))}
          cleLigne={(l) => l.id_activitee}
        />
      </section>

      {stats.par_sexe?.length > 1 && (
        <section className="carte">
          <header>
            <div>
              <h2>Equite hommes / femmes</h2>
              <p>
                Comparaison des taux de couverture et des montants moyens par bénéficiaire. Un écart
                marqué signale un déséquilibre dans la distribution.
              </p>
            </div>
          </header>
          <Tableau
            colonnes={[
              { cle: "libelle", titre: "Sexe" },
              { cle: "effectif", titre: "Effectif", num: true },
              { cle: "nb_beneficiaires", titre: "Servis", num: true },
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
              { cle: "total", titre: "Montant total", num: true, rendu: (l) => formatMAD(l.total) },
              {
                cle: "montant_moyen",
                titre: "Moyenne par beneficiaire",
                num: true,
                rendu: (l) => formatMAD(l.montant_moyen),
              },
            ]}
            lignes={stats.par_sexe}
            cleLigne={(l) => l.sexe || "nr"}
          />
        </section>
      )}

      <section className="carte">
        <header>
          <div>
            <h2>Detail par departement</h2>
            <p>Equite de la distribution entre entites.</p>
          </div>
        </header>
        <Tableau
          colonnes={[
            { cle: "departement", titre: "Departement" },
            { cle: "effectif", titre: "Effectif", num: true },
            { cle: "nb_beneficiaires", titre: "Servis", num: true },
            { cle: "taux_couverture", titre: "Couverture", num: true, rendu: (l) => `${l.taux_couverture} %` },
            { cle: "total", titre: "Montant", num: true, rendu: (l) => formatMAD(l.total) },
          ]}
          lignes={[...stats.par_departement].sort((a, b) => a.taux_couverture - b.taux_couverture)}
          cleLigne={(l) => l.departement}
        />
      </section>
    </>
  );
}
