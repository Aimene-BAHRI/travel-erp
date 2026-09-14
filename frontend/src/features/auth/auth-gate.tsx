"use client";

import { useQuery } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { apiRequest, ApiError } from "@/lib/api/client";

import type { CurrentUser } from "./types";

export function AuthGate({ children }: Readonly<{ children: (user: CurrentUser) => React.ReactNode }>) {
  const router = useRouter();
  const session = useQuery({
    queryKey: ["current-user"],
    queryFn: () => apiRequest<CurrentUser>("/auth/me/"),
  });

  useEffect(() => {
    if (session.error instanceof ApiError && session.error.status === 401) router.replace("/login");
  }, [router, session.error]);

  if (session.isPending) {
    return <div className="grid min-h-screen place-items-center"><LoaderCircle className="size-8 animate-spin text-cyan-800" /></div>;
  }
  if (!session.data) return null;
  return children(session.data);
}

