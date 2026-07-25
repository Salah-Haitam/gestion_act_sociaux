import { useEffect, useState } from "react";
import api from "../api/client";
import Discussion from "../components/Discussion";
import { Message } from "../components/ui";

export default function Assistant() {
  const [moteur, setMoteur] = useState(null);

  useEffect(() => {
    api
      .get("/ia/chatbot/")
      .then(({ data }) => setMoteur(data))
      .catch(() => setMoteur(null));
  }, []);

  return (
    <>
      <Message type="info">
        <strong>Comment l'assistant comprend vos questions.</strong> Un moteur à règles analyse la
        phrase (service, année, département, sexe, employé, intention), tolère les abréviations et
        les fautes de frappe, et garde le fil de la conversation.
        {moteur?.llm_actif ? (
          <>
            {" "}
            Un modèle de langage ({moteur.modele}) vient en renfort pour les tournures libres. Il ne
            fait que <strong>traduire la question</strong> : les chiffres proviennent tous de la base
            de données, et aucune donnée nominative ne sort du serveur.
          </>
        ) : (
          <>
            {" "}
            Le renfort par modèle de langage est désactivé (aucune clé configurée) : le moteur à
            règles fonctionne seul, hors ligne.
          </>
        )}
      </Message>

      <section className="carte">
        <header>
          <div>
            <h2>Assistant administrateur</h2>
            <p>
              L'assistant est aussi accessible depuis n'importe quel écran, via la bulle en bas à
              droite.
            </p>
          </div>
          {moteur && (
            <span className={`badge ${moteur.llm_actif ? "accent" : ""}`}>
              {moteur.llm_actif ? `Règles + IA (${moteur.modele})` : "Règles seules"}
            </span>
          )}
        </header>
        <Discussion />
      </section>
    </>
  );
}
