import { useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Image, LayoutList, LogOut, Plus, Settings, Users } from "lucide-react";
import { useCallback, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, ApiError } from "./api";
import Composer from "./Composer";
import { ComposerContext, useMe, type ComposerRequest } from "./hooks";
import AccountsPage from "./pages/Accounts";
import AuthPage from "./pages/Auth";
import CalendarPage from "./pages/Calendar";
import LandingPage from "./pages/Landing";
import MediaPage from "./pages/Media";
import PostsPage from "./pages/Posts";
import SettingsPage from "./pages/Settings";
import { Button, cx, ErrorNote, Spinner } from "./ui";

const NAV = [
  { to: "/", label: "Calendrier", icon: CalendarDays },
  { to: "/posts", label: "Posts", icon: LayoutList },
  { to: "/media", label: "Médias", icon: Image },
  { to: "/accounts", label: "Comptes", icon: Users },
  { to: "/settings", label: "Réglages", icon: Settings },
];

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <img src="/favicon.svg" alt="" className="size-8" />
      <span className="text-lg font-semibold tracking-tight">Cadence</span>
    </div>
  );
}

export default function App() {
  const me = useMe();
  const client = useQueryClient();
  const navigate = useNavigate();
  const [composer, setComposer] = useState<ComposerRequest | null>(null);
  const openComposer = useCallback((request?: ComposerRequest) => setComposer(request ?? {}), []);

  if (me.isPending) return <Spinner />;
  if (me.isError) {
    if (me.error instanceof ApiError && me.error.status === 401) {
      return (
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/signup" element={<AuthPage mode="signup" />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      );
    }
    return (
      <div className="mx-auto mt-24 max-w-sm space-y-3 text-center">
        <ErrorNote>{me.error.message}</ErrorNote>
        <Button onClick={() => me.refetch()}>Réessayer</Button>
      </div>
    );
  }

  const logout = async () => {
    await api.logout();
    client.clear();
    navigate("/");
    await me.refetch();
  };

  return (
    <ComposerContext.Provider value={openComposer}>
      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="flex shrink-0 flex-col gap-1 border-b border-slate-200 bg-white p-3 md:sticky md:top-0 md:h-screen md:w-60 md:border-b-0 md:border-r md:p-4">
          <div className="flex items-center justify-between px-2 py-2 md:mb-4">
            <Logo />
            <div className="flex items-center gap-1 md:hidden">
              <Button variant="primary" size="sm" onClick={() => openComposer()}>
                <Plus className="size-4" /> Post
              </Button>
              <Button variant="ghost" size="sm" aria-label="Se déconnecter" onClick={logout}>
                <LogOut className="size-4" />
              </Button>
            </div>
          </div>
          <div className="mb-3 hidden md:block">
            <Button variant="primary" className="w-full" onClick={() => openComposer()}>
              <Plus className="size-4" /> Nouveau post
            </Button>
          </div>
          <nav className="flex gap-1 overflow-x-auto md:flex-col">
            {NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  cx(
                    "flex items-center gap-3 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition",
                    isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100",
                  )
                }
              >
                <Icon className="size-4.5" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-auto hidden border-t border-slate-100 pt-3 md:block">
            <p className="truncate px-3 text-xs text-slate-500" title={me.data.email}>{me.data.email}</p>
            <button onClick={logout} className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100">
              <LogOut className="size-4" /> Se déconnecter
            </button>
          </div>
        </aside>
        <main className="min-w-0 flex-1 p-4 md:p-8">
          <div className="mx-auto max-w-6xl">
            <Routes>
              <Route path="/" element={<CalendarPage />} />
              <Route path="/posts" element={<PostsPage />} />
              <Route path="/media" element={<MediaPage />} />
              <Route path="/accounts" element={<AccountsPage />} />
              <Route path="/settings" element={<SettingsPage workspace={me.data.workspace} />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </main>
      </div>
      {composer && <Composer request={composer} onClose={() => setComposer(null)} />}
    </ComposerContext.Provider>
  );
}
