"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { CurrentUser } from "@/features/auth/types";
import type { Paginated } from "@/features/reference/types";

type Staff = { id: string; email: string; first_name: string; last_name: string; branch: string | null; branch_name: string | null; role_ids: string[]; role_names: string[]; is_active: boolean; protected_account: boolean; effective_permissions: string[] };
type Role = { id: string; name: string; code: string; description: string; permission_ids: number[]; is_active: boolean };
type Permission = { id: number; app_label: string; codename: string; name: string };
type Branch = { id: string; name: string; is_active: boolean };
const input = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm";
const button = "rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-40";

async function all<T>(path: string): Promise<T[]> {
  let next: string | null = path;
  const records: T[] = [];
  while (next) {
    const page: Paginated<T> = await apiRequest(next);
    records.push(...page.results);
    next = page.next ? path.split("?")[0] + new URL(page.next, "http://localhost").search : null;
  }
  return records;
}

export function AccessManagement({ user }: { user: CurrentUser }) {
  const { locale } = useLocale();
  const t = (en: string, ar: string) => locale === "ar" ? ar : en;
  const can = (permission: string) => user.permissions.includes(`accounts.${permission}`);
  const cache = useQueryClient();
  const [tab, setTab] = useState("users");
  const [search, setSearch] = useState("");
  const [branchFilter, setBranchFilter] = useState("all");
  const [person, setPerson] = useState<Partial<Staff> & { password?: string } | null>(null);
  const [role, setRole] = useState<Partial<Role> | null>(null);
  const users = useQuery({ queryKey: ["access-users"], queryFn: () => all<Staff>("/accounts/users/"), enabled: can("view_user") });
  const roles = useQuery({ queryKey: ["access-roles"], queryFn: () => all<Role>("/accounts/roles/"), enabled: can("view_role") });
  const permissions = useQuery({ queryKey: ["access-permissions"], queryFn: () => all<Permission>("/accounts/permissions/"), enabled: can("view_role") });
  const branches = useQuery({ queryKey: ["access-branches"], queryFn: () => all<Branch>("/organizations/branches/"), enabled: can("view_user") });
  const refresh = () => { cache.invalidateQueries({ queryKey: ["access-users"] }); cache.invalidateQueries({ queryKey: ["access-roles"] }); };
  const saveUser = useMutation({ mutationFn: () => apiRequest(`/accounts/users/${person?.id ? `${person.id}/` : ""}`, {
    method: person?.id ? "PATCH" : "POST", body: JSON.stringify({ email: person?.email, first_name: person?.first_name, last_name: person?.last_name, branch: person?.branch || null, role_ids: person?.role_ids, is_active: person?.is_active, ...(person?.password ? { password: person.password } : {}) }),
  }), onSuccess: () => { setPerson(null); refresh(); } });
  const saveRole = useMutation({ mutationFn: () => apiRequest(`/accounts/roles/${role?.id ? `${role.id}/` : ""}`, {
    method: role?.id ? "PATCH" : "POST", body: JSON.stringify(role),
  }), onSuccess: () => { setRole(null); refresh(); } });
  const allowedIds = new Set(permissions.data?.map(p => p.id));
  const assignable = roles.data?.filter(r => r.is_active && r.code !== "agency-owner" && r.permission_ids.every(id => allowedIds.has(id))) ?? [];
  const list = users.data?.filter(p => `${p.first_name} ${p.last_name} ${p.email}`.toLowerCase().includes(search.toLowerCase()) && (branchFilter === "all" || (p.branch ?? "agency") === branchFilter)) ?? [];
  const grouped = Object.groupBy(permissions.data ?? [], p => p.app_label);
  return <section className="space-y-5">
    <header className="rounded-xl border bg-white p-5"><h2 className="text-xl font-semibold">{t("Users, roles & access", "المستخدمون والأدوار والصلاحيات")}</h2>
      <p className="mt-2 text-sm text-slate-600">{user.agency_name} · {t("Manage access within this agency and its branches.", "إدارة الوصول داخل هذه الوكالة وفروعها.")}</p>
      <p className="mt-2 text-sm text-slate-500">{t("Roles define permitted actions. A branch limits the records a user can work with; “view all” permissions can expand visibility across branches. Agency-level users have no branch restriction. Users cannot access another agency.", "تحدد الأدوار الإجراءات المسموحة. يقيد الفرع السجلات المتاحة؛ ويمكن لصلاحيات عرض الكل توسيع الرؤية بين الفروع. مستخدم الوكالة غير مقيد بفرع. لا يمكن الوصول إلى وكالة أخرى.")}</p>
    </header>
    <nav className="flex gap-2">{[["users", t("Users", "المستخدمون")], ["roles", t("Roles & permissions", "الأدوار والصلاحيات")]].map(([key, label]) => <button key={key} onClick={() => setTab(key)} aria-pressed={tab === key} className={tab === key ? button : "rounded-lg border bg-white px-4 py-2 text-sm"}>{label}</button>)}</nav>
    <MutationMessage error={users.error || roles.error || permissions.error || branches.error} />
    {tab === "users" ? !can("view_user") ? <p>{t("You do not have permission to view users.", "لا تملك صلاحية عرض المستخدمين.")}</p> : <div className="rounded-xl border bg-white p-5">
      <div className="mb-5 flex flex-wrap gap-3"><input aria-label={t("Search users", "بحث المستخدمين")} placeholder={t("Search name or email", "البحث بالاسم أو البريد")} value={search} onChange={e => setSearch(e.target.value)} className="rounded-lg border px-3 py-2 text-sm" />
        <select aria-label={t("Filter branch", "تصفية الفرع")} value={branchFilter} onChange={e => setBranchFilter(e.target.value)} className="rounded-lg border px-3 py-2 text-sm"><option value="all">{t("All visible branches", "كل الفروع المتاحة")}</option><option value="agency">{t("Agency-level", "مستوى الوكالة")}</option>{branches.data?.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select>
        {can("add_user") && <button className={button} onClick={() => { saveUser.reset(); setPerson({ email: "", first_name: "", last_name: "", branch: user.branch, role_ids: [], is_active: true, password: "" }); }}>{t("Add user", "إضافة مستخدم")}</button>}
      </div>
      {users.isPending ? <p>{t("Loading users…", "جار تحميل المستخدمين…")}</p> : <div className="overflow-x-auto"><table className="w-full text-start text-sm"><thead><tr>{[t("User", "المستخدم"), t("Scope", "النطاق"), t("Roles", "الأدوار"), t("Status", "الحالة"), t("Manage", "إدارة")].map(label => <th key={label} className="border-b p-3 text-start">{label}</th>)}</tr></thead><tbody>{list.map(p => <tr key={p.id}>
        <td className="border-b p-3"><p className="font-medium">{`${p.first_name} ${p.last_name}`.trim() || p.email}</p><p className="text-xs text-slate-500">{p.email}</p></td><td className="border-b p-3">{p.branch_name || t("Agency-level", "مستوى الوكالة")}</td><td className="border-b p-3">{p.role_names.join(", ") || "—"}<details className="mt-2"><summary className="cursor-pointer text-cyan-800">{t("View access", "عرض الصلاحيات")} ({p.effective_permissions.length})</summary><ul className="mt-2 max-h-48 overflow-y-auto text-xs">{p.effective_permissions.map(key => <li key={key} className="py-1">{permissions.data?.find(x => `${x.app_label}.${x.codename}` === key)?.name || key}</li>)}</ul></details></td><td className="border-b p-3">{p.is_active ? t("Active", "نشط") : t("Inactive", "غير نشط")}</td>
        <td className="border-b p-3">{p.protected_account || p.id === user.id ? <span className="text-xs text-slate-500">{t("Protected account", "حساب محمي")}</span> : can("change_user") && <button className="text-cyan-800 underline" onClick={() => { saveUser.reset(); setPerson({ ...p, password: "" }); }}>{t("Edit", "تعديل")}</button>}</td>
      </tr>)}</tbody></table>{!list.length && <p className="p-5 text-slate-500">{t("No users found.", "لا يوجد مستخدمون.")}</p>}</div>}
    </div> : !can("view_role") ? <p>{t("You do not have permission to view roles.", "لا تملك صلاحية عرض الأدوار.")}</p> : <div className="space-y-4">
      {!user.branch && can("add_role") && <button className={button} onClick={() => { saveRole.reset(); setRole({ name: "", code: "", description: "", permission_ids: [], is_active: true }); }}>{t("Create role", "إنشاء دور")}</button>}
      {roles.isPending && <p>{t("Loading roles…", "جار تحميل الأدوار…")}</p>}
      {roles.data?.map(r => <article key={r.id} className="rounded-xl border bg-white p-5"><div className="flex justify-between gap-3"><div><h3 className="font-semibold">{r.name} · {r.is_active ? t("Active", "نشط") : t("Inactive", "غير نشط")}</h3><p className="mt-1 text-sm text-slate-500">{r.description}</p></div>{!user.branch && can("change_role") && r.code !== "agency-owner" && !user.role_names.includes(r.name) && <button className="text-sm text-cyan-800 underline" onClick={() => { saveRole.reset(); setRole({ ...r }); }}>{t("Edit", "تعديل")}</button>}</div><details className="mt-3 text-sm"><summary className="cursor-pointer">{r.permission_ids.length} {t("permissions", "صلاحية")}</summary><ul className="mt-2 grid gap-1 sm:grid-cols-2">{r.permission_ids.map(id => <li key={id}>{permissions.data?.find(p => p.id === id)?.name || t("Permission outside your delegation scope", "صلاحية خارج نطاق التفويض المتاح لك")}</li>)}</ul></details></article>)}
    </div>}
    <FormDialog open={!!person} title={person?.id ? t("Edit user", "تعديل المستخدم") : t("Add user", "إضافة مستخدم")} onClose={() => setPerson(null)}>
      {person && <form className="space-y-4" onSubmit={e => { e.preventDefault(); saveUser.mutate(); }}>
        {([['email', t('Email', 'البريد الإلكتروني')], ['first_name', t('First name', 'الاسم')], ['last_name', t('Last name', 'اللقب')]] as const).map(([key, label]) => <label key={key} className="block text-sm">{label}<input className={input} required={key === "email"} type={key === "email" ? "email" : "text"} value={person[key] || ""} onChange={e => setPerson({ ...person, [key]: e.target.value })} /></label>)}
        <label className="block text-sm">{t("Branch scope", "نطاق الفرع")}<select className={input} disabled={!!user.branch} value={person.branch || ""} onChange={e => setPerson({ ...person, branch: e.target.value || null })}>{!user.branch && <option value="">{t("Agency-level — all branches", "مستوى الوكالة — كل الفروع")}</option>}{branches.data?.filter(b => !user.branch || b.id === user.branch).map(b => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
        <fieldset><legend className="text-sm font-medium">{t("Assigned roles", "الأدوار المسندة")}</legend>{assignable.map(r => <label key={r.id} className="mt-2 flex gap-2 text-sm"><input type="checkbox" checked={person.role_ids?.includes(r.id) ?? false} onChange={e => setPerson({ ...person, role_ids: e.target.checked ? [...(person.role_ids ?? []), r.id] : person.role_ids?.filter(id => id !== r.id) })} />{r.name}</label>)}{!assignable.length && <p className="text-xs text-slate-500">{t("No assignable roles. An agency administrator must create an appropriate role first.", "لا توجد أدوار قابلة للإسناد. يجب إنشاء دور مناسب بواسطة مدير الوكالة.")}</p>}</fieldset>
        <label className="block text-sm">{person.id ? t("New password (leave blank to keep current)", "كلمة مرور جديدة (اتركها فارغة للإبقاء على الحالية)") : t("Initial password", "كلمة المرور الأولية")}<input className={input} type="password" autoComplete="new-password" minLength={10} required={!person.id} value={person.password || ""} onChange={e => setPerson({ ...person, password: e.target.value })} /></label>
        <label className="flex gap-2 text-sm"><input type="checkbox" checked={person.is_active} onChange={e => setPerson({ ...person, is_active: e.target.checked })} />{t("Active — can sign in", "نشط — يمكنه تسجيل الدخول")}</label>
        <MutationMessage error={saveUser.error} /><button disabled={saveUser.isPending} className={button}>{t("Save user", "حفظ المستخدم")}</button>
      </form>}
    </FormDialog>
    <FormDialog open={!!role} title={t("Role permissions", "صلاحيات الدور")} onClose={() => setRole(null)}>{role && <form className="space-y-4" onSubmit={e => { e.preventDefault(); saveRole.mutate(); }}>
      {([['name', t('Role name', 'اسم الدور')], ['code', t('Role code', 'رمز الدور')], ['description', t('Description', 'الوصف')]] as const).map(([key, label]) => <label key={key} className="block text-sm">{label}<input required={key !== 'description'} pattern={key === 'code' ? '[a-zA-Z0-9_-]+' : undefined} value={role[key] || ""} className={input} onChange={e => setRole({ ...role, [key]: e.target.value })} /></label>)}
      <label className="flex gap-2 text-sm"><input type="checkbox" checked={role.is_active} onChange={e => setRole({ ...role, is_active: e.target.checked })} />{t("Role active", "الدور نشط")}</label>
      <p className="text-sm text-slate-500">{t("Changes affect every user assigned this role. Only permissions you can delegate are listed.", "تؤثر التغييرات على كل المستخدمين المسند إليهم الدور. تعرض فقط الصلاحيات التي يمكنك تفويضها.")}</p>
      <div className="max-h-80 space-y-3 overflow-y-auto rounded-lg border p-3">{Object.entries(grouped).map(([app, items]) => <fieldset key={app}><legend className="mb-2 font-semibold capitalize">{app}</legend>{items?.map(p => <label key={p.id} className="mb-2 flex gap-2 text-sm"><input type="checkbox" checked={role.permission_ids?.includes(p.id) ?? false} onChange={e => setRole({ ...role, permission_ids: e.target.checked ? [...(role.permission_ids ?? []), p.id] : role.permission_ids?.filter(id => id !== p.id) })} />{p.name}</label>)}</fieldset>)}</div>
      <MutationMessage error={saveRole.error} /><button disabled={saveRole.isPending || !permissions.data} className={button}>{t("Save role", "حفظ الدور")}</button>
    </form>}</FormDialog>
  </section>;
}
