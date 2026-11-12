import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { PenLine, Sparkles } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import type { Post } from "../api";
import { MediaThumb } from "../Composer";
import { needsApproval, useComposer, usePosts } from "../hooks";
import { AccountAvatar, Button, Card, cx, Empty, ErrorNote, PageHeader, Spinner, StatusBadge } from "../ui";

const TABS: { key: string; label: string; match: (p: Post) => boolean }[] = [
  { key: "all", label: "Tous", match: () => true },
  { key: "approval", label: "À valider", match: needsApproval },
  { key: "draft", label: "Brouillons", match: (p) => p.status === "draft" && !needsApproval(p) },
  { key: "scheduled", label: "Planifiés", match: (p) => p.status === "scheduled" || p.status === "publishing" },
  { key: "published", label: "Publiés", match: (p) => p.status === "published" },
  { key: "failed", label: "Échecs", match: (p) => p.status === "failed" || p.status === "partial" },
];

export default function PostsPage() {
  const posts = usePosts();
  const openComposer = useComposer();
  const [params, setParams] = useSearchParams();
  const tab = TABS.find((t) => t.key === params.get("tab")) ?? TABS[0];
  const all = posts.data ?? [];
  const shown = all.filter(tab.match);

  return (
    <>
      <PageHeader title="Posts" subtitle="Tous tes contenus, du brouillon à la publication." />
      <div className="mb-4 flex gap-1 overflow-x-auto" role="tablist">
        {TABS.map((t) => {
          const count = all.filter(t.match).length;
          return (
            <button
              key={t.key}
              role="tab"
              aria-selected={t.key === tab.key}
              onClick={() => setParams(t.key === "all" ? {} : { tab: t.key })}
              className={cx(
                "flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium",
                t.key === tab.key ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100",
              )}
            >
              {t.label}
              {t.key !== "all" && count > 0 && (
                <span className={cx("rounded-full px-1.5 text-xs", t.key === tab.key ? "bg-white/20" : t.key === "approval" ? "bg-violet-100 text-violet-700" : "bg-slate-200")}>{count}</span>
              )}
            </button>
          );
        })}
      </div>
      {posts.isError && <ErrorNote>{posts.error.message}</ErrorNote>}
      {posts.isPending ? (
        <Spinner />
      ) : shown.length === 0 ? (
        <Empty icon={<PenLine className="size-5" />} title={all.length === 0 ? "Aucun post pour l'instant" : "Rien dans cette catégorie"}>
          {all.length === 0 && (
            <>
              <p>Écris ton premier post, ou laisse ton assistant IA le préparer.</p>
              <Button variant="primary" className="mt-4" onClick={() => openComposer()}>Nouveau post</Button>
            </>
          )}
        </Empty>
      ) : (
        <div className="space-y-3">
          {shown.map((p) => (
            <Card key={p.id}>
              <button onClick={() => openComposer({ post: p })} className="flex w-full items-start gap-4 p-4 text-left">
                {p.media[0] ? (
                  <div className="size-16 shrink-0 overflow-hidden rounded-lg bg-slate-100"><MediaThumb media={p.media[0]} /></div>
                ) : (
                  <div className="flex size-16 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-400"><PenLine className="size-5" /></div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <StatusBadge status={p.status} />
                    {p.source === "mcp" && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700">
                        <Sparkles className="size-3" /> {needsApproval(p) ? "À valider" : "IA"}
                      </span>
                    )}
                    {p.scheduled_at && <span className="text-xs text-slate-500">{format(new Date(p.scheduled_at), "EEE d MMM yyyy 'à' HH:mm", { locale: fr })}</span>}
                  </div>
                  <p className="line-clamp-2 break-words text-sm text-slate-700">{p.caption || <span className="text-slate-400">Sans texte</span>}</p>
                </div>
                <div className="flex shrink-0 -space-x-2">
                  {p.targets.slice(0, 4).map((t) => <AccountAvatar key={t.id} account={t.account} size="size-8" />)}
                </div>
              </button>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
