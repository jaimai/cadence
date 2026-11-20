import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../App";
import { PRIVACY, PUBLISHER, TERMS, UPDATED, type Lang } from "../legal";
import { cx } from "../ui";

export function LegalLinks({ className }: { className?: string }) {
  return (
    <nav aria-label="Informations légales" className={cx("flex flex-wrap gap-x-5 gap-y-1", className)}>
      <Link to="/terms" className="hover:underline">Conditions d'utilisation</Link>
      <Link to="/privacy" className="hover:underline">Confidentialité</Link>
    </nav>
  );
}

export default function LegalPage({ kind }: { kind: "terms" | "privacy" }) {
  // Reviewers at the social networks read English; the product itself is in French.
  const [lang, setLang] = useState<Lang>(() => (navigator.language.toLowerCase().startsWith("fr") ? "fr" : "en"));
  const doc = (kind === "terms" ? TERMS : PRIVACY)[lang];

  useEffect(() => {
    document.title = `${doc.title} · Cadence`;
    window.scrollTo(0, 0);
    return () => {
      document.title = "Cadence";
    };
  }, [doc.title]);

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-slate-100">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-3">
          <Link to="/" aria-label="Accueil"><Logo /></Link>
          <div className="flex rounded-lg p-0.5 ring-1 ring-slate-200" role="group" aria-label="Langue / Language">
            {(["fr", "en"] as const).map((l) => (
              <button
                key={l}
                aria-pressed={lang === l}
                onClick={() => setLang(l)}
                className={cx("rounded-md px-2.5 py-1 text-sm font-medium", lang === l ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100")}
              >
                {l === "fr" ? "Français" : "English"}
              </button>
            ))}
          </div>
        </div>
      </header>
      <main lang={lang} className="mx-auto max-w-3xl px-5 py-10">
        <Link to="/" className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
          <ArrowLeft className="size-4" /> {lang === "fr" ? "Accueil" : "Home"}
        </Link>
        <h1 className="text-3xl font-semibold tracking-tight">{doc.title}</h1>
        <p className="mt-2 text-sm text-slate-500">
          {lang === "fr" ? `Dernière mise à jour : ${UPDATED.fr}` : `Last updated: ${UPDATED.en}`} · {PUBLISHER}
        </p>
        <p className="mt-6 leading-relaxed text-slate-700">{doc.intro}</p>
        {doc.sections.map((section) => (
          <section key={section.title} className="mt-8">
            <h2 className="text-lg font-semibold">{section.title}</h2>
            {section.text?.map((paragraph) => (
              <p key={paragraph} className="mt-3 leading-relaxed text-slate-700">{paragraph}</p>
            ))}
            {section.list && (
              <ul className="mt-3 list-disc space-y-2 pl-5 leading-relaxed text-slate-700">
                {section.list.map((item) => <li key={item}>{item}</li>)}
              </ul>
            )}
          </section>
        ))}
      </main>
      <footer className="border-t border-slate-100">
        <div className="mx-auto max-w-3xl px-5 py-6 text-sm text-slate-500"><LegalLinks /></div>
      </footer>
    </div>
  );
}
