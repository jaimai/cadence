import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext } from "react";
import { api, type Post } from "./api";

export const useMe = () => useQuery({ queryKey: ["me"], queryFn: api.me });
export const useAccounts = () => useQuery({ queryKey: ["accounts"], queryFn: api.accounts });
export const useMedia = () => useQuery({ queryKey: ["media"], queryFn: api.media });
// Polled so statuses follow the worker without a manual refresh.
export const usePosts = () => useQuery({ queryKey: ["posts"], queryFn: api.posts, refetchInterval: 15_000 });

export function useInvalidate() {
  const client = useQueryClient();
  return (...keys: string[]) => Promise.all(keys.map((k) => client.invalidateQueries({ queryKey: [k] })));
}

export type ComposerRequest = { post?: Post; date?: Date };
export const ComposerContext = createContext<(request?: ComposerRequest) => void>(() => {});
export const useComposer = () => useContext(ComposerContext);

/** Drafts an LLM wanted to publish: they wait for a human decision. */
export const needsApproval = (p: Post) => p.status === "draft" && p.source === "mcp";
