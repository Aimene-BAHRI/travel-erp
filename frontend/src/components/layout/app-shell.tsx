"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRightLeft,
  Banknote,
  Bell,
  BookOpenCheck,
  Bus,
  Building2,
  CalendarDays,
  Contact,
  CreditCard,
  Hotel,
  Inbox,
  LayoutDashboard,
  LogOut,
  Menu,
  PackageSearch,
  Settings,
  Languages,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { CurrentUser } from "@/features/auth/types";
import { NotificationCenter } from "@/features/notifications/notification-center";
import type { TransportOverview } from "@/features/trips/transport-types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";

const navigation = [
  { label: { ar: "لوحة التحكم", en: "Dashboard" }, href: "/dashboard", icon: LayoutDashboard },
  { label: { ar: "الرحلات", en: "Trips" }, href: "/trips", icon: CalendarDays },
  { label: { ar: "النقل", en: "Transport" }, href: "/transport", icon: Bus },
  { label: { ar: "الحجوزات", en: "Bookings" }, href: "/bookings", icon: BookOpenCheck },
  { label: { ar: "طلبات الحجز", en: "Booking requests" }, href: "/booking-requests", icon: Inbox },
  { label: { ar: "المدفوعات", en: "Payments" }, href: "/payments", icon: CreditCard },
  { label: { ar: "الصندوق", en: "Cash flow" }, href: "/cash-flow", icon: Banknote },
  { label: { ar: "أسعار الصرف", en: "Exchange rates" }, href: "/exchange-rates", icon: ArrowRightLeft },
  { label: { ar: "المسافرون", en: "Travelers" }, href: "/travelers", icon: Users },
  { label: { ar: "العملاء", en: "Customers" }, href: "/customers", icon: Contact },
  { label: { ar: "الفنادق", en: "Hotels" }, href: "/hotels", icon: Hotel },
  { label: { ar: "الفهرس", en: "Catalog" }, href: "/catalog", icon: PackageSearch },
  { label: { ar: "الإعدادات", en: "Settings" }, href: "/settings", icon: Settings },
  { label: { ar: "الإشعارات", en: "Notifications" }, href: "/notifications", icon: Bell },
];

export function AppShell({
  user,
  children,
}: Readonly<{ user: CurrentUser; children: React.ReactNode }>) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { locale, isRtl, toggleLocale } = useLocale();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const transport = useQuery({
    queryKey: ["transport-overview"],
    queryFn: () => apiRequest<TransportOverview>("/trips/transports/overview/"),
  });
  const logout = useMutation({
    mutationFn: () => apiRequest<void>("/auth/logout/", { method: "POST" }),
    onSuccess: () => {
      queryClient.clear();
      router.replace("/");
      router.refresh();
    },
  });
  return (
    <div className={`min-h-screen bg-slate-50 md:grid print:block print:min-h-0 print:bg-white ${isRtl ? "md:grid-cols-[1fr_260px]" : "md:grid-cols-[260px_1fr]"}`}>
      {mobileNavOpen && (
        <button
          type="button"
          aria-label={locale === "ar" ? "إغلاق القائمة" : "Close menu"}
          onClick={() => setMobileNavOpen(false)}
          className="no-print fixed inset-0 z-40 bg-slate-950/50 md:hidden"
        />
      )}
      <aside
        className={`no-print fixed inset-y-0 z-50 w-72 overflow-y-auto bg-slate-950 p-5 text-slate-100 transition-transform md:static md:z-auto md:w-auto md:translate-x-0 ${
          isRtl
            ? `right-0 border-l border-slate-200 ${mobileNavOpen ? "translate-x-0" : "translate-x-full"} md:col-start-2`
            : `left-0 border-r border-slate-200 ${mobileNavOpen ? "translate-x-0" : "-translate-x-full"} md:col-start-1`
        }`}
      >
        <div className="flex items-center justify-between gap-3 border-b border-slate-800 pb-5">
          <div className="flex items-center gap-3">
            <Building2 className="size-7 text-cyan-400" />
            <div>
              <p className="font-semibold">Wakaltcom ERP</p>
              <p className="text-xs text-slate-400">{user.agency_name}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setMobileNavOpen(false)}
            className="rounded-lg p-2 text-slate-300 hover:bg-slate-800 md:hidden"
          >
            <X className="size-5" />
            <span className="sr-only">{locale === "ar" ? "إغلاق القائمة" : "Close menu"}</span>
          </button>
        </div>
        <button
          type="button"
          onClick={toggleLocale}
          className="mt-4 flex w-full items-center justify-between rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800"
        >
          <span className="inline-flex items-center gap-2">
            <Languages className="size-4" />
            {locale === "ar" ? "اللغة" : "Language"}
          </span>
          <span className="font-semibold">{locale === "ar" ? "EN" : "AR"}</span>
        </button>
        <nav className="mt-6 space-y-1">
          {navigation.map(({ label, href, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setMobileNavOpen(false)}
              className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-300 hover:bg-slate-800 hover:text-white"
            >
              <Icon className="size-4" />
              <span className="flex-1">{label[locale]}</span>
              {href === "/transport" &&
                (transport.data?.counts.today ?? 0) > 0 && (
                  <span
                    title={locale === "ar" ? "رحلات النقل اليوم" : "Transport today"}
                    className="grid min-w-5 place-items-center rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-semibold text-white"
                  >
                    {transport.data?.counts.today}
                  </span>
                )}
              {href === "/transport" &&
                (transport.data?.counts.total ?? 0) -
                  (transport.data?.counts.today ?? 0) >
                  0 && (
                  <span
                    title={locale === "ar" ? "رحلات النقل القادمة" : "Future transports"}
                    className="grid min-w-5 place-items-center rounded-full bg-cyan-500 px-1.5 py-0.5 text-[10px] font-semibold text-white"
                  >
                    {(transport.data?.counts.total ?? 0) -
                      (transport.data?.counts.today ?? 0)}
                  </span>
                )}
            </Link>
          ))}
        </nav>
      </aside>
      <div className={`${isRtl ? "md:col-start-1" : "md:col-start-2"} md:row-start-1`}>
        <header className="no-print flex min-h-16 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 sm:px-6">
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50 md:hidden"
          >
            <Menu className="size-5" />
            <span className="sr-only">{locale === "ar" ? "فتح القائمة" : "Open menu"}</span>
          </button>
          <p className="min-w-0 flex-1 truncate text-sm text-slate-500">
            {user.branch_name ?? (locale === "ar" ? "كل الفروع" : "All branches")}
          </p>
          <div className="flex items-center gap-3">
            <NotificationCenter />
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium">
                {user.first_name || user.email}
              </p>
              <p className="text-xs text-slate-500">
                {user.role_names.join(locale === "ar" ? "، " : ", ") ||
                  (locale === "ar" ? "مستخدم" : "User")}
              </p>
            </div>
            <button
              type="button"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              title={locale === "ar" ? "تسجيل الخروج" : "Log out"}
              className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-50 hover:text-red-700 disabled:opacity-50"
            >
              <LogOut className="size-4" />
              <span className="sr-only">{locale === "ar" ? "تسجيل الخروج" : "Log out"}</span>
            </button>
          </div>
        </header>
        <main className="p-4 sm:p-6 md:p-8 print:p-0">{children}</main>
      </div>
    </div>
  );
}
