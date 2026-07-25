/**
 * Composants de data-visualisation (Recharts).
 * Palette : slots categoriels 1-3, validee CVD sur surface blanche.
 * Regles appliquees : un seul axe de valeur, marques fines, grille discrete,
 * infobulle au survol, legende des qu'il y a 2 series ou plus.
 */
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatCourt } from "./ui";

export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a"];
const GRILLE = "#e1e0d9";
const AXE = "#898781";
const ENCRE_2 = "#52514e";

const styleAxe = { fontSize: 11.5, fill: AXE };

function Infobulle({ active, payload, label, unite, formateur }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="infobulle">
      <div className="titre">{label}</div>
      {payload.map((p) => (
        <div className="ligne" key={p.dataKey}>
          <span className="pastille" style={{ background: p.color }} />
          <span>
            {p.name} : <strong>{formateur ? formateur(p.value) : p.value}</strong>
            {unite ? ` ${unite}` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

export function Legende({ items }) {
  if (items.length < 2) return null;
  return (
    <div className="legende">
      {items.map((item, i) => (
        <span className="item" key={item.nom}>
          <span className="pastille" style={{ background: item.couleur || SERIES[i] }} />
          {item.nom}
        </span>
      ))}
    </div>
  );
}

/** Barres verticales, une seule serie (magnitude par categorie). */
export function GrapheBarres({ donnees, cleX, cleY, nom, unite, formateur, hauteur = 300, couleur = SERIES[0] }) {
  return (
    <div className="zone-graphe" style={{ height: hauteur }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={donnees} margin={{ top: 8, right: 8, left: 4, bottom: 8 }}>
          <CartesianGrid stroke={GRILLE} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey={cleX}
            tick={styleAxe}
            axisLine={{ stroke: GRILLE }}
            tickLine={false}
            interval={0}
            angle={donnees.length > 5 ? -20 : 0}
            textAnchor={donnees.length > 5 ? "end" : "middle"}
            height={donnees.length > 5 ? 70 : 30}
          />
          <YAxis tick={styleAxe} axisLine={false} tickLine={false} tickFormatter={formatCourt} width={46} />
          <Tooltip
            cursor={{ fill: "rgba(42,120,214,0.07)" }}
            content={<Infobulle unite={unite} formateur={formateur} />}
          />
          <Bar dataKey={cleY} name={nom} fill={couleur} radius={[4, 4, 0, 0]} maxBarSize={44} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Barres horizontales avec seuil de couleur (ex : taux de couverture).
 * `seuilFaible` colore en orange les categories sous le seuil : la valeur reste
 * lisible en direct-label, la couleur n'est donc jamais le seul canal.
 */
export function GrapheBarresH({ donnees, cleX, cleY, nom, unite, hauteur, seuilFaible }) {
  return (
    <div className="zone-graphe" style={{ height: hauteur || Math.max(220, donnees.length * 34 + 40) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={donnees} layout="vertical" margin={{ top: 4, right: 40, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={GRILLE} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={styleAxe} axisLine={false} tickLine={false} tickFormatter={formatCourt} />
          <YAxis
            type="category"
            dataKey={cleX}
            tick={{ ...styleAxe, fill: ENCRE_2 }}
            axisLine={false}
            tickLine={false}
            width={168}
          />
          <Tooltip cursor={{ fill: "rgba(42,120,214,0.07)" }} content={<Infobulle unite={unite} />} />
          <Bar dataKey={cleY} name={nom} radius={[0, 4, 4, 0]} maxBarSize={20}>
            {donnees.map((d, i) => (
              <Cell
                key={i}
                fill={seuilFaible !== undefined && d[cleY] < seuilFaible ? SERIES[1] : SERIES[0]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Courbes d'evolution : une ou plusieurs series sur un seul axe de valeur. */
export function GrapheLignes({ donnees, cleX, series, unite, formateur, hauteur = 300 }) {
  return (
    <>
      <div className="zone-graphe" style={{ height: hauteur }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={donnees} margin={{ top: 10, right: 14, left: 4, bottom: 8 }}>
            <CartesianGrid stroke={GRILLE} strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey={cleX} tick={styleAxe} axisLine={{ stroke: GRILLE }} tickLine={false} />
            <YAxis tick={styleAxe} axisLine={false} tickLine={false} tickFormatter={formatCourt} width={46} />
            <Tooltip content={<Infobulle unite={unite} formateur={formateur} />} />
            {series.map((s, i) => (
              <Line
                key={s.cle}
                type="monotone"
                dataKey={s.cle}
                name={s.nom}
                stroke={s.couleur || SERIES[i]}
                strokeWidth={2}
                dot={{ r: 4, strokeWidth: 2, stroke: "#fff" }}
                activeDot={{ r: 6, strokeWidth: 2, stroke: "#fff" }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Legende items={series.map((s, i) => ({ nom: s.nom, couleur: s.couleur || SERIES[i] }))} />
    </>
  );
}
