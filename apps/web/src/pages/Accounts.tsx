import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Monitor, RefreshCw, Smartphone, Users } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Account, type Platform } from "../api";
import { useAccounts, useInvalidate } from "../hooks";
import { AccountAvatar, Button, Card, Empty, ErrorNote, Modal, PageHeader, PlatformIcon, Spinner, useToast } from "../ui";

const HINTS: Record<string, string> = {
  facebook: "Pages Facebook que tu administres.",
  instagram: "Comptes professionnels ou créateurs.",
  linkedin: "Profil personnel.",
  tiktok: "Autant de comptes que tu veux, un par un.",
  x: "Autant de comptes que tu veux, un par un.",
};

/**
 * Connect with a phone: scanning opens the network's own login there, where
 * switching between several accounts is easier than in a desktop browser.
 */
function ConnectModal({ platform, onClose }: { platform: Platform; onClose: () => void }) {
  const toast = useToast();
  const [redirecting, setRedirecting] = useState(false);
  const link = useQuery({
    queryKey: ["oauth-link", platform.platform],
    queryFn: () => api.oauthLink(platform.platform),
    staleTime: Infinity,
    gcTime: 0,
  });
  // While the QR code is on screen, watch for accounts connected from the phone.
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.accounts, refetchInterval: 3000 });
  const known = useRef<Set<string> | null>(null);
  const [added, setAdded] = useState<Account[]>([]);
  useEffect(() => {
    if (!accounts.data) return;
    if (known.current === null) {
      known.current = new Set(accounts.data.map((a) => a.id));
      return;
    }
    const fresh = accounts.data.filter((a) => !known.current!.has(a.id));
    if (fresh.length === 0) return;
    fresh.forEach((a) => known.current!.add(a.id));
    setAdded((list) => [...list, ...fresh]);
  }, [accounts.data]);

  const [expired, setExpired] = useState(false);
  useEffect(() => {
    if (!link.data) return;
    setExpired(false);
    const timer = setTimeout(() => setExpired(true), Math.max(0, new Date(link.data.expires_at).getTime() - Date.now()));
    return () => clearTimeout(timer);
  }, [link.data]);

  const here = async () => {
    setRedirecting(true);
    try {
      window.location.href = (await api.oauthStart(platform.platform)).url;
    } catch (e) {
      toast((e as Error).message, "error");
      setRedirecting(false);
    }
  };

  return (
    <Modal title={`Connecter ${platform.label}`} onClose={onClose}>
      <div className="space-y-5 p-6">
        <div className="flex items-start gap-3">
          <Smartphone className="mt-0.5 size-5 shrink-0 text-brand-600" />
          <p className="text-sm text-slate-600">
            Scanne ce code avec l'appareil photo de ton téléphone, puis autorise le compte de ton choix. Pour en ajouter un autre, change de compte sur {platform.label} et scanne à nouveau.
          </p>
        </div>

        <div className="flex justify-center">
          <div className="relative rounded-2xl bg-white p-4 ring-1 ring-slate-200">
            {link.data ? (
              <QRCodeSVG value={link.data.url} size={208} marginSize={0} className={expired ? "opacity-10" : undefined} title={`QR code de connexion ${platform.label}`} />
            ) : (
              <div className="flex size-52 items-center justify-center text-sm text-slate-400">{link.isError ? "" : "Préparation…"}</div>
            )}
            {expired && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
                <p className="text-sm font-medium">Code expiré</p>
                <Button size="sm" variant="primary" onClick={() => link.refetch()}><RefreshCw className="size-4" /> Nouveau code</Button>
              </div>
            )}
          </div>
        </div>

        {link.isError && <ErrorNote>{link.error.message}</ErrorNote>}
        {link.data && !link.data.reachable && (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
            L'API tourne en local : ton téléphone ne peut pas ouvrir ce lien. Le QR code fonctionnera une fois l'API en ligne.
          </p>
        )}

        {added.length > 0 ? (
          <ul className="space-y-2">
            {added.map((a) => (
              <li key={a.id} className="flex items-center gap-3 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                <AccountAvatar account={a} size="size-8" />
                <span><strong>{a.display_name}</strong> est connecté.</span>
              </li>
            ))}
          </ul>
        ) : (
          link.data && !expired && <p className="text-center text-xs text-slate-400" role="status">En attente de la connexion depuis ton téléphone…</p>
        )}
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-6 py-4">
        <Button variant="ghost" loading={redirecting} onClick={here}>
          {!redirecting && <Monitor className="size-4" />} Continuer sur cet appareil
        </Button>
        <Button variant={added.length > 0 ? "primary" : "secondary"} onClick={onClose}>{added.length > 0 ? "Terminé" : "Fermer"}</Button>
      </div>
    </Modal>
  );
}

export default function AccountsPage() {
  const accounts = useAccounts();
  const platforms = useQuery({ queryKey: ["platforms"], queryFn: api.platforms });
  const invalidate = useInvalidate();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [connecting, setConnecting] = useState<Platform | null>(null);

  // Result of the OAuth round-trip, passed back in the URL by the API.
  useEffect(() => {
    const connected = params.get("connected");
    const error = params.get("error");
    if (!connected && !error) return;
    if (connected) toast(`${connected} compte${Number(connected) > 1 ? "s" : ""} connecté${Number(connected) > 1 ? "s" : ""}.`);
    if (error) toast(error, "error");
    setParams({}, { replace: true });
  }, [params, setParams, toast]);

  const disconnect = async (id: string, name: string) => {
    if (!window.confirm(`Déconnecter ${name} ? Ses posts planifiés ne partiront plus.`)) return;
    try {
      await api.disconnect(id);
      await invalidate("accounts", "posts");
      toast("Compte déconnecté.");
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  return (
    <>
      <PageHeader title="Comptes" subtitle="Connecte les réseaux sur lesquels tu veux publier." />
      <div className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {platforms.data?.map((p) => (
          <Card key={p.platform} className="flex flex-col p-4">
            <PlatformIcon platform={p.platform} className="size-10 text-sm" />
            <p className="mt-3 font-medium">{p.label}</p>
            <p className="mb-4 mt-0.5 flex-1 text-sm text-slate-500">{HINTS[p.platform]}</p>
            {!p.available ? (
              <span className="self-start rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">Bientôt disponible</span>
            ) : !p.configured ? (
              <span className="text-xs text-amber-700">Identifiants de l'app {p.label} manquants côté serveur (voir README).</span>
            ) : (
              <Button variant="primary" size="sm" onClick={() => setConnecting(p)}>Connecter</Button>
            )}
          </Card>
        ))}
      </div>

      {connecting && (
        <ConnectModal
          platform={connecting}
          onClose={() => {
            setConnecting(null);
            invalidate("accounts");
          }}
        />
      )}

      <h2 className="mb-3 text-sm font-medium text-slate-500">Comptes connectés</h2>
      {accounts.isError && <ErrorNote>{accounts.error.message}</ErrorNote>}
      {accounts.isPending ? (
        <Spinner />
      ) : accounts.data?.length === 0 ? (
        <Empty icon={<Users className="size-5" />} title="Aucun compte connecté">Choisis un réseau ci-dessus pour commencer.</Empty>
      ) : (
        <Card className="divide-y divide-slate-100">
          {accounts.data?.map((a) => (
            <div key={a.id} className="flex items-center gap-3 p-4">
              <AccountAvatar account={a} size="size-10" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{a.display_name}</p>
                {a.status === "needs_reauth" ? (
                  <p className="flex items-center gap-1 text-sm text-amber-700"><AlertTriangle className="size-3.5" /> Accès expiré : reconnecte ce compte.</p>
                ) : (
                  <p className="text-sm text-slate-500">{a.username ? `@${a.username}` : "Connecté"}</p>
                )}
              </div>
              <Button variant="danger" size="sm" onClick={() => disconnect(a.id, a.display_name)}>Déconnecter</Button>
            </div>
          ))}
        </Card>
      )}
    </>
  );
}
