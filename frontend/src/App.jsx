import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Chargement } from "./components/ui";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Activites from "./pages/Activites";
import Assistant from "./pages/Assistant";
import Budget from "./pages/Budget";
import Clusters from "./pages/Clusters";
import Connexion from "./pages/Connexion";
import Equite from "./pages/Equite";
import Personnel from "./pages/Personnel";
import Recommandations from "./pages/Recommandations";
import Statistiques from "./pages/Statistiques";
import TableauDeBord from "./pages/TableauDeBord";
import Transactions from "./pages/Transactions";

/** Toutes les pages de l'espace admin exigent une session valide. */
function RouteProtegee({ children }) {
  const { utilisateur, chargement } = useAuth();
  if (chargement) return <Chargement texte="Verification de la session…" />;
  return utilisateur ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Connexion />} />
          <Route
            element={
              <RouteProtegee>
                <Layout />
              </RouteProtegee>
            }
          >
            <Route path="/" element={<TableauDeBord />} />
            <Route path="/statistiques" element={<Statistiques />} />
            <Route path="/budget" element={<Budget />} />
            <Route path="/equite" element={<Equite />} />
            <Route path="/recommandations" element={<Recommandations />} />
            <Route path="/clusters" element={<Clusters />} />
            <Route path="/assistant" element={<Assistant />} />
            <Route path="/personnel" element={<Personnel />} />
            <Route path="/activites" element={<Activites />} />
            <Route path="/transactions" element={<Transactions />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
