"use client";
import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { PartnerWorkspace } from "@/features/partners/partner-workspace";
export default function PartnersPage(){return <AuthGate>{user=><AppShell user={user}><header className="mb-7"><p className="text-sm font-medium text-cyan-800">Distribution and commissions</p><h1 className="mt-1 text-3xl font-semibold">Partners</h1></header><PartnerWorkspace/></AppShell>}</AuthGate>}
