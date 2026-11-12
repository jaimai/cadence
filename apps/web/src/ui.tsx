import { Loader2, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import type { Account, PostStatus } from "./api";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
};

const VARIANTS = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm",
  secondary: "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 shadow-sm",
  ghost: "text-slate-600 hover:bg-slate-100",
  danger: "text-red-600 hover:bg-red-50",
};

export function Button({ variant = "secondary", size = "md", loading, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:opacity-50",
        size === "sm" ? "px-2.5 py-1.5 text-sm" : "px-4 py-2 text-sm",
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx("rounded-2xl bg-white ring-1 ring-slate-200/70 shadow-sm", className)}>{children}</div>;
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-slate-300 px-6 py-14 text-center">
      <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">{icon}</div>
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 max-w-sm text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function Spinner() {
  return (
    <div className="flex justify-center py-16 text-slate-400">
      <Loader2 className="size-6 animate-spin" />
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{children}</p>;
}

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:p-8" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cx("w-full rounded-2xl bg-white shadow-xl", wide ? "max-w-5xl" : "max-w-lg")}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button aria-label="Fermer" onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X className="size-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

const PLATFORM_STYLE: Record<string, { bg: string; letter: string }> = {
  facebook: { bg: "bg-[#1877f2]", letter: "f" },
  instagram: { bg: "bg-gradient-to-tr from-amber-400 via-pink-500 to-purple-600", letter: "ig" },
  linkedin: { bg: "bg-[#0a66c2]", letter: "in" },
  tiktok: { bg: "bg-black", letter: "tt" },
  x: { bg: "bg-slate-900", letter: "X" },
};

export function PlatformIcon({ platform, className }: { platform: string; className?: string }) {
  const style = PLATFORM_STYLE[platform] ?? { bg: "bg-slate-500", letter: "?" };
  return (
    <span className={cx("inline-flex items-center justify-center rounded-full font-bold text-white", style.bg, className ?? "size-5 text-[10px]")}>
      {style.letter}
    </span>
  );
}

export function AccountAvatar({ account, size = "size-9" }: { account: Account; size?: string }) {
  const [broken, setBroken] = useState(false);
  return (
    <span className={cx("relative inline-block shrink-0", size)}>
      {account.avatar_url && !broken ? (
        <img src={account.avatar_url} alt="" onError={() => setBroken(true)} className="size-full rounded-full object-cover" />
      ) : (
        <span className="flex size-full items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-600">
          {account.display_name.slice(0, 1).toUpperCase()}
        </span>
      )}
      <PlatformIcon platform={account.platform} className="absolute -bottom-0.5 -right-0.5 size-4 text-[8px] ring-2 ring-white" />
    </span>
  );
}

export const STATUS: Record<PostStatus, { label: string; chip: string; dot: string }> = {
  draft: { label: "Brouillon", chip: "bg-slate-100 text-slate-700", dot: "bg-slate-400" },
  scheduled: { label: "Planifié", chip: "bg-brand-50 text-brand-700", dot: "bg-brand-500" },
  publishing: { label: "En cours", chip: "bg-amber-50 text-amber-700", dot: "bg-amber-500" },
  published: { label: "Publié", chip: "bg-emerald-50 text-emerald-700", dot: "bg-emerald-500" },
  partial: { label: "Partiel", chip: "bg-orange-50 text-orange-700", dot: "bg-orange-500" },
  failed: { label: "Échec", chip: "bg-red-50 text-red-700", dot: "bg-red-500" },
};

export function StatusBadge({ status }: { status: PostStatus }) {
  const s = STATUS[status];
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", s.chip)}>
      <span className={cx("size-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
  );
}

type Toast = { id: number; message: string; kind: "ok" | "error" };
const ToastContext = createContext<(message: string, kind?: Toast["kind"]) => void>(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((message: string, kind: Toast["kind"] = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={cx("max-w-sm rounded-xl px-4 py-3 text-sm text-white shadow-lg", t.kind === "error" ? "bg-red-600" : "bg-slate-900")}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function formatBytes(n: number) {
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} Ko`;
  return `${(n / 1024 / 1024).toFixed(1)} Mo`;
}
