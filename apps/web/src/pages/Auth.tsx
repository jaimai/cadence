import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Logo } from "../App";
import { Button, Card, ErrorNote } from "../ui";

export default function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const client = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await (mode === "login" ? api.login(email, password) : api.signup(email, password));
      await client.invalidateQueries({ queryKey: ["me"] });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const input = "mt-1 w-full rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-brand-500 focus:outline-none";
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-slate-50 p-4">
      <Card className="w-full max-w-sm p-8">
        <Link to="/" className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
          <ArrowLeft className="size-4" /> Accueil
        </Link>
        <Logo />
        <h1 className="mt-6 text-xl font-semibold">{mode === "login" ? "Content de te revoir" : "Créer ton espace"}</h1>
        <p className="mt-1 text-sm text-slate-500">Planifie et publie sur tous tes réseaux depuis un seul endroit.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block text-sm font-medium">
            E-mail
            <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={input} />
          </label>
          <label className="block text-sm font-medium">
            Mot de passe
            <input
              type="password"
              required
              minLength={8}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={input}
            />
            {mode === "signup" && <span className="mt-1 block text-xs font-normal text-slate-500">8 caractères minimum.</span>}
          </label>
          {error && <ErrorNote>{error}</ErrorNote>}
          <Button type="submit" variant="primary" className="w-full" loading={busy}>
            {mode === "login" ? "Se connecter" : "Créer mon compte"}
          </Button>
        </form>
        <Link
          to={mode === "login" ? "/signup" : "/login"}
          onClick={() => setError("")}
          className="mt-4 block text-center text-sm text-brand-600 hover:underline"
        >
          {mode === "login" ? "Pas encore de compte ? Créer un compte" : "Déjà un compte ? Se connecter"}
        </Link>
      </Card>
    </div>
  );
}
