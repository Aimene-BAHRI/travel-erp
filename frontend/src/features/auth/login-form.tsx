"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, LogIn } from "lucide-react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { apiRequest, ensureCsrfToken } from "@/lib/api/client";

import type { CurrentUser } from "./types";

const loginSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  const login = useMutation({
    mutationFn: async (values: LoginValues) => {
      await ensureCsrfToken();
      return apiRequest<CurrentUser>("/auth/login/", {
        method: "POST",
        body: JSON.stringify(values),
      });
    },
    onSuccess: (user) => {
      queryClient.setQueryData(["current-user"], user);
      router.replace("/dashboard");
    },
  });

  return (
    <form className="space-y-5" onSubmit={form.handleSubmit((values) => login.mutate(values))}>
      <div>
        <label className="mb-2 block text-sm font-medium text-slate-700" htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          className="w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-cyan-700 focus:ring-2 focus:ring-cyan-100"
          {...form.register("email")}
        />
        {form.formState.errors.email && <p className="mt-1 text-sm text-red-600">{form.formState.errors.email.message}</p>}
      </div>
      <div>
        <label className="mb-2 block text-sm font-medium text-slate-700" htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          className="w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-cyan-700 focus:ring-2 focus:ring-cyan-100"
          {...form.register("password")}
        />
        {form.formState.errors.password && <p className="mt-1 text-sm text-red-600">{form.formState.errors.password.message}</p>}
      </div>
      {login.isError && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">The email or password is incorrect.</p>}
      <button
        type="submit"
        disabled={login.isPending}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-800 px-4 py-2.5 font-medium text-white hover:bg-cyan-900 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {login.isPending ? <LoaderCircle className="size-5 animate-spin" /> : <LogIn className="size-5" />}
        Sign in
      </button>
    </form>
  );
}

