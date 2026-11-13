export type Account = {
  id: string;
  platform: string;
  display_name: string;
  username: string | null;
  avatar_url: string | null;
  status: "active" | "needs_reauth";
};

export type Media = {
  id: string;
  filename: string;
  content_type: string;
  kind: "image" | "video";
  size: number;
  status: string;
  url: string;
  created_at: string;
};

export type Target = {
  id: string;
  account: Account;
  caption_override: string | null;
  status: "pending" | "publishing" | "published" | "failed";
  attempts: number;
  permalink: string | null;
  error: string | null;
  published_at: string | null;
};

export type PostStatus = "draft" | "scheduled" | "publishing" | "published" | "partial" | "failed";

export type Post = {
  id: string;
  caption: string;
  status: PostStatus;
  scheduled_at: string | null;
  source: "web" | "mcp";
  created_at: string;
  updated_at: string;
  media: Media[];
  targets: Target[];
};

export type Platform = { platform: string; label: string; available: boolean; configured: boolean };
export type Workspace = { id: string; name: string; llm_publish_mode: "draft" | "direct" };
export type Me = { email: string; workspace: Workspace };
export type ApiKey = { id: string; name: string; prefix: string; created_at: string; last_used_at: string | null; key?: string };

export type PostInput = {
  caption: string;
  account_ids: string[];
  media_ids: string[];
  caption_overrides?: Record<string, string>;
};

// Empty in dev (Vite proxies /api). Set VITE_API_URL to the API origin in production.
export const API_URL: string = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_URL + path, {
      method,
      credentials: "include",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Serveur injoignable. Vérifie ta connexion.", 0);
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => undefined);
  // A 200 that is not JSON is not our API answering: typically the host serving
  // the app's HTML for /api because no API is configured.
  if (data === undefined && (res.ok || res.status === 404)) {
    throw new ApiError("Le serveur ne répond pas pour le moment.", 0);
  }
  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string" ? detail : res.status === 422 ? "Certains champs sont invalides." : "Une erreur est survenue.";
    throw new ApiError(message, res.status);
  }
  return data as T;
}

export async function uploadFile(file: File): Promise<Media> {
  const presign = await request<{
    media: Media;
    upload_url: string;
    upload_method: string;
    upload_headers: Record<string, string>;
  }>("POST", "/api/media/presign", { filename: file.name, content_type: file.type, size: file.size });
  // Local dev storage uploads through our API (needs the session cookie);
  // R2 uploads go straight to Cloudflare with a presigned URL.
  const target = new URL(presign.upload_url, window.location.href);
  const viaApi = target.pathname.startsWith("/api/media/");
  const res = await fetch(viaApi ? API_URL + target.pathname : presign.upload_url, {
    method: presign.upload_method,
    headers: presign.upload_headers,
    body: file,
    credentials: viaApi ? "include" : "omit",
  }).catch(() => null);
  if (!res || !res.ok) throw new ApiError(`L'envoi de « ${file.name} » a échoué.`, res?.status ?? 0);
  return request<Media>("POST", `/api/media/${presign.media.id}/complete`);
}

export const api = {
  me: () => request<Me>("GET", "/api/auth/me"),
  login: (email: string, password: string) => request("POST", "/api/auth/login", { email, password }),
  signup: (email: string, password: string) => request("POST", "/api/auth/signup", { email, password }),
  logout: () => request("POST", "/api/auth/logout"),

  platforms: () => request<Platform[]>("GET", "/api/platforms"),
  accounts: () => request<Account[]>("GET", "/api/accounts"),
  disconnect: (id: string) => request<void>("DELETE", `/api/accounts/${id}`),
  oauthStart: (platform: string) => request<{ url: string }>("GET", `/api/oauth/${platform}/start`),
  oauthLink: (platform: string) =>
    request<{ url: string; expires_at: string; reachable: boolean }>("POST", `/api/oauth/${platform}/link`),

  media: () => request<Media[]>("GET", "/api/media"),
  deleteMedia: (id: string) => request<void>("DELETE", `/api/media/${id}`),

  posts: () => request<Post[]>("GET", "/api/posts?limit=500"),
  createPost: (body: PostInput & { scheduled_at?: string | null; publish_now?: boolean }) =>
    request<Post>("POST", "/api/posts", body),
  updatePost: (id: string, body: Partial<PostInput>) => request<Post>("PATCH", `/api/posts/${id}`, body),
  schedulePost: (id: string, scheduled_at: string | null) =>
    request<Post>("POST", `/api/posts/${id}/schedule`, { scheduled_at }),
  unschedulePost: (id: string) => request<Post>("POST", `/api/posts/${id}/unschedule`),
  retryPost: (id: string) => request<Post>("POST", `/api/posts/${id}/retry`),
  deletePost: (id: string) => request<void>("DELETE", `/api/posts/${id}`),

  updateWorkspace: (body: Partial<Pick<Workspace, "name" | "llm_publish_mode">>) =>
    request<Workspace>("PATCH", "/api/workspace", body),
  apiKeys: () => request<ApiKey[]>("GET", "/api/api-keys"),
  createApiKey: (name: string) => request<ApiKey>("POST", "/api/api-keys", { name }),
  revokeApiKey: (id: string) => request<void>("DELETE", `/api/api-keys/${id}`),
};
