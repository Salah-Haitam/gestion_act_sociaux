import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Discussion from "./Discussion";

/**
 * Assistant accessible depuis n'importe quel ecran, sous forme de bulle
 * flottante. Le panneau reste monte une fois ouvert : la conversation n'est
 * donc pas perdue quand on le referme pour consulter un tableau.
 */
export default function BulleAssistant() {
  const [ouvert, setOuvert] = useState(false);
  const [dejaOuvert, setDejaOuvert] = useState(false);

  useEffect(() => {
    if (ouvert) setDejaOuvert(true);
  }, [ouvert]);

  useEffect(() => {
    const echap = (e) => e.key === "Escape" && setOuvert(false);
    window.addEventListener("keydown", echap);
    return () => window.removeEventListener("keydown", echap);
  }, []);

  return (
    <>
      <button
        className={`bulle-declencheur ${ouvert ? "actif" : ""}`}
        onClick={() => setOuvert((o) => !o)}
        aria-expanded={ouvert}
        aria-label={ouvert ? "Fermer l'assistant" : "Ouvrir l'assistant"}
        title="Assistant (Echap pour fermer)"
      >
        <span aria-hidden="true">{ouvert ? "×" : "✦"}</span>
        {!ouvert && <span className="etiquette">Assistant</span>}
      </button>

      {dejaOuvert && (
        <section
          className={`bulle-panneau ${ouvert ? "" : "masque"}`}
          role="dialog"
          aria-label="Assistant administrateur"
        >
          <header>
            <div>
              <strong>Assistant</strong>
              <div className="petit muet">Interrogez la base en langage naturel</div>
            </div>
            <div className="actions">
              <Link className="petit" to="/assistant" onClick={() => setOuvert(false)}>
                Plein écran
              </Link>
              <button className="fermer" onClick={() => setOuvert(false)} aria-label="Fermer">
                ×
              </button>
            </div>
          </header>
          <div className="corps">
            <Discussion compact />
          </div>
        </section>
      )}
    </>
  );
}
