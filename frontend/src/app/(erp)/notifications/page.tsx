"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/features/auth/auth-gate";
import { NotificationInbox } from "@/features/notifications/notification-inbox";

export default function NotificationsPage() {
  const uiText = useUiText();
  return (
    <AuthGate>
      {(user) => (
        <AppShell user={user}>
          <header className="mb-7">
            <p className="text-sm font-medium text-cyan-800">{uiText("قائمة المتابعة")}</p>
            <h1 className="mt-1 text-3xl font-semibold">{uiText("الإشعارات")}</h1>
          </header>
          <NotificationInbox />
        </AppShell>
      )}
    </AuthGate>
  );
}
