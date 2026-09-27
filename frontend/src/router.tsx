import { createBrowserRouter, Link, Navigate } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Empty } from "./components/ui";
import { AccountPage } from "./pages/AccountPage";
import { AnalysisPage } from "./pages/AnalysisPage";
import { GroupPage } from "./pages/GroupPage";
import { GroupsPage } from "./pages/GroupsPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { MatchPage } from "./pages/MatchPage";
import { PlayerPage } from "./pages/PlayerPage";
import { ScoutReportPage } from "./pages/ScoutReportPage";
import { TeamFormPage } from "./pages/TeamFormPage";
import { TeamPage } from "./pages/TeamPage";
import { TeamsPage } from "./pages/TeamsPage";
import { UploaderPage } from "./pages/UploaderPage";

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
      { path: "groups", element: <GroupsPage /> },
      { path: "groups/:key", element: <GroupPage /> },
      { path: "scout", element: <Navigate to="/" replace /> },
      { path: "scout/:key", element: <ScoutReportPage /> },
      { path: "uploader", element: <UploaderPage /> },
      { path: "login", element: <LoginPage /> },
      { path: "account", element: <AccountPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
