import { createBrowserRouter, Link } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Empty } from "./components/ui";
import { AnalysisPage } from "./pages/AnalysisPage";
import { HomePage } from "./pages/HomePage";
import { MatchPage } from "./pages/MatchPage";
import { PlayerPage } from "./pages/PlayerPage";
import { TeamFormPage } from "./pages/TeamFormPage";
import { TeamPage } from "./pages/TeamPage";
import { TeamsPage } from "./pages/TeamsPage";

const NotFound = () => (
  <Empty>
    <h1>404</h1>
    <p>Diese Seite gibt es nicht.</p>
    <Link className="btn" to="/">Zur Startseite</Link>
  </Empty>
);

export const routes = [
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "player/:name/:tag", element: <PlayerPage /> },
      { path: "analysis", element: <AnalysisPage /> },
      { path: "match/:matchId", element: <MatchPage /> },
      { path: "teams", element: <TeamsPage /> },
      { path: "teams/new", element: <TeamFormPage /> },
      { path: "teams/:teamId", element: <TeamPage /> },
      { path: "teams/:teamId/edit", element: <TeamFormPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
