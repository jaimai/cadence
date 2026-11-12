import { addDays, addMonths, format, isSameDay, isSameMonth, startOfMonth, startOfWeek } from "date-fns";
import { fr } from "date-fns/locale";
import { ChevronLeft, ChevronRight, Plus, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { Post } from "../api";
import { needsApproval, useComposer, usePosts } from "../hooks";
import { Button, Card, cx, ErrorNote, PageHeader, PlatformIcon, Spinner, STATUS } from "../ui";

const DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

export function ApprovalBanner({ posts }: { posts: Post[] }) {
  const count = posts.filter(needsApproval).length;
  if (count === 0) return null;
  return (
    <Link to="/posts?tab=approval" className="mb-4 flex items-center gap-2 rounded-xl bg-violet-50 px-4 py-3 text-sm text-violet-800 ring-1 ring-violet-200 hover:bg-violet-100">
      <Sparkles className="size-4 shrink-0" />
      <span>
        <strong>{count} post{count > 1 ? "s" : ""}</strong> proposé{count > 1 ? "s" : ""} par ton assistant IA {count > 1 ? "attendent" : "attend"} ta validation.
      </span>
    </Link>
  );
}

export default function CalendarPage() {
  const posts = usePosts();
  const openComposer = useComposer();
  const [month, setMonth] = useState(() => startOfMonth(new Date()));
  const today = new Date();

  const days = useMemo(() => {
    const first = startOfWeek(month, { weekStartsOn: 1 });
    const cells = Array.from({ length: 42 }, (_, i) => addDays(first, i));
    // Drop the sixth week when it belongs entirely to the next month.
    return isSameMonth(cells[35], month) ? cells : cells.slice(0, 35);
  }, [month]);

  const byDay = useMemo(() => {
    const map = new Map<string, Post[]>();
    for (const p of posts.data ?? []) {
      if (!p.scheduled_at) continue;
      const key = format(new Date(p.scheduled_at), "yyyy-MM-dd");
      map.set(key, [...(map.get(key) ?? []), p]);
    }
    for (const list of map.values()) list.sort((a, b) => a.scheduled_at!.localeCompare(b.scheduled_at!));
    return map;
  }, [posts.data]);

  return (
    <>
      <PageHeader
        title="Calendrier"
        subtitle="Clique sur un jour pour y planifier un post."
        action={
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => setMonth(startOfMonth(new Date()))}>Aujourd'hui</Button>
            <Button size="sm" aria-label="Mois précédent" onClick={() => setMonth((m) => addMonths(m, -1))}><ChevronLeft className="size-4" /></Button>
            <span className="w-36 text-center text-sm font-medium capitalize">{format(month, "MMMM yyyy", { locale: fr })}</span>
            <Button size="sm" aria-label="Mois suivant" onClick={() => setMonth((m) => addMonths(m, 1))}><ChevronRight className="size-4" /></Button>
          </div>
        }
      />
      {posts.isError && <div className="mb-4"><ErrorNote>{posts.error.message}</ErrorNote></div>}
      {posts.data && <ApprovalBanner posts={posts.data} />}
      {posts.isPending ? (
        <Spinner />
      ) : (
        <Card className="overflow-hidden">
          <div className="grid grid-cols-7 border-b border-slate-100 bg-slate-50 text-center text-xs font-medium text-slate-500">
            {DAYS.map((d) => <div key={d} className="py-2">{d}</div>)}
          </div>
          <div className="grid grid-cols-7">
            {days.map((day) => {
              const list = byDay.get(format(day, "yyyy-MM-dd")) ?? [];
              const isToday = isSameDay(day, today);
              return (
                <div
                  key={day.toISOString()}
                  className={cx("group relative min-h-24 border-b border-r border-slate-100 p-1.5 md:min-h-32", !isSameMonth(day, month) && "bg-slate-50/60")}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className={cx("flex size-6 items-center justify-center rounded-full text-xs", isToday ? "bg-brand-600 font-semibold text-white" : isSameMonth(day, month) ? "text-slate-700" : "text-slate-400")}>
                      {format(day, "d")}
                    </span>
                    <button
                      aria-label={`Nouveau post le ${format(day, "d MMMM", { locale: fr })}`}
                      onClick={() => openComposer({ date: day })}
                      className="rounded p-0.5 text-slate-400 opacity-0 hover:bg-slate-100 hover:text-brand-600 focus:opacity-100 group-hover:opacity-100"
                    >
                      <Plus className="size-4" />
                    </button>
                  </div>
                  <div className="space-y-1">
                    {list.slice(0, 3).map((p) => (
                      <button
                        key={p.id}
                        onClick={() => openComposer({ post: p })}
                        title={p.caption}
                        className={cx(
                          "flex w-full items-center gap-1 rounded-md px-1.5 py-1 text-left text-xs",
                          needsApproval(p) ? "border border-dashed border-violet-300 bg-violet-50 text-violet-800" : STATUS[p.status].chip,
                        )}
                      >
                        <span className="hidden shrink-0 tabular-nums opacity-70 md:inline">{format(new Date(p.scheduled_at!), "HH:mm")}</span>
                        <span className="min-w-0 flex-1 truncate">{p.caption || "Sans texte"}</span>
                        {p.targets[0] && <PlatformIcon platform={p.targets[0].account.platform} className="hidden size-3.5 shrink-0 text-[7px] md:inline-flex" />}
                      </button>
                    ))}
                    {list.length > 3 && <p className="px-1.5 text-xs text-slate-500">+{list.length - 3} autres</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </>
  );
}
