import { useEffect, useRef, useState } from "react";
import api, { messageErreur } from "../api/client";
import { Message, Tableau, formatMAD } from "./ui";

const SUGGESTIONS = [
  "Qui n'a jamais rien recu ?",
  "Qui n'a pas beneficie de l'aide scolaire en 2024 ?",
  "Montre-moi ceux qui meritent le Hajj",
  "Quel service est le moins distribue ?",
  "Quel est l'etat du budget ?",
];

const ACCUEIL = {
  role: "assistant",
  texte:
    "Bonjour. Posez votre question en francais : bénéficiaires et non-bénéficiaires d'un " +
    "service, montants, budget, historique d'un employé, priorisation…\n" +
    "Je garde le fil : après une question sur un service, « et en 2023 ? » suffit.",
};

const MONTANTS = ["montantTR", "budget_alloue", "consomme", "restant", "total_percu"];

/** Chat réutilisable : page pleine (compact=false) ou bulle flottante (compact=true). */
export default function Discussion({ compact = false }) {
  const [messages, setMessages] = useState([ACCUEIL]);
  const [question, setQuestion] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState("");
  // Fil de la conversation, renvoyé par l'API et reposté au tour suivant.
  const [contexte, setContexte] = useState({});
  const finRef = useRef(null);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, enCours]);

  const envoyer = async (texte) => {
    const contenu = (texte ?? question).trim();
    if (!contenu || enCours) return;
    setMessages((m) => [...m, { role: "admin", texte: contenu }]);
    setQuestion("");
    setEnCours(true);
    setErreur("");
    try {
      const { data } = await api.post("/ia/chatbot/", { question: contenu, contexte });
      setContexte(data.contexte || {});
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          texte: data.reponse,
          colonnes: data.colonnes,
          donnees: data.donnees,
          moteur: data.moteur,
        },
      ]);
    } catch (err) {
      setErreur(messageErreur(err));
    } finally {
      setEnCours(false);
    }
  };

  const reinitialiser = () => {
    setMessages([ACCUEIL]);
    setContexte({});
    setErreur("");
  };

  return (
    <>
      {erreur && <Message type="erreur">{erreur}</Message>}

      {!compact && (
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => envoyer(s)} disabled={enCours}>
              {s}
            </button>
          ))}
        </div>
      )}

      <div className={`discussion ${compact ? "compacte" : ""}`}>
        {messages.map((m, i) => (
          <div key={i} className={`bulle ${m.role}`}>
            {m.texte}
            {m.moteur === "llm" && (
              <span className="badge accent marque-moteur" title="Question comprise avec le renfort du modele de langage">
                IA
              </span>
            )}
            {m.donnees?.length > 0 && (
              <div className="resultats">
                <Tableau
                  colonnes={m.colonnes.map((c) => ({
                    cle: c,
                    titre: c.replace(/_/g, " "),
                    num: MONTANTS.includes(c) || ["taux", "annee", "score", "rang"].includes(c),
                    rendu: MONTANTS.includes(c) ? (l) => formatMAD(l[c]) : undefined,
                  }))}
                  lignes={m.donnees}
                  cleLigne={(l, i2) => l.matricule || l.service || i2}
                />
                {m.donnees.length >= 200 && (
                  <p className="muet petit">Affichage limité aux 200 premières lignes.</p>
                )}
              </div>
            )}
          </div>
        ))}
        {enCours && <div className="bulle assistant muet">Analyse de la question…</div>}
        <div ref={finRef} />
      </div>

      {compact && messages.length === 1 && (
        <div className="suggestions compactes">
          {SUGGESTIONS.slice(0, 3).map((s) => (
            <button key={s} onClick={() => envoyer(s)} disabled={enCours}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        className="saisie"
        onSubmit={(e) => {
          e.preventDefault();
          envoyer();
        }}
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Posez votre question…"
          aria-label="Question"
        />
        <button type="submit" disabled={enCours || !question.trim()}>
          Envoyer
        </button>
      </form>

      <div className="entre petit muet" style={{ marginTop: 8 }}>
        <span>
          {contexte.service
            ? `Sujet : ${contexte.service}${contexte.annee ? ` — ${contexte.annee}` : ""}${
                contexte.departement ? ` — ${contexte.departement}` : ""
              }`
            : "Aucun sujet en cours"}
        </span>
        <button className="discret" onClick={reinitialiser} disabled={messages.length <= 1}>
          Nouvelle conversation
        </button>
      </div>
    </>
  );
}
