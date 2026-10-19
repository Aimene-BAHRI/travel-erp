"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Banknote,
  LoaderCircle,
  Plus,
} from "lucide-react";
import { useState } from "react";

import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type {
  AgencyCurrency,
  Paginated,
  PaymentMethod,
} from "@/features/reference/types";
import type { TripRecord } from "@/features/trips/types";
import { apiRequest } from "@/lib/api/client";

import type { CashFlowReport, CashEntry, CashEntryCategory } from "./types";

type Branch = { id: string; name: string };
type Draft = {
  branch: string;
  trip: string;
  direction: "IN" | "OUT";
  category: CashEntryCategory;
  description: string;
  recipient_name: string;
  amount: string;
  currency: string;
  source_amount: string;
  source_currency: string;
  exchange_rate: string;
  payment_method: string;
  entry_date: string;
  reference: string;
  notes: string;
};

const categories: Array<{ value: CashEntryCategory; label: string }> = [
  { value: "OTHER_INCOME", label: "Other income" },
  { value: "OWNER_FUNDS", label: "Owner funds" },
  { value: "OPERATING_COST", label: "Operating cost" },
  { value: "TAX", label: "Tax" },
  { value: "SALARY", label: "Salary" },
  { value: "TRANSFER", label: "Transfer" },
  { value: "TRIP_ADVANCE", label: "Trip advance" },
  { value: "OTHER_EXPENSE", label: "Other expense" },
];

const emptyDraft: Draft = {
  branch: "",
  trip: "",
  direction: "OUT",
  category: "OPERATING_COST",
  description: "",
  recipient_name: "",
  amount: "",
  currency: "",
  source_amount: "",
  source_currency: "",
  exchange_rate: "",
  payment_method: "",
  entry_date: new Date().toISOString().slice(0, 10),
  reference: "",
  notes: "",
};

function amount(value: string | number) {
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function CashFlowWorkspace() {
  const uiText = useUiText();
  const cache = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [trip, setTrip] = useState("");
  const [currency, setCurrency] = useState("");
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const report = useQuery({
    queryKey: ["cash-flow-report", trip],
    queryFn: () =>
      apiRequest<CashFlowReport>(
        `/finance/cash-entries/report/${trip ? `?trip=${trip}` : ""}`,
      ),
  });
  const trips = useQuery({
    queryKey: ["cash-flow-trips"],
    queryFn: () =>
      apiRequest<Paginated<TripRecord>>("/trips/?ordering=-departure_date"),
  });
  const branches = useQuery({
    queryKey: ["branches"],
    queryFn: () => apiRequest<Paginated<Branch>>("/organizations/branches/"),
  });
  const currencies = useQuery({
    queryKey: ["agency-currencies"],
    queryFn: () =>
      apiRequest<Paginated<AgencyCurrency>>("/reference/agency-currencies/"),
  });
  const methods = useQuery({
    queryKey: ["payment-methods"],
    queryFn: () =>
      apiRequest<Paginated<PaymentMethod>>("/reference/payment-methods/"),
  });
  const post = useMutation({
    mutationFn: () =>
      apiRequest<CashEntry>(editingId ? `/finance/cash-entries/${editingId}/` : "/finance/cash-entries/post/", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify({
          ...draft,
          trip: draft.trip || null,
          source_amount: draft.source_amount || null,
          source_currency: draft.source_currency || null,
          exchange_rate: draft.exchange_rate || null,
        }),
      }),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["cash-flow-report"] });
      setOpen(false);
      setDraft(emptyDraft);
    },
  });

  const editEntry = useMutation({
    mutationFn: (id: string) => apiRequest<Draft>(`/finance/cash-entries/${id}/`),
    onSuccess: (entry, id) => {
      const next = { ...emptyDraft };
      for (const key of Object.keys(next) as Array<keyof Draft>) {
        (next as Record<string, string>)[key] = String(entry[key] ?? "");
      }
      setDraft(next);
      setEditingId(id);
      post.reset();
      setOpen(true);
    },
  });
  const removeEntry = useMutation({
    mutationFn: (id: string) => apiRequest(`/finance/cash-entries/${id}/`, { method: "DELETE" }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["cash-flow-report"] }),
  });

  const totals = Object.entries(report.data?.totals_by_currency ?? {}).filter(
    ([code]) => !currency || code === currency,
  );
  const entries = (report.data?.entries ?? []).filter(
    (entry) => !currency || entry.currency === currency,
  );
  const openEntry = () => {
    setEditingId(null);
    const defaultCurrency =
      currencies.data?.results.find((item) => item.is_accounting)?.currency ??
      currencies.data?.results.find((item) => item.is_enabled)?.currency ??
      "";
    setDraft({
      ...emptyDraft,
      currency: defaultCurrency,
      branch: branches.data?.results[0]?.id ?? "",
      payment_method: methods.data?.results[0]?.id ?? "",
      trip,
    });
    post.reset();
    setOpen(true);
  };

  if (report.isPending)
    return (
      <div className="grid min-h-72 place-items-center">
        <LoaderCircle className="size-8 animate-spin text-cyan-800" />
      </div>
    );
  if (report.isError || !report.data)
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
        {uiText(
          "The cash-flow report could not be loaded. Please refresh and try again.",
        )}
      </div>
    );

  return (
    <>
      <div className="space-y-6">
        <section className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="grid flex-1 gap-3 sm:grid-cols-2">
            <Field label={uiText("Trip")}>
              <select
                className="input"
                value={trip}
                onChange={(event) => setTrip(event.target.value)}
              >
                <option value="">{uiText("All agency cash flow")}</option>
                {trips.data?.results.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.code} · {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={uiText("Currency")}>
              <select
                className="input"
                value={currency}
                onChange={(event) => setCurrency(event.target.value)}
              >
                <option value="">{uiText("All currencies")}</option>
                {Object.keys(report.data.totals_by_currency).map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <button
            type="button"
            onClick={openEntry}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-900"
          >
            <Plus className="size-4" />
            {uiText("Add cash entry")}
          </button>
        </section>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {totals.length ? (
            totals.map(([code, value]) => (
              <div
                key={code}
                className="rounded-xl border border-slate-200 bg-white p-5"
              >
                <div className="flex items-center justify-between">
                  <p className="font-semibold">{code}</p>
                  <Banknote className="size-5 text-cyan-700" />
                </div>
                <div className="mt-5 grid grid-cols-3 gap-3 text-sm">
                  <Metric
                    label={uiText("Inflow")}
                    value={amount(value.inflow)}
                    tone="text-emerald-700"
                  />
                  <Metric
                    label={uiText("Outflow")}
                    value={amount(value.outflow)}
                    tone="text-rose-700"
                  />
                  <Metric
                    label={uiText("Net")}
                    value={amount(value.net)}
                    tone={
                      Number(value.net) >= 0 ? "text-cyan-900" : "text-rose-700"
                    }
                  />
                </div>
              </div>
            ))
          ) : (
            <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 sm:col-span-2 xl:col-span-3">
              {uiText("No cash movement has been recorded yet.")}
            </p>
          )}
        </section>

        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <header className="flex items-center justify-between border-b border-slate-200 p-5">
            <div>
              <h2 className="flex items-center gap-2 font-semibold">
                <Banknote className="size-5 text-cyan-700" />
                {uiText("Cash ledger")}
              </h2>
              <p className="text-sm text-slate-500">
                {uiText(
                  "Booking receipts, supplier payments, and manual entries.",
                )}
              </p>
            </div>
            <span className="text-sm text-slate-500">
              {entries.length} {uiText("entries")}
            </span>
          </header>
          <MutationMessage error={editEntry.error || removeEntry.error} />
          {entries.length ? (
            <div className="divide-y divide-slate-100">
              {entries.map((entry) => (
                <div
                  key={entry.id}
                  className="grid gap-3 p-5 md:grid-cols-[auto_1fr_auto_auto] md:items-center"
                >
                  <span
                    className={`grid size-9 place-items-center rounded-full ${Number(entry.amount) >= 0 ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}
                  >
                    {Number(entry.amount) >= 0 ? (
                      <ArrowDownLeft className="size-4" />
                    ) : (
                      <ArrowUpRight className="size-4" />
                    )}
                  </span>
                  <div>
                    <p className="font-medium">{entry.description}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {entry.number} · {entry.date} · {uiText(entry.kind)}
                      {entry.recipient_name ? ` · ${entry.recipient_name}` : ""}
                    </p>
                    {entry.source_amount && entry.source_currency ? (
                      <p className="mt-1 text-xs text-slate-500">
                        {uiText("Converted from")} {entry.source_amount}{" "}
                        {entry.source_currency}
                        {entry.exchange_rate
                          ? ` · ${uiText("rate")} ${entry.exchange_rate}`
                          : ""}
                      </p>
                    ) : null}
                  </div>
                  <p
                    className={`text-end font-semibold ${Number(entry.amount) >= 0 ? "text-emerald-700" : "text-rose-700"}`}
                  >
                    {Number(entry.amount) >= 0 ? "+" : "−"}
                    {amount(Math.abs(Number(entry.amount)))} {entry.currency}
                  </p>
                  <div className="flex justify-end gap-3 text-sm">
                    {entry.editable ? <>
                      <button className="text-cyan-800 underline" disabled={editEntry.isPending || removeEntry.isPending} onClick={() => editEntry.mutate(entry.id)}>{uiText("Edit")}</button>
                      <button className="text-red-700 underline" disabled={removeEntry.isPending} onClick={() => {
                        if (window.confirm(uiText("Delete this cash entry? Its amount will be reversed."))) removeEntry.mutate(entry.id);
                      }}>{uiText("Delete")}</button>
                    </> : entry.manage_url ? <a className="text-cyan-800 underline" href={entry.manage_url}>{uiText("Manage payment")}</a> : <span className="text-slate-500">{uiText("Reversed entry")}</span>}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="p-10 text-center text-sm text-slate-500">
              {uiText("No entries match the selected filters.")}
            </p>
          )}
        </section>
      </div>

      <FormDialog
        open={open}
        onClose={() => setOpen(false)}
        title={uiText(editingId ? "Edit cash entry" : "Add cash entry")}
        description={uiText("Record money entering or leaving the agency.")}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            post.mutate();
          }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={uiText("Direction")}>
              <select
                className="input"
                value={draft.direction}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    direction: event.target.value as Draft["direction"],
                  })
                }
              >
                <option value="OUT">{uiText("Money out")}</option>
                <option value="IN">{uiText("Money in")}</option>
              </select>
            </Field>
            <Field label={uiText("Category")}>
              <select
                className="input"
                value={draft.category}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    category: event.target.value as CashEntryCategory,
                  })
                }
              >
                {categories.map((item) => (
                  <option key={item.value} value={item.value}>
                    {uiText(item.label)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={uiText("Description")} wide>
              <input
                required
                className="input"
                value={draft.description}
                onChange={(event) =>
                  setDraft({ ...draft, description: event.target.value })
                }
              />
            </Field>
            <Field label={uiText("Recipient")}>
              <input
                className="input"
                placeholder={uiText("Guide or responsible person")}
                value={draft.recipient_name}
                onChange={(event) =>
                  setDraft({ ...draft, recipient_name: event.target.value })
                }
              />
            </Field>
            <Field label={uiText("Amount")}>
              <input
                required
                min="0.0001"
                step="0.0001"
                type="number"
                className="input"
                value={draft.amount}
                onChange={(event) =>
                  setDraft({ ...draft, amount: event.target.value })
                }
              />
            </Field>
            <Field label={uiText("Currency")}>
              <select
                required
                className="input"
                value={draft.currency}
                onChange={(event) =>
                  setDraft({ ...draft, currency: event.target.value })
                }
              >
                {currencies.data?.results
                  .filter((item) => item.is_enabled)
                  .map((item) => (
                    <option key={item.id} value={item.currency}>
                      {item.currency} · {item.currency_name}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label={uiText("Converted from currency")}>
              <select
                className="input"
                value={draft.source_currency}
                onChange={(event) =>
                  setDraft({ ...draft, source_currency: event.target.value })
                }
              >
                <option value="">{uiText("No conversion")}</option>
                {currencies.data?.results
                  .filter(
                    (item) =>
                      item.is_enabled && item.currency !== draft.currency,
                  )
                  .map((item) => (
                    <option key={item.id} value={item.currency}>
                      {item.currency} · {item.currency_name}
                    </option>
                  ))}
              </select>
            </Field>
            {draft.source_currency ? (
              <>
                <Field label={uiText("Source amount")}>
                  <input
                    required
                    min="0.0001"
                    step="0.0001"
                    type="number"
                    className="input"
                    value={draft.source_amount}
                    onChange={(event) =>
                      setDraft({ ...draft, source_amount: event.target.value })
                    }
                  />
                </Field>
                <Field label={uiText("Exchange rate")}>
                  <input
                    required
                    min="0.00000001"
                    step="0.00000001"
                    type="number"
                    className="input"
                    value={draft.exchange_rate}
                    onChange={(event) =>
                      setDraft({ ...draft, exchange_rate: event.target.value })
                    }
                  />
                </Field>
              </>
            ) : null}
            <Field label={uiText("Payment method")}>
              <select
                required
                className="input"
                value={draft.payment_method}
                onChange={(event) =>
                  setDraft({ ...draft, payment_method: event.target.value })
                }
              >
                {methods.data?.results.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={uiText("Branch")}>
              <select
                required
                className="input"
                value={draft.branch}
                onChange={(event) =>
                  setDraft({ ...draft, branch: event.target.value })
                }
              >
                {branches.data?.results.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={uiText("Trip")}>
              <select
                className="input"
                value={draft.trip}
                onChange={(event) =>
                  setDraft({ ...draft, trip: event.target.value })
                }
              >
                <option value="">{uiText("Agency-wide")}</option>
                {trips.data?.results.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.code} · {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={uiText("Entry date")}>
              <input
                required
                type="date"
                className="input"
                value={draft.entry_date}
                onChange={(event) =>
                  setDraft({ ...draft, entry_date: event.target.value })
                }
              />
            </Field>
            <Field label={uiText("Reference")}>
              <input
                className="input"
                value={draft.reference}
                onChange={(event) =>
                  setDraft({ ...draft, reference: event.target.value })
                }
              />
            </Field>
            <Field label={uiText("Notes")} wide>
              <textarea
                className="input"
                value={draft.notes}
                onChange={(event) =>
                  setDraft({ ...draft, notes: event.target.value })
                }
              />
            </Field>
          </div>
          <MutationMessage error={post.error} />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-lg border px-4 py-2"
            >
              {uiText("Cancel")}
            </button>
            <button
              disabled={post.isPending}
              className="rounded-lg bg-cyan-800 px-4 py-2 text-white disabled:opacity-50"
            >
              {post.isPending ? uiText("Saving...") : uiText(editingId ? "Save changes" : "Post entry")}
            </button>
          </div>
        </form>
      </FormDialog>
    </>
  );
}

function Field({
  label,
  wide,
  children,
}: Readonly<{ label: string; wide?: boolean; children: React.ReactNode }>) {
  return (
    <label className={`text-sm font-medium ${wide ? "sm:col-span-2" : ""}`}>
      {label}
      <div className="mt-1 [&_.input]:w-full [&_.input]:rounded-lg [&_.input]:border [&_.input]:border-slate-300 [&_.input]:px-3 [&_.input]:py-2">
        {children}
      </div>
    </label>
  );
}
function Metric({
  label,
  value,
  tone,
}: Readonly<{ label: string; value: string; tone: string }>) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-1 font-semibold ${tone}`}>{value}</p>
    </div>
  );
}
