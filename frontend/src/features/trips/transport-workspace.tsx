"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bus,
  CalendarDays,
  Clock3,
  Pencil,
  LoaderCircle,
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { Paginated } from "@/features/reference/types";
import type { SupplierRecord } from "@/features/catalog/types";
import { apiRequest } from "@/lib/api/client";

import type { TransportOverview, TransportRecord } from "./transport-types";
import type { TripRecord } from "./types";

const dateFormatter = new Intl.DateTimeFormat("en", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});
const timeFormatter = new Intl.DateTimeFormat("en", {
  hour: "2-digit",
  minute: "2-digit",
});

function date(value: string) {
  return dateFormatter.format(new Date(value));
}

function time(value: string) {
  return timeFormatter.format(new Date(value));
}

function isToday(value: string) {
  return new Date(value).toDateString() === new Date().toDateString();
}

type TransportDraft = {
  trip: string;
  mode: TransportRecord["mode"];
  supplier: string;
  origin_city: string;
  destination_city: string;
  departure_at: string;
  arrival_at: string;
  reference: string;
  vehicle_details: string;
  vehicle_number: string;
  order: number;
  notes: string;
};
type City = { id: string; name: string };

const emptyDraft: TransportDraft = {
  trip: "",
  mode: "BUS",
  supplier: "",
  origin_city: "",
  destination_city: "",
  departure_at: "",
  arrival_at: "",
  reference: "",
  vehicle_details: "",
  vehicle_number: "",
  order: 1,
  notes: "",
};

function toLocalDateTime(value: string) {
  return value ? new Date(value).toISOString().slice(0, 16) : "";
}

export function TransportWorkspace() {
  const uiText = useUiText();
  const cache = useQueryClient();
  const [scope, setScope] = useState<"upcoming" | "all">("upcoming");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<TransportRecord | null>(null);
  const [draft, setDraft] = useState<TransportDraft>(emptyDraft);
  const overview = useQuery({
    queryKey: ["transport-overview", scope],
    queryFn: () =>
      apiRequest<TransportOverview>(
        `/trips/transports/overview/?scope=${scope}`,
      ),
  });
  const trips = useQuery({
    queryKey: ["transport-trips"],
    queryFn: () =>
      apiRequest<Paginated<TripRecord>>("/trips/?ordering=departure_date"),
  });
  const cities = useQuery({
    queryKey: ["transport-cities"],
    queryFn: () =>
      apiRequest<Paginated<City>>("/reference/cities/?ordering=name"),
  });
  const suppliers = useQuery({
    queryKey: ["transport-suppliers"],
    queryFn: () =>
      apiRequest<Paginated<SupplierRecord>>(
        "/catalog/suppliers/?ordering=name",
      ),
  });
  const save = useMutation({
    mutationFn: () =>
      apiRequest<TransportRecord>(
        editing ? `/trips/transports/${editing.id}/` : "/trips/transports/",
        {
          method: editing ? "PATCH" : "POST",
          body: JSON.stringify({ ...draft, supplier: draft.supplier || null }),
        },
      ),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["transport-overview"] });
      cache.invalidateQueries({ queryKey: ["trip-transports"] });
      setFormOpen(false);
      setEditing(null);
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) =>
      apiRequest<void>(`/trips/transports/${id}/`, { method: "DELETE" }),
    onSuccess: () =>
      cache.invalidateQueries({ queryKey: ["transport-overview"] }),
  });

  const openCreate = () => {
    setEditing(null);
    setDraft({
      ...emptyDraft,
      trip: trips.data?.results[0]?.id ?? "",
      origin_city: cities.data?.results[0]?.id ?? "",
      destination_city: cities.data?.results[1]?.id ?? "",
      supplier: suppliers.data?.results[0]?.id ?? "",
    });
    save.reset();
    setFormOpen(true);
  };
  const openEdit = (item: TransportRecord) => {
    setEditing(item);
    setDraft({
      trip: item.trip,
      mode: item.mode,
      supplier: item.supplier ?? "",
      origin_city: item.origin_city,
      destination_city: item.destination_city,
      departure_at: toLocalDateTime(item.departure_at),
      arrival_at: toLocalDateTime(item.arrival_at),
      reference: item.reference,
      vehicle_details: item.vehicle_details,
      vehicle_number: item.vehicle_number,
      order: item.order,
      notes: item.notes,
    });
    save.reset();
    setFormOpen(true);
  };
  if (overview.isPending)
    return (
      <div className="grid min-h-72 place-items-center">
        <LoaderCircle className="size-8 animate-spin text-cyan-800" />
      </div>
    );
  if (overview.isError || !overview.data)
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
        {uiText(
          "The transport schedule could not be loaded. Please refresh and try again.",
        )}
      </div>
    );
  const { counts, results } = overview.data;
  return (
    <div className="space-y-6">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Stat
          label={uiText("Urgent · next 3 days")}
          value={counts.urgent}
          icon={AlertTriangle}
          tone="amber"
        />
        <Stat
          label={uiText("Today")}
          value={counts.today}
          icon={Clock3}
          tone="rose"
        />
        <Stat
          label={uiText("This week")}
          value={counts.week}
          icon={CalendarDays}
          tone="cyan"
        />
        <Stat
          label={uiText("This month")}
          value={counts.month}
          icon={CalendarDays}
          tone="emerald"
        />
        <Stat
          label={uiText("Total upcoming")}
          value={counts.total}
          icon={Bus}
          tone="slate"
        />
      </section>

      <section className="rounded-xl border border-slate-200 bg-white">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-5">
          <div>
            <h2 className="font-semibold">
              {uiText(
                scope === "all" ? "All transports" : "Upcoming transport",
              )}
            </h2>
            <p className="text-sm text-slate-500">
              {uiText(
                scope === "all"
                  ? "Every scheduled transport leg across your trips."
                  : "Every scheduled transport leg requiring follow-up.",
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-lg border border-slate-200 p-1">
              {(["upcoming", "all"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setScope(option)}
                  className={`rounded-md px-3 py-1.5 text-sm ${scope === option ? "bg-cyan-800 text-white" : "text-slate-600 hover:bg-slate-50"}`}
                >
                  {uiText(option === "all" ? "All" : "Upcoming")}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={openCreate}
              className="inline-flex items-center gap-2 rounded-lg bg-cyan-800 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-900"
            >
              <Plus className="size-4" />
              {uiText("Add transport")}
            </button>
          </div>
        </header>
        {results.length ? (
          <div className="grid gap-4 p-5 xl:grid-cols-2">
            {results.map((item) => (
              <TransportCard
                key={item.id}
                item={item}
                onEdit={() => openEdit(item)}
                onDelete={() => remove.mutate(item.id)}
              />
            ))}
          </div>
        ) : (
          <p className="p-10 text-center text-sm text-slate-500">
            {uiText(
              scope === "all"
                ? "No transport has been scheduled."
                : "No upcoming transport has been scheduled.",
            )}
          </p>
        )}
      </section>
      <FormDialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? uiText("Edit transport") : uiText("Add transport")}
        description={uiText("Schedule a transport leg for a trip.")}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
          className="space-y-4"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={uiText("Trip")} wide>
              <select
                required
                className="input"
                value={draft.trip}
                onChange={(event) =>
                  setDraft({ ...draft, trip: event.target.value })
                }
              >
                <option value="">{uiText("Select trip")}</option>
                {trips.data?.results.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.code} · {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={uiText("Mode")}>
              <select
                className="input"
                value={draft.mode}
                onChange={(event) =>
                  setDraft({
                    ...draft,
                    mode: event.target.value as TransportDraft["mode"],
                  })
                }
              >
                <option value="BUS">{uiText("Bus")}</option>
                <option value="PRIVATE_CAR">{uiText("Private car")}</option>
                <option value="TRAIN">{uiText("Train")}</option>
                <option value="FERRY">{uiText("Ferry")}</option>
                <option value="OTHER">{uiText("Other")}</option>
              </select>
            </Field>
            <Field label={uiText("Supplier")}>
              <select
                className="input"
                value={draft.supplier}
                onChange={(event) =>
                  setDraft({ ...draft, supplier: event.target.value })
                }
              >
                <option value="">{uiText("No supplier")}</option>
                {suppliers.data?.results.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={uiText("Origin city")}>
              <select
                required
                className="input"
                value={draft.origin_city}
                onChange={(event) =>
                  setDraft({ ...draft, origin_city: event.target.value })
                }
              >
                <option value="">{uiText("Select origin")}</option>
                {cities.data?.results.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={uiText("Destination city")}>
              <select
                required
                className="input"
                value={draft.destination_city}
                onChange={(event) =>
                  setDraft({ ...draft, destination_city: event.target.value })
                }
              >
                <option value="">{uiText("Select destination")}</option>
                {cities.data?.results.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={uiText("Departure")}>
              <input
                required
                type="datetime-local"
                className="input"
                value={draft.departure_at}
                onChange={(event) =>
                  setDraft({ ...draft, departure_at: event.target.value })
                }
              />
            </Field>
            <Field label={uiText("Arrival")}>
              <input
                required
                type="datetime-local"
                className="input"
                value={draft.arrival_at}
                onChange={(event) =>
                  setDraft({ ...draft, arrival_at: event.target.value })
                }
              />
            </Field>
            <Field label={uiText("Order")}>
              <input
                required
                min={1}
                type="number"
                className="input"
                value={draft.order}
                onChange={(event) =>
                  setDraft({ ...draft, order: Number(event.target.value) })
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
            <Field label={uiText("Vehicle details")}>
              <input
                className="input"
                value={draft.vehicle_details}
                onChange={(event) =>
                  setDraft({ ...draft, vehicle_details: event.target.value })
                }
              />
            </Field>
            <Field label={uiText("Vehicle number")}>
              <input
                className="input"
                value={draft.vehicle_number}
                onChange={(event) =>
                  setDraft({ ...draft, vehicle_number: event.target.value })
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
          <MutationMessage error={save.error} />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setFormOpen(false)}
              className="rounded-lg border px-4 py-2"
            >
              {uiText("Cancel")}
            </button>
            <button
              disabled={save.isPending}
              className="rounded-lg bg-cyan-800 px-4 py-2 text-white"
            >
              {save.isPending
                ? uiText("Saving...")
                : editing
                  ? uiText("Save changes")
                  : uiText("Create transport")}
            </button>
          </div>
        </form>
      </FormDialog>
    </div>
  );
}

function TransportCard({
  item,
  onEdit,
  onDelete,
}: Readonly<{
  item: TransportRecord;
  onEdit: () => void;
  onDelete: () => void;
}>) {
  const uiText = useUiText();
  const today = isToday(item.departure_at);
  return (
    <article
      className={`rounded-xl border p-5 ${today ? "border-rose-200 bg-rose-50/40" : "border-slate-200 bg-white"}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={`grid size-10 shrink-0 place-items-center rounded-lg ${today ? "bg-rose-100 text-rose-700" : "bg-cyan-50 text-cyan-800"}`}
          >
            <Bus className="size-5" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold">{uiText(item.mode_display)}</h3>
              {today && (
                <span className="rounded-full bg-rose-100 px-2 py-1 text-[11px] font-semibold uppercase text-rose-700">
                  {uiText("Today")}
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-slate-500">
              {item.trip_code} · {item.trip_name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="shrink-0 text-end text-xs font-medium text-slate-500">
            #{item.order}
          </span>
          <button
            type="button"
            onClick={onEdit}
            title={uiText("Edit transport")}
            className="rounded p-2 text-cyan-800 hover:bg-cyan-50"
          >
            <Pencil className="size-4" />
          </button>
          <button
            type="button"
            onClick={() => {
              if (window.confirm(uiText("Delete this transport leg?")))
                onDelete();
            }}
            title={uiText("Delete transport")}
            className="rounded p-2 text-red-700 hover:bg-red-50"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-400">
            {uiText("Departure")}
          </p>
          <p className="mt-1 font-semibold">{date(item.departure_at)}</p>
          <p className="text-sm text-slate-600">
            {time(item.departure_at)} · {item.origin_city_name}
          </p>
        </div>
        <div className="hidden text-slate-300 sm:block">→</div>
        <div className="sm:text-end">
          <p className="text-xs uppercase tracking-wide text-slate-400">
            {uiText("Arrival")}
          </p>
          <p className="mt-1 font-semibold">{date(item.arrival_at)}</p>
          <p className="text-sm text-slate-600">
            {time(item.arrival_at)} · {item.destination_city_name}
          </p>
        </div>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4 text-sm">
        <span className="inline-flex items-center gap-1.5 text-slate-600">
          <Users className="size-4" />
          {item.passenger_count} {uiText("travelers")}
        </span>
        <span className="text-slate-500">
          {[
            item.supplier_name,
            item.vehicle_details,
            item.vehicle_number,
            item.reference,
          ]
            .filter(Boolean)
            .join(" · ") || uiText("Transport details pending")}
        </span>
        <Link
          href={`/trips/${item.trip}?tab=transport`}
          className="font-medium text-cyan-800 hover:text-cyan-950"
        >
          {uiText("Open trip")}
        </Link>
      </div>
    </article>
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

function Stat({
  label,
  value,
  icon: Icon,
  tone,
}: Readonly<{
  label: string;
  value: number;
  icon: typeof Bus;
  tone: "amber" | "rose" | "cyan" | "emerald" | "slate";
}>) {
  const colors = {
    amber: "bg-amber-50 text-amber-700",
    rose: "bg-rose-50 text-rose-700",
    cyan: "bg-cyan-50 text-cyan-800",
    emerald: "bg-emerald-50 text-emerald-700",
    slate: "bg-slate-100 text-slate-700",
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <span
        className={`grid size-9 place-items-center rounded-lg ${colors[tone]}`}
      >
        <Icon className="size-4" />
      </span>
      <p className="mt-4 text-2xl font-semibold">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{label}</p>
    </div>
  );
}
