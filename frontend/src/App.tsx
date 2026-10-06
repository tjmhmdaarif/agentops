import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { AuthProvider } from "./hooks/auth";
import { AppProvider } from "./hooks/store";
import { SceneProvider } from "./three/sceneStore";
import AnalyticsPage from "./pages/AnalyticsPage";
import DashboardPage from "./pages/DashboardPage";
import DeviceDetailPage from "./pages/DeviceDetailPage";
import FleetPage from "./pages/FleetPage";
import IncidentDetailPage from "./pages/IncidentDetailPage";
import IncidentsPage from "./pages/IncidentsPage";
import SettingsPage from "./pages/SettingsPage";
import SimulationPage from "./pages/SimulationPage";

// three.js is heavy — split it out so the app shell and the scene load in parallel.
const SpaceScene = lazy(() => import("./three/SpaceScene"));

export default function App() {
  return (
    <SceneProvider>
      {/* Cinematic universe: pre-login hero globe → dissolves into the
          application's permanent deep-space background */}
      <Suspense fallback={null}>
        <SpaceScene quality="auto" interactive />
      </Suspense>
      <AuthProvider>
        <AppProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<Layout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/fleet" element={<FleetPage />} />
                <Route path="/devices/:id" element={<DeviceDetailPage />} />
                <Route path="/incidents" element={<IncidentsPage />} />
                <Route path="/incidents/:id" element={<IncidentDetailPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/simulation" element={<SimulationPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="*" element={<DashboardPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AppProvider>
      </AuthProvider>
    </SceneProvider>
  );
}
