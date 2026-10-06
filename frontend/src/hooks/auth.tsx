import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { authApi } from "../lib/api";
import { Spinner } from "../components/primitives";
import LandingPage from "../pages/LandingPage";

type AuthState =
  | { status: "loading" }
  | { status: "unauthenticated" }
  | { status: "authenticated"; username: string };

interface AuthContextValue {
  username: string;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  const check = () => {
    authApi
      .me()
      .then((r) => setState({ status: "authenticated", username: r.username }))
      .catch(() => setState({ status: "unauthenticated" }));
  };

  useEffect(() => {
    check();
    const onExpired = () => setState({ status: "unauthenticated" });
    window.addEventListener("agentops:unauthenticated", onExpired);
    return () => window.removeEventListener("agentops:unauthenticated", onExpired);
  }, []);

  if (state.status === "loading") {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-slate-500">
        <Spinner /> <span className="text-xs">Checking session…</span>
      </div>
    );
  }
  if (state.status === "unauthenticated") {
    return <LandingPage onLogin={check} />;
  }
  return (
    <AuthContext.Provider
      value={{
        username: state.username,
        logout: async () => {
          await authApi.logout().catch(() => undefined);
          setState({ status: "unauthenticated" });
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
