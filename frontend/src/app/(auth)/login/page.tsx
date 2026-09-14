import { Building2 } from "lucide-react";

import { LoginForm } from "@/features/auth/login-form";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-slate-100 p-6">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-8 flex items-center gap-3"><Building2 className="size-8 text-cyan-800" /><div><h1 className="text-xl font-semibold">Travel ERP</h1><p className="text-sm text-slate-500">Sign in to your agency workspace</p></div></div>
        <LoginForm />
      </section>
    </main>
  );
}

