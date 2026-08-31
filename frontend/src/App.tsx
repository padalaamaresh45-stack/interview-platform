import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./hooks/useAuth";
import { AuthenticatedShell } from "./pages/AuthenticatedShell";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { PositionDetailPage } from "./pages/PositionDetailPage";
import { PositionListPage } from "./pages/PositionListPage";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<AuthenticatedShell />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/positions" element={<PositionListPage />} />
            <Route path="/positions/:positionId" element={<PositionDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
