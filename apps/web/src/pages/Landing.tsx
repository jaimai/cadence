import { ArrowRight, CalendarDays, Check, Images, RotateCcw, Send, ShieldCheck, Sparkles, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../App";
import { cx, PlatformIcon } from "../ui";

const primary = "inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700";
const secondary = "inline-flex items-center justify-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-50";

const NETWORKS = [
  { platform: "tiktok", label: "TikTok", note: "Plusieurs comptes" },
  { platform: "instagram", label: "Instagram", note: "Posts, carrousels, Reels" },
  { platform: "facebook", label: "Facebook", note: "Pages" },
  { platform: "linkedin", label: "LinkedIn", note: "Profil personnel" },
  { platform: "x", label: "X", note: "Plusieurs comptes" },
];

const FEATURES = [
  { icon: Users, title: "Tous tes comptes au même endroit", text: "Connecte les comptes de chacune de tes apps, y compris plusieurs comptes TikTok, et choisis où part chaque post." },
  { icon: Send, title: "Un post, plusieurs réseaux", text: "Écris une fois, publie partout. Cadence vérifie les règles de chaque réseau avant l'envoi, pas après." },
  { icon: CalendarDays, title: "Un calendrier lisible", text: "Vois ton mois d'un coup d'œil. Clique sur un jour pour planifier, sur un post pour le modifier." },
  { icon: Images, title: "Une médiathèque partagée", text: "Importe tes images et vidéos une fois, réutilise-les dans tous tes posts." },
  { icon: RotateCcw, title: "Des échecs qui se rattrapent", text: "Une erreur passagère est retentée automatiquement. Sinon tu sais pourquoi, et tu relances en un clic." },
  { icon: ShieldCheck, title: "Tu gardes la main", text: "Rien ne part sans toi si tu le décides : les posts préparés par l'IA attendent ta validation." },
];

const STEPS = [
  { title: "Connecte tes comptes", text: "Quelques clics par réseau, avec la connexion officielle de chaque plateforme." },
  { title: "Prépare tes posts", text: "Dans l'interface, ou en le demandant à ton assistant IA." },
  { title: "Laisse Cadence publier", text: "À l'heure prévue, sur chaque compte, avec le suivi de chaque publication." },
];

function Section({ id, eyebrow, title, children }: { id?: string; eyebrow: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="mx-auto max-w-6xl scroll-mt-20 px-5 py-16 md:py-24">
      <p className="text-sm font-semibold text-brand-600">{eyebrow}</p>
      <h2 className="mt-2 max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">{title}</h2>
      <div className="mt-10">{children}</div>
    </section>
  );
}

/** Stylised product preview: a week of the calendar. */
type MockPost = { t: string; c: string; p: string; ai?: boolean };

function CalendarMock() {
  const days: { d: string; n: number; posts: MockPost[]; today?: boolean }[] = [
    { d: "Lun", n: 9, posts: [{ t: "09:00", c: "Astuce du lundi", p: "instagram" }] },
    { d: "Mar", n: 10, posts: [{ t: "18:30", c: "Nouvelle séance", p: "tiktok" }, { t: "18:30", c: "Nouvelle séance", p: "facebook" }] },
    { d: "Mer", n: 11, posts: [] },
    { d: "Jeu", n: 12, posts: [{ t: "12:15", c: "Coulisses", p: "tiktok" }], today: true },
    { d: "Ven", n: 13, posts: [{ t: "17:00", c: "Recette express", p: "instagram", ai: true }] },
    { d: "Sam", n: 14, posts: [{ t: "10:00", c: "Défi du week-end", p: "tiktok" }] },
    { d: "Dim", n: 15, posts: [] },
  ];
  return (
    <div aria-hidden="true" className="overflow-hidden rounded-2xl bg-white shadow-2xl shadow-brand-600/10 ring-1 ring-slate-200">
      <div className="flex items-center gap-1.5 border-b border-slate-100 px-4 py-3">
        <span className="size-2.5 rounded-full bg-slate-200" />
        <span className="size-2.5 rounded-full bg-slate-200" />
        <span className="size-2.5 rounded-full bg-slate-200" />
        <span className="ml-3 text-xs font-medium text-slate-400">Calendrier</span>
      </div>
      <div className="grid grid-cols-7 divide-x divide-slate-100">
        {days.map((day) => (
          <div key={day.n} className="min-h-40 p-1.5 sm:min-h-52 sm:p-2">
            <p className="text-center text-[10px] font-medium text-slate-400 sm:text-xs">{day.d}</p>
            <p className={cx("mx-auto mt-1 flex size-6 items-center justify-center rounded-full text-xs", day.today ? "bg-brand-600 font-semibold text-white" : "text-slate-700")}>{day.n}</p>
            <div className="mt-2 space-y-1.5">
              {day.posts.map((post, i) => (
                <div key={i} className={cx("rounded-md px-1.5 py-1 text-left text-[10px] sm:text-xs", post.ai ? "border border-dashed border-violet-300 bg-violet-50 text-violet-800" : "bg-brand-50 text-brand-700")}>
                  <div className="flex items-center gap-1">
                    <PlatformIcon platform={post.p} className="size-3.5 shrink-0 text-[7px]" />
                    <span className="tabular-nums opacity-70">{post.t}</span>
                  </div>
                  <p className="mt-0.5 hidden truncate sm:block">{post.c}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChatMock() {
  return (
    <div aria-hidden="true" className="space-y-3 rounded-2xl bg-white/5 p-5 ring-1 ring-white/10">
      <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-brand-500 px-4 py-2.5 text-sm text-white">
        Planifie la vidéo de lancement sur mes trois comptes TikTok demain à 18 h, avec une légende différente pour chacun.
      </p>
      <div className="w-fit max-w-[85%] space-y-2 rounded-2xl rounded-bl-md bg-white/10 px-4 py-3 text-sm text-slate-100">
        <p>C'est prêt. J'ai préparé trois posts pour demain 18 h :</p>
        <ul className="space-y-1 text-slate-300">
          {["@monapp.fitness", "@monapp.recettes", "@monapp.studio"].map((name) => (
            <li key={name} className="flex items-center gap-2">
              <PlatformIcon platform="tiktok" className="size-4 text-[7px] ring-1 ring-white/30" /> {name}
            </li>
          ))}
        </ul>
        <p className="flex items-center gap-1.5 text-violet-200">
          <Sparkles className="size-3.5" /> Ils attendent ta validation dans Cadence.
        </p>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="bg-white">
      <header className="sticky top-0 z-20 border-b border-slate-100 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <Logo />
          <nav className="hidden items-center gap-7 text-sm font-medium text-slate-600 md:flex">
            <a href="#fonctionnalites" className="hover:text-slate-900">Fonctionnalités</a>
            <a href="#ia" className="hover:text-slate-900">Pilotage par IA</a>
            <a href="#demarrer" className="hover:text-slate-900">Comment ça marche</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">Se connecter</Link>
            <Link to="/signup" className="rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-semibold text-white hover:bg-brand-700">Commencer</Link>
          </div>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden bg-gradient-to-b from-brand-50 via-white to-white">
          <div className="mx-auto max-w-6xl px-5 pb-16 pt-16 text-center md:pt-24">
            <p className="mx-auto mb-5 inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-medium text-brand-700 ring-1 ring-brand-100">
              <Sparkles className="size-3.5" /> Pilotable depuis Claude et tout assistant compatible MCP
            </p>
            <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl md:text-6xl">
              Tous tes réseaux.<br />
              <span className="text-brand-600">Un seul calendrier.</span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
              Planifie et publie le contenu de toutes tes apps sur TikTok, Instagram, Facebook, LinkedIn et X, depuis une interface simple ou en le demandant à ton assistant IA.
            </p>
            <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
              <Link to="/signup" className={primary}>Créer mon espace <ArrowRight className="size-4" /></Link>
              <a href="#fonctionnalites" className={secondary}>Voir les fonctionnalités</a>
            </div>
            <div className="mx-auto mt-14 max-w-4xl"><CalendarMock /></div>
          </div>
        </section>

        <section aria-label="Réseaux pris en charge" className="border-y border-slate-100 bg-slate-50">
          <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-5 py-8 sm:grid-cols-3 lg:grid-cols-5">
            {NETWORKS.map((n) => (
              <div key={n.platform} className="flex items-center gap-3">
                <PlatformIcon platform={n.platform} className="size-10 shrink-0 text-sm" />
                <div>
                  <p className="font-medium">{n.label}</p>
                  <p className="text-sm text-slate-500">{n.note}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <Section id="fonctionnalites" eyebrow="Fonctionnalités" title="L'essentiel pour publier régulièrement, sans y passer tes journées.">
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="rounded-2xl p-6 ring-1 ring-slate-200">
                <div className="flex size-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><Icon className="size-5" /></div>
                <h3 className="mt-4 font-semibold">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{text}</p>
              </div>
            ))}
          </div>
        </Section>

        <section id="ia" className="scroll-mt-20 bg-slate-900 text-white">
          <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-16 md:grid-cols-2 md:py-24">
            <div>
              <p className="text-sm font-semibold text-brand-100">Pilotage par IA</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">Demande-le, c'est planifié.</h2>
              <p className="mt-4 text-slate-300">
                Cadence se branche sur ton assistant IA par le protocole MCP. Il peut lister tes comptes, importer un média, écrire, planifier et suivre tes publications, avec les mêmes règles que l'interface.
              </p>
              <ul className="mt-6 space-y-3 text-sm text-slate-200">
                {[
                  "Validation humaine par défaut : l'assistant prépare, tu approuves.",
                  "Publication directe possible, quand tu lui fais confiance.",
                  "Des clés d'accès que tu crées et révoques à tout moment.",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2.5">
                    <Check className="mt-0.5 size-4 shrink-0 text-emerald-400" /> {item}
                  </li>
                ))}
              </ul>
            </div>
            <ChatMock />
          </div>
        </section>

        <Section id="demarrer" eyebrow="Comment ça marche" title="Trois étapes, et tes réseaux tournent.">
          <ol className="grid gap-5 md:grid-cols-3">
            {STEPS.map((step, i) => (
              <li key={step.title} className="rounded-2xl bg-slate-50 p-6">
                <span className="flex size-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">{i + 1}</span>
                <h3 className="mt-4 font-semibold">{step.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{step.text}</p>
              </li>
            ))}
          </ol>
        </Section>

        <section className="mx-auto max-w-6xl px-5 pb-20">
          <div className="rounded-3xl bg-gradient-to-br from-brand-600 to-brand-700 px-6 py-14 text-center text-white">
            <h2 className="text-3xl font-semibold tracking-tight">Prêt à reprendre la main sur tes réseaux ?</h2>
            <p className="mx-auto mt-3 max-w-xl text-brand-100">Crée ton espace, connecte un premier compte et planifie ton premier post en quelques minutes.</p>
            <Link to="/signup" className="mt-7 inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-brand-700 hover:bg-brand-50">
              Créer mon espace <ArrowRight className="size-4" />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-100">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-5 py-8 text-sm text-slate-500 sm:flex-row">
          <Logo />
          <p>© {new Date().getFullYear()} Cadence</p>
        </div>
      </footer>
    </div>
  );
}
