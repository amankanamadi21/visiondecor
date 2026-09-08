import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { DashboardPage } from "./pages/DashboardPage";
import { NewDesignPage } from "./pages/NewDesignPage";
import { DesignDetailPage } from "./pages/DesignDetailPage";
import { CompareDesignsPage } from "./pages/CompareDesignsPage";
import "./App.css";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/designs/new"
            element={
              <ProtectedRoute>
                <NewDesignPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/designs/:id"
            element={
              <ProtectedRoute>
                <DesignDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/designs/:id/compare"
            element={
              <ProtectedRoute>
                <CompareDesignsPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
