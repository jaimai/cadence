import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { Check, Clock, ExternalLink, ImagePlus, RotateCcw, Send, Sparkles, Trash2, TriangleAlert, Upload, X } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, uploadFile, type Media, type Post } from "./api";
import { needsApproval, useAccounts, useInvalidate, useMedia, type ComposerRequest } from "./hooks";
import { AccountAvatar, Button, cx, ErrorNote, Modal, StatusBadge, useToast } from "./ui";

type Mode = "now" | "later" | "draft";

/** Mirrors the server-side rules so problems show while writing, not on submit. */
function networkIssues(platforms: Set<string>, caption: string, media: Media[]): string[] {
  const issues: string[] = [];
  const images = media.filter((m) => m.kind === "image");
  const videos = media.filter((m) => m.kind === "video");
  if (platforms.has("instagram")) {
    if (media.length === 0) issues.push("Instagram demande au moins une image ou une vidéo.");
    if (images.some((m) => m.content_type !== "image/jpeg")) issues.push("Instagram n'accepte que les images JPG.");
    if (media.length > 10) issues.push("Instagram accepte 10 médias au maximum.");
    if (caption.length > 2200) issues.push("Instagram limite le texte à 2 200 caractères.");
  }
  if (platforms.has("tiktok")) {
    if (media.length === 0) issues.push("TikTok demande une vidéo ou des photos.");
    if (images.length > 0 && videos.length > 0) issues.push("TikTok ne mélange pas photos et vidéo.");
    if (videos.length > 1) issues.push("TikTok accepte une seule vidéo par post.");
    if (images.some((m) => m.content_type === "image/png")) issues.push("TikTok n'accepte que les photos JPG ou WebP.");
    if (videos.length > 0 && caption.length > 2200) issues.push("TikTok limite le texte d'une vidéo à 2 200 caractères.");
  }
  if (platforms.has("linkedin")) {
    if (images.length > 0 && videos.length > 0) issues.push("LinkedIn ne mélange pas photos et vidéo.");
    if (videos.length > 1) issues.push("LinkedIn accepte une seule vidéo par post.");
    if (images.some((m) => m.content_type === "image/webp")) issues.push("LinkedIn n'accepte que les images JPG ou PNG.");
    if (videos.some((m) => m.content_type !== "video/mp4")) issues.push("LinkedIn n'accepte que les vidéos MP4.");
    if (caption.length > 3000) issues.push("LinkedIn limite le texte à 3 000 caractères.");
  }
  if (platforms.has("x")) {
    if (caption.length > 280) issues.push(`X limite le texte à 280 caractères (${caption.length} ici).`);
    if (images.length > 4) issues.push("X accepte 4 images au maximum.");
    if (images.length > 0 && videos.length > 0) issues.push("X ne mélange pas photos et vidéo.");
    if (videos.length > 1) issues.push("X accepte une seule vidéo par post.");
  }
  if (platforms.has("facebook")) {
    if (images.length > 0 && videos.length > 0) issues.push("Facebook ne mélange pas photos et vidéo.");
    if (videos.length > 1) issues.push("Facebook accepte une seule vidéo par post.");
  }
  return issues;
}

const toLocalInput = (d: Date) => format(d, "yyyy-MM-dd'T'HH:mm");

function defaultDate(request: ComposerRequest): Date {
  if (request.post?.scheduled_at) return new Date(request.post.scheduled_at);
  const d = request.date ? new Date(request.date) : new Date(Date.now() + 3600_000);
  if (request.date) d.setHours(9, 0, 0, 0);
  return d;
}

export default function Composer({ request, onClose }: { request: ComposerRequest; onClose: () => void }) {
  const { post } = request;
  if (post && post.status !== "draft" && post.status !== "scheduled") return <PostDetails post={post} onClose={onClose} />;
  return <Editor request={request} onClose={onClose} />;
}

function Editor({ request, onClose }: { request: ComposerRequest; onClose: () => void }) {
  const { post } = request;
  const accounts = useAccounts();
  const invalidate = useInvalidate();
  const toast = useToast();

  const [caption, setCaption] = useState(post?.caption ?? "");
  const [accountIds, setAccountIds] = useState<string[]>(post?.targets.map((t) => t.account.id) ?? []);
  const [media, setMedia] = useState<Media[]>(post?.media ?? []);
  const [mode, setMode] = useState<Mode>(post?.scheduled_at || request.date ? "later" : "now");
  const [when, setWhen] = useState(toLocalInput(defaultDate(request)));
  const [picking, setPicking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const toggleAccount = (id: string) =>
    setAccountIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));

  const addFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
        const uploaded = await uploadFile(file);
        setMedia((m) => [...m, uploaded]);
      }
      await invalidate("media");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const save = async () => {
    setError("");
    if (mode !== "draft" && accountIds.length === 0) return setError("Choisis au moins un compte.");
    if (mode !== "draft" && !caption.trim() && media.length === 0) return setError("Écris un texte ou ajoute un média.");
    const date = new Date(when);
    if (mode === "later" && Number.isNaN(date.getTime())) return setError("Choisis une date et une heure.");
    if (mode === "later" && date.getTime() < Date.now()) return setError("Cette date est déjà passée.");

    const content = { caption, account_ids: accountIds, media_ids: media.map((m) => m.id) };
    const scheduledAt = mode === "later" ? date.toISOString() : null;
    setBusy(true);
    try {
      if (!post) {
        await api.createPost({ ...content, scheduled_at: scheduledAt, publish_now: mode === "now" });
      } else if (mode === "draft") {
        if (post.status === "scheduled") await api.unschedulePost(post.id);
        await api.updatePost(post.id, content);
      } else {
        await api.updatePost(post.id, content);
        await api.schedulePost(post.id, scheduledAt);
      }
      await invalidate("posts");
      toast(mode === "now" ? "Publication lancée." : mode === "later" ? "Post planifié." : "Brouillon enregistré.");
      onClose();
    } catch (e) {
      setError((e as Error).message);
      await invalidate("posts");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!post || !window.confirm("Supprimer ce post ?")) return;
    try {
      await api.deletePost(post.id);
      await invalidate("posts");
      toast("Post supprimé.");
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const selected = accounts.data?.filter((a) => accountIds.includes(a.id)) ?? [];
  const issues = networkIssues(new Set(selected.map((a) => a.platform)), caption, media);
  const submitLabel = mode === "now" ? "Publier maintenant" : mode === "later" ? "Planifier" : "Enregistrer le brouillon";

  return (
    <Modal title={post ? "Modifier le post" : "Nouveau post"} onClose={onClose} wide>
      <div className="grid gap-0 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-6 p-6">
          {post && needsApproval(post) && (
            <p className="flex items-start gap-2 rounded-lg bg-violet-50 px-3 py-2 text-sm text-violet-800">
              <Sparkles className="mt-0.5 size-4 shrink-0" />
              Proposé par ton assistant IA. Relis-le, puis planifie-le ou publie-le pour l'approuver.
            </p>
          )}

          <section>
            <h3 className="mb-2 text-sm font-medium">Publier sur</h3>
            {accounts.data?.length === 0 ? (
              <p className="rounded-lg bg-slate-50 px-3 py-3 text-sm text-slate-600">
                Aucun compte connecté.{" "}
                <Link to="/accounts" onClick={onClose} className="font-medium text-brand-600 hover:underline">
                  Connecter un compte
                </Link>
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {accounts.data?.map((a) => {
                  const on = accountIds.includes(a.id);
                  return (
                    <button
                      key={a.id}
                      aria-pressed={on}
                      onClick={() => toggleAccount(a.id)}
                      className={cx(
                        "flex items-center gap-2 rounded-full py-1 pl-1 pr-3 text-sm ring-1 transition",
                        on ? "bg-brand-50 text-brand-700 ring-brand-500" : "bg-white text-slate-600 ring-slate-200 hover:bg-slate-50",
                      )}
                    >
                      <AccountAvatar account={a} size="size-7" />
                      {a.display_name}
                      {on && <Check className="size-3.5" />}
                    </button>
                  );
                })}
              </div>
            )}
          </section>

          <section>
            <label htmlFor="caption" className="mb-2 block text-sm font-medium">Texte</label>
            <textarea
              id="caption"
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={7}
              placeholder="Qu'est-ce que tu veux partager ?"
              className="w-full resize-y rounded-xl border-0 px-4 py-3 text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-brand-500 focus:outline-none"
            />
            <p className="mt-1 text-right text-xs text-slate-400">{caption.length} caractères</p>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-medium">Médias</h3>
            <div className="flex flex-wrap gap-2">
              {media.map((m) => (
                <div key={m.id} className="group relative size-20 overflow-hidden rounded-lg bg-slate-100 ring-1 ring-slate-200">
                  <MediaThumb media={m} />
                  <button
                    aria-label={`Retirer ${m.filename}`}
                    onClick={() => setMedia((list) => list.filter((x) => x.id !== m.id))}
                    className="absolute right-1 top-1 rounded-full bg-slate-900/70 p-0.5 text-white"
                  >
                    <X className="size-3.5" />
                  </button>
                </div>
              ))}
              <input ref={fileInput} type="file" multiple hidden accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime" onChange={(e) => addFiles(e.target.files)} />
              <Button onClick={() => fileInput.current?.click()} loading={uploading} className="h-20">
                {!uploading && <Upload className="size-4" />} Importer
              </Button>
              <Button onClick={() => setPicking(true)} className="h-20">
                <ImagePlus className="size-4" /> Médiathèque
              </Button>
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-medium">Quand</h3>
            <div className="grid grid-cols-3 gap-2">
              {([["now", "Maintenant", Send], ["later", "Planifier", Clock], ["draft", "Brouillon", null]] as const).map(([value, label, Icon]) => (
                <button
                  key={value}
                  aria-pressed={mode === value}
                  onClick={() => setMode(value)}
                  className={cx(
                    "flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ring-1 transition",
                    mode === value ? "bg-brand-50 text-brand-700 ring-brand-500" : "text-slate-600 ring-slate-200 hover:bg-slate-50",
                  )}
                >
                  {Icon && <Icon className="size-4" />} {label}
                </button>
              ))}
            </div>
            {mode === "later" && (
              <input
                type="datetime-local"
                aria-label="Date et heure de publication"
                value={when}
                min={toLocalInput(new Date())}
                onChange={(e) => setWhen(e.target.value)}
                className="mt-3 w-full rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-brand-500 focus:outline-none sm:w-auto"
              />
            )}
          </section>

          {issues.length > 0 && (
            <ul className="space-y-1 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {issues.map((issue) => (
                <li key={issue} className="flex items-start gap-2">
                  <TriangleAlert className="mt-0.5 size-4 shrink-0" /> {issue}
                </li>
              ))}
            </ul>
          )}
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>

        <aside className="border-t border-slate-100 bg-slate-50 p-6 lg:rounded-br-2xl lg:border-l lg:border-t-0">
          <h3 className="mb-3 text-sm font-medium text-slate-500">Aperçu</h3>
          <Preview caption={caption} media={media} name={selected[0]?.display_name} account={selected[0]} />
          {selected.length > 1 && <p className="mt-3 text-xs text-slate-500">Le même contenu partira sur {selected.length} comptes.</p>}
        </aside>
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-6 py-4">
        {post ? (
          <Button variant="danger" onClick={remove}>
            <Trash2 className="size-4" /> Supprimer
          </Button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onClose}>Annuler</Button>
          <Button variant="primary" onClick={save} loading={busy} disabled={uploading}>{submitLabel}</Button>
        </div>
      </div>
      {picking && (
        <MediaPicker
          exclude={media.map((m) => m.id)}
          onClose={() => setPicking(false)}
          onPick={(m) => {
            setMedia((list) => [...list, m]);
            setPicking(false);
          }}
        />
      )}
    </Modal>
  );
}

export function MediaThumb({ media }: { media: Media }) {
  return media.kind === "video" ? (
    <video src={media.url} muted preload="metadata" className="size-full object-cover" />
  ) : (
    <img src={media.url} alt={media.filename} loading="lazy" className="size-full object-cover" />
  );
}

function Preview({ caption, media, name, account }: { caption: string; media: Media[]; name?: string; account?: Parameters<typeof AccountAvatar>[0]["account"] }) {
  return (
    <div className="overflow-hidden rounded-xl bg-white ring-1 ring-slate-200">
      <div className="flex items-center gap-2.5 p-3">
        {account ? <AccountAvatar account={account} /> : <span className="size-9 rounded-full bg-slate-200" />}
        <div>
          <p className="text-sm font-semibold">{name ?? "Ton compte"}</p>
          <p className="text-xs text-slate-400">À l'instant</p>
        </div>
      </div>
      {caption ? (
        <p className="whitespace-pre-wrap break-words px-3 pb-3 text-sm">{caption}</p>
      ) : (
        <p className="px-3 pb-3 text-sm text-slate-400">Ton texte apparaîtra ici.</p>
      )}
      {media.length > 0 && (
        <div className={cx("grid gap-0.5", media.length > 1 && "grid-cols-2")}>
          {media.slice(0, 4).map((m, i) => (
            <div key={m.id} className={cx("relative bg-slate-100", media.length === 1 ? "aspect-[4/3]" : "aspect-square")}>
              <MediaThumb media={m} />
              {i === 3 && media.length > 4 && (
                <span className="absolute inset-0 flex items-center justify-center bg-slate-900/50 text-xl font-semibold text-white">+{media.length - 4}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MediaPicker({ exclude, onPick, onClose }: { exclude: string[]; onPick: (m: Media) => void; onClose: () => void }) {
  const media = useMedia();
  const available = media.data?.filter((m) => !exclude.includes(m.id)) ?? [];
  return (
    <Modal title="Choisir dans la médiathèque" onClose={onClose}>
      <div className="max-h-[60vh] overflow-y-auto p-6">
        {available.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">{media.isPending ? "Chargement…" : "Aucun autre média disponible."}</p>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {available.map((m) => (
              <button key={m.id} onClick={() => onPick(m)} aria-label={m.filename} className="aspect-square overflow-hidden rounded-lg bg-slate-100 ring-1 ring-slate-200 hover:ring-2 hover:ring-brand-500">
                <MediaThumb media={m} />
              </button>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}

function PostDetails({ post, onClose }: { post: Post; onClose: () => void }) {
  const invalidate = useInvalidate();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const canRetry = post.status === "failed" || post.status === "partial";

  const run = async (action: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await action();
      await invalidate("posts");
      toast(message);
      onClose();
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Détail du post" onClose={onClose}>
      <div className="space-y-5 p-6">
        <div className="flex items-center justify-between">
          <StatusBadge status={post.status} />
          {post.scheduled_at && <span className="text-sm text-slate-500">{format(new Date(post.scheduled_at), "d MMMM yyyy 'à' HH:mm", { locale: fr })}</span>}
        </div>
        {post.caption && <p className="whitespace-pre-wrap break-words text-sm">{post.caption}</p>}
        {post.media.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {post.media.map((m) => (
              <div key={m.id} className="size-20 overflow-hidden rounded-lg bg-slate-100"><MediaThumb media={m} /></div>
            ))}
          </div>
        )}
        <ul className="divide-y divide-slate-100 rounded-xl ring-1 ring-slate-200">
          {post.targets.map((t) => (
            <li key={t.id} className="flex items-start gap-3 p-3">
              <AccountAvatar account={t.account} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{t.account.display_name}</p>
                {t.status === "published" && <p className="text-xs text-emerald-600">Publié</p>}
                {t.status === "publishing" && <p className="text-xs text-amber-600">Publication en cours…</p>}
                {t.status === "pending" && <p className="text-xs text-slate-500">{t.error ? `Nouvel essai prévu. ${t.error}` : "En attente"}</p>}
                {t.status === "failed" && <p className="text-xs text-red-600">{t.error ?? "Échec de la publication."}</p>}
              </div>
              {t.permalink && (
                <a href={t.permalink} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-sm text-brand-600 hover:underline">
                  Voir <ExternalLink className="size-3.5" />
                </a>
              )}
            </li>
          ))}
        </ul>
      </div>
      <div className="flex justify-between border-t border-slate-100 px-6 py-4">
        <Button
          variant="danger"
          disabled={busy || post.status === "publishing"}
          onClick={() => window.confirm("Retirer ce post de Cadence ? Il restera en ligne sur les réseaux où il est déjà publié.") && run(() => api.deletePost(post.id), "Post retiré.")}
        >
          <Trash2 className="size-4" /> Retirer
        </Button>
        {canRetry && (
          <Button variant="primary" loading={busy} onClick={() => run(() => api.retryPost(post.id), "Nouvelle tentative lancée.")}>
            <RotateCcw className="size-4" /> Relancer les échecs
          </Button>
        )}
      </div>
    </Modal>
  );
}
