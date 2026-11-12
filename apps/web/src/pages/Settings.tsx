import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { Check, Copy, KeyRound, ShieldCheck, Zap } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, API_URL, type Workspace } from "../api";
import { useInvalidate } from "../hooks";
import { Button, Card, cx, PageHeader, useToast } from "../ui";

function CopyField({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2">
      <code className="min-w-0 flex-1 truncate text-sm text-slate-100">{value}</code>
      <button onClick={copy} aria-label={`Copier ${label}`} className="rounded p-1 text-slate-300 hover:bg-white/10">
        {copied ? <Check className="size-4 text-emerald-400" /> : <Copy className="size-4" />}
      </button>
    </div>
  );
}

export default function SettingsPage({ workspace }: { workspace: Workspace }) {
  const keys = useQuery({ queryKey: ["api-keys"], queryFn: api.apiKeys });
  const invalidate = useInvalidate();
  const toast = useToast();
  const [name, setName] = useState("");
  const [created, setCreated] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mcpUrl = `${API_URL || window.location.origin}/mcp/`;

  const setMode = async (llm_publish_mode: Workspace["llm_publish_mode"]) => {
    try {
      await api.updateWorkspace({ llm_publish_mode });
      await invalidate("me");
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  const createKey = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const key = await api.createApiKey(name.trim());
      setCreated(key.key ?? null);
      setName("");
      await invalidate("api-keys");
    } catch (err) {
      toast((err as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (id: string, keyName: string) => {
    if (!window.confirm(`Révoquer la clé « ${keyName} » ? Les assistants qui l'utilisent perdront l'accès.`)) return;
    await api.revokeApiKey(id);
    await invalidate("api-keys");
  };

  const modes = [
    { value: "draft" as const, icon: ShieldCheck, title: "Validation requise", text: "L'assistant prépare les posts, tu les approuves avant qu'ils partent." },
    { value: "direct" as const, icon: Zap, title: "Publication directe", text: "L'assistant peut planifier et publier sans attendre ta validation." },
  ];

  return (
    <>
      <PageHeader title="Réglages" subtitle="Pilote Cadence depuis Claude ou tout assistant compatible MCP." />
      <div className="space-y-6">
        <Card className="p-6">
          <h2 className="font-semibold">Autonomie de l'assistant IA</h2>
          <p className="mt-1 text-sm text-slate-500">Ce que l'assistant a le droit de faire avec tes comptes.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {modes.map(({ value, icon: Icon, title, text }) => (
              <button
                key={value}
                aria-pressed={workspace.llm_publish_mode === value}
                onClick={() => setMode(value)}
                className={cx(
                  "rounded-xl p-4 text-left ring-1 transition",
                  workspace.llm_publish_mode === value ? "bg-brand-50 ring-2 ring-brand-500" : "ring-slate-200 hover:bg-slate-50",
                )}
              >
                <Icon className="size-5 text-brand-600" />
                <p className="mt-2 font-medium">{title}</p>
                <p className="mt-0.5 text-sm text-slate-500">{text}</p>
              </button>
            ))}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-semibold">Connexion MCP</h2>
          <p className="mb-3 mt-1 text-sm text-slate-500">
            Ajoute cette adresse comme serveur MCP dans ton assistant, avec une clé API dans l'en-tête <code className="rounded bg-slate-100 px-1">Authorization: Bearer</code>.
          </p>
          <CopyField value={mcpUrl} label="l'adresse du serveur MCP" />

          <h3 className="mt-6 flex items-center gap-2 text-sm font-medium"><KeyRound className="size-4" /> Clés API</h3>
          {created && (
            <div className="mt-3 rounded-xl bg-emerald-50 p-4 ring-1 ring-emerald-200">
              <p className="mb-2 text-sm font-medium text-emerald-800">Copie cette clé maintenant : elle ne sera plus jamais affichée.</p>
              <CopyField value={created} label="la clé API" />
            </div>
          )}
          <form onSubmit={createKey} className="mt-3 flex gap-2">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={120}
              aria-label="Nom de la clé"
              placeholder="Nom de la clé, ex. Claude Desktop"
              className="min-w-0 flex-1 rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-brand-500 focus:outline-none"
            />
            <Button type="submit" variant="primary" loading={busy}>Créer une clé</Button>
          </form>
          {keys.data && keys.data.length > 0 && (
            <ul className="mt-4 divide-y divide-slate-100 rounded-xl ring-1 ring-slate-200">
              {keys.data.map((k) => (
                <li key={k.id} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{k.name}</p>
                    <p className="text-xs text-slate-500">
                      <code>{k.prefix}…</code> · {k.last_used_at ? `utilisée le ${format(new Date(k.last_used_at), "d MMM yyyy 'à' HH:mm", { locale: fr })}` : "jamais utilisée"}
                    </p>
                  </div>
                  <Button variant="danger" size="sm" onClick={() => revoke(k.id, k.name)}>Révoquer</Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
