import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./hooks/useAuth";
import { AuthenticatedShell } from "./pages/AuthenticatedShell";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { CandidateDetailPage } from "./pages/CandidateDetailPage";
import { CandidateListPage } from "./pages/CandidateListPage";
import { InterviewerQueuePage } from "./pages/InterviewerQueuePage";
import { InterviewerScorecardPage } from "./pages/InterviewerScorecardPage";
import { PositionDetailPage } from "./pages/PositionDetailPage";
import { PositionListPage } from "./pages/PositionListPage";
import { UserListPage } from "./pages/UserListPage";

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
            <Route path="/users" element={<UserListPage />} />
            <Route path="/candidates" element={<CandidateListPage />} />
            <Route path="/candidates/:candidateId" element={<CandidateDetailPage />} />
            <Route path="/my-candidates" element={<InterviewerQueuePage />} />
            <Route path="/my-candidates/:candidateId" element={<InterviewerScorecardPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
