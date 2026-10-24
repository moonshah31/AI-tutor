import { useEffect, useState } from "react";
import {
  Link,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";

import { ProtectedRoute } from "./auth/ProtectedRoute";
import {
  DashboardPage,
  LoginPage,
  RegisterPage,
  TutorPage,
} from "./pages";

type ApiHealth = {
  status: "ok" | "degraded";
  database: "connected" | "unavailable";
};

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />

      <Route path="/login" element={<LoginPage />} />

      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route
          path="/dashboard"
          element={<DashboardPage />}
        />

        <Route
          path="/tutor"
          element={<TutorPage />}
        />

        <Route
          path="/tutor/:conversationId"
          element={<TutorPage />}
        />
      </Route>

      <Route
        path="*"
        element={<LandingPage />}
      />
    </Routes>
  );
}

function LandingPage() {
  const [health, setHealth] =
    useState<ApiHealth | null>(null);

  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function checkHealth() {
      try {
        const response = await fetch(
          "/api/health",
          {
            signal: controller.signal,
          },
        );

        if (!response.ok) {
          throw new Error("Health check failed");
        }

        setHealth(
          (await response.json()) as ApiHealth,
        );
      } catch {
        if (!controller.signal.aborted) {
          setError(true);
        }
      }
    }

    void checkHealth();

    return () => controller.abort();
  }, []);

  const navigate = useNavigate();

  return (
    <main className="page-shell">
      <section
        className="hero"
        aria-labelledby="page-title"
      >
        <p className="eyebrow">AI Tutor</p>

        <h1 id="page-title">
          Learn the why, not just the answer.
        </h1>

        <p className="lead">
          A personal academic tutor that will
          explain concepts, guide problem solving,
          and adapt to how you learn.
        </p>

        <button
          type="button"
          onClick={() => navigate("/register")}
        >
          Start Learning
        </button>

        <p>
          <Link to="/login">
            Already have an account? Log in
          </Link>
        </p>
      </section>

      <section
        className="foundation"
        aria-label="Service status"
      >
        <h2>Foundation status</h2>

        {health ? (
          <p className="success">
            API is ready. MongoDB is{" "}
            {health.database}.
          </p>
        ) : error ? (
          <p className="warning">
            The API is not available yet. Start the
            backend and MongoDB to continue.
          </p>
        ) : (
          <p>Checking the API...</p>
        )}
      </section>
    </main>
  );
}