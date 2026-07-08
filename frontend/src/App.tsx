import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { RequireAuth } from './auth/RequireAuth'
import { LoginPage } from './pages/Login'
import { ExperimentsListPage } from './pages/ExperimentsList'
import { NewExperimentStubPage } from './pages/NewExperimentStub'
import { ExperimentDetailStubPage } from './pages/ExperimentDetailStub'
import { DatasetsPage } from './pages/Datasets'
import { ValidationStubPage } from './pages/ValidationStub'
import { AdminPage } from './pages/Admin'
import { AuditPage } from './pages/Audit'
import { ProfilePage } from './pages/Profile'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/experiments" replace />} />
        <Route path="/experiments" element={<ExperimentsListPage />} />
        <Route path="/experiments/new" element={<NewExperimentStubPage />} />
        <Route path="/experiments/:name" element={<ExperimentDetailStubPage />} />
        <Route path="/datasets" element={<DatasetsPage />} />
        <Route path="/validation" element={<ValidationStubPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route
          path="/admin"
          element={
            <RequireAuth minRole="admin">
              <AdminPage />
            </RequireAuth>
          }
        />
        <Route
          path="/audit"
          element={
            <RequireAuth minRole="admin">
              <AuditPage />
            </RequireAuth>
          }
        />
      </Route>
    </Routes>
  )
}

export default App
