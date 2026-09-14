"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { Customer } from "@/features/customers/types";
import type { AgencyCurrency, Paginated } from "@/features/reference/types";
import type { TripRecord } from "@/features/trips/types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";

import type { BookingRecord } from "./types";

type Branch = { id: string; name: string };
type NewCustomer = {
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
};

const text = {
  ar: {
    start: "بدء حجز مباشر",
    help: "أنشئ حجزا مسودة، ثم أضف المسافرين، الغرف، الأسعار، والتخفيضات.",
    branch: "الفرع",
    trip: "الرحلة",
    customerSource: "مصدر العميل",
    newCustomer: "عميل جديد",
    existingCustomer: "عميل موجود",
    firstName: "الاسم",
    lastName: "اللقب",
    phone: "الهاتف",
    email: "البريد الإلكتروني",
    sellingCurrency: "عملة البيع",
    accountingCurrency: "عملة المحاسبة",
    exchangeRate: "سعر الصرف المحاسبي",
    notes: "ملاحظات",
    cancel: "إلغاء",
    createDraft: "إنشاء حجز مسودة",
    select: "اختر",
  },
  en: {
    start: "Start direct booking",
    help: "Create a draft, then add travelers, rooms, prices, and discounts.",
    branch: "Branch",
    trip: "Trip",
    customerSource: "Customer source",
    newCustomer: "New customer",
    existingCustomer: "Existing customer",
    firstName: "First name",
    lastName: "Last name",
    phone: "Phone",
    email: "Email",
    sellingCurrency: "Selling currency",
    accountingCurrency: "Accounting currency",
    exchangeRate: "Accounting exchange rate",
    notes: "Notes",
    cancel: "Cancel",
    createDraft: "Create draft booking",
    select: "Select",
  },
};

export function BookingCreator() {
  const { locale } = useLocale();
  const copy = text[locale];
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [branch, setBranch] = useState("");
  const [mode, setMode] = useState<"NEW" | "EXISTING">("NEW");
  const [customer, setCustomer] = useState("");
  const [fresh, setFresh] = useState<NewCustomer>({
    first_name: "",
    last_name: "",
    phone: "",
    email: "",
  });
  const [trip, setTrip] = useState("");
  const [expectedTravelers, setExpectedTravelers] = useState("1");
  const [currency, setCurrency] = useState("");
  const [accounting, setAccounting] = useState("");
  const [rate, setRate] = useState("1");
  const [notes, setNotes] = useState("");
  const branches = useQuery({
    queryKey: ["branches"],
    queryFn: () => apiRequest<Paginated<Branch>>("/organizations/branches/"),
  });
  const customers = useQuery({
    queryKey: ["customers", "booking-options"],
    queryFn: () => apiRequest<Paginated<Customer>>("/customers/?ordering=display_name"),
  });
  const trips = useQuery({
    queryKey: ["trips", "booking-options"],
    queryFn: () => apiRequest<Paginated<TripRecord>>("/trips/?ordering=departure_date"),
  });
  const currencies = useQuery({
    queryKey: ["agency-currencies"],
    queryFn: () => apiRequest<Paginated<AgencyCurrency>>("/reference/agency-currencies/"),
  });
  const create = useMutation({
    mutationFn: () =>
      apiRequest<BookingRecord>("/bookings/draft/", {
        method: "POST",
        body: JSON.stringify({
          branch,
          ...(mode === "NEW"
            ? { new_customer: { kind: "INDIVIDUAL", ...fresh } }
            : { customer }),
          trip,
          expected_travelers: Number(expectedTravelers),
          currency,
          accounting_currency: accounting,
          accounting_exchange_rate: rate,
          notes,
        }),
      }),
    onSuccess: (booking) => router.push(`/bookings/${booking.id}`),
  });
  const start = () => {
    const enabled = currencies.data?.results.filter((item) => item.is_enabled) ?? [];
    const base = enabled.find((item) => item.is_accounting)?.currency ?? enabled[0]?.currency ?? "";
    setBranch(branches.data?.results[0]?.id ?? "");
    setMode("NEW");
    setCustomer(customers.data?.results[0]?.id ?? "");
    setFresh({ first_name: "", last_name: "", phone: "", email: "" });
    setTrip(trips.data?.results[0]?.id ?? "");
    setCurrency(base);
    setAccounting(base);
    setRate("1");
    setNotes("");
    setExpectedTravelers("1");
    create.reset();
    setOpen(true);
  };
  const selectedTrip = trips.data?.results.find((item) => item.id === trip);
  const ready =
    mode === "EXISTING"
      ? Boolean(customer)
      : Boolean((fresh.first_name.trim() || fresh.last_name.trim()) && (fresh.phone.trim() || fresh.email.trim()));

  return (
    <>
      <div className="mb-6 flex justify-end">
        <button
          onClick={start}
          className="flex items-center justify-center gap-2 rounded-xl bg-cyan-800 px-6 py-4 font-medium text-white"
        >
          <Plus className="size-5" />
          {copy.start}
        </button>
      </div>
      <FormDialog open={open} onClose={() => setOpen(false)} title={copy.start} description={copy.help}>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
          className="space-y-5"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={copy.branch}>
              <Select value={branch} onChange={setBranch} options={branches.data?.results.map((item) => [item.id, item.name]) ?? []} placeholder={copy.select} />
            </Field>
            <Field label={copy.trip}>
              <Select value={trip} onChange={setTrip} options={trips.data?.results.map((item) => [item.id, `${item.code} · ${item.name}`]) ?? []} placeholder={copy.select} />
            </Field>
            <Field label={locale === "ar" ? "??? ????????? ?????" : "Number of travelers to book"} wide>
              <input required type="number" min="1" max="32767" className="input" value={expectedTravelers} onChange={(event) => setExpectedTravelers(event.target.value)} />
              {selectedTrip && <p className="mt-2 text-sm text-slate-600">
                {locale === "ar" ? "??? ??????" : "Trip capacity"}: {selectedTrip.max_travelers ?? "?"} ? {locale === "ar" ? "?????" : "Booked"}: {selectedTrip.booked_places} ? {locale === "ar" ? "?????" : "Remaining"}: {selectedTrip.remaining_places ?? "?"}
              </p>}
              {selectedTrip?.remaining_places != null && Number(expectedTravelers) > selectedTrip.remaining_places && <p className="mt-2 text-sm text-red-700">{locale === "ar" ? "??????? ??? ?????. ????? ????? ????? ??? ?? ???? ??????? ??? ????? ?????." : "Not enough places. You can prepare a draft, but confirmation requires available places."}</p>}
            </Field>
            <Field label={copy.customerSource} wide>
              <div className="flex gap-2">
                <Toggle active={mode === "NEW"} onClick={() => setMode("NEW")}>{copy.newCustomer}</Toggle>
                <Toggle active={mode === "EXISTING"} onClick={() => setMode("EXISTING")}>{copy.existingCustomer}</Toggle>
              </div>
            </Field>
            {mode === "NEW" ? (
              <>
                <Field label={copy.firstName}><input className="input" value={fresh.first_name} onChange={(event) => setFresh({ ...fresh, first_name: event.target.value })} /></Field>
                <Field label={copy.lastName}><input className="input" value={fresh.last_name} onChange={(event) => setFresh({ ...fresh, last_name: event.target.value })} /></Field>
                <Field label={copy.phone}><input className="input" value={fresh.phone} onChange={(event) => setFresh({ ...fresh, phone: event.target.value })} /></Field>
                <Field label={copy.email}><input type="email" className="input" value={fresh.email} onChange={(event) => setFresh({ ...fresh, email: event.target.value })} /></Field>
              </>
            ) : (
              <Field label={copy.existingCustomer} wide>
                <Select value={customer} onChange={setCustomer} options={customers.data?.results.map((item) => [item.id, item.display_name]) ?? []} placeholder={copy.select} />
              </Field>
            )}
            <Field label={copy.sellingCurrency}>
              <Select value={currency} onChange={setCurrency} options={currencies.data?.results.filter((item) => item.is_enabled).map((item) => [item.currency, item.currency]) ?? []} placeholder={copy.select} />
            </Field>
            <Field label={copy.accountingCurrency}>
              <Select value={accounting} onChange={setAccounting} options={currencies.data?.results.filter((item) => item.is_enabled).map((item) => [item.currency, item.currency]) ?? []} placeholder={copy.select} />
            </Field>
            <Field label={copy.exchangeRate}>
              <input required min="0.00000001" step="0.00000001" type="number" className="input" value={rate} onChange={(event) => setRate(event.target.value)} />
            </Field>
            <Field label={copy.notes} wide>
              <textarea className="input" value={notes} onChange={(event) => setNotes(event.target.value)} />
            </Field>
          </div>
          <MutationMessage error={create.error} />
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border px-4 py-2">{copy.cancel}</button>
            <button disabled={create.isPending || !branch || !trip || !ready} className="rounded-lg bg-cyan-800 px-4 py-2 text-white disabled:opacity-50">{copy.createDraft}</button>
          </div>
        </form>
      </FormDialog>
    </>
  );
}

function Toggle({ active, onClick, children }: Readonly<{ active: boolean; onClick: () => void; children: React.ReactNode }>) {
  return (
    <button type="button" onClick={onClick} className={`rounded-lg px-3 py-2 ${active ? "bg-cyan-800 text-white" : "border"}`}>
      {children}
    </button>
  );
}

function Field({ label, wide, children }: Readonly<{ label: string; wide?: boolean; children: React.ReactNode }>) {
  return (
    <label className={`text-sm font-medium ${wide ? "sm:col-span-2" : ""}`}>
      {label}
      <div className="mt-1 [&_.input]:w-full [&_.input]:rounded-lg [&_.input]:border [&_.input]:px-3 [&_.input]:py-2">{children}</div>
    </label>
  );
}

function Select({
  value,
  onChange,
  options,
  placeholder,
}: Readonly<{
  value: string;
  onChange: (value: string) => void;
  options: string[][];
  placeholder: string;
}>) {
  return (
    <select required className="input" value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">{placeholder}</option>
      {options.map((option) => (
        <option key={option[0]} value={option[0]}>{option[1]}</option>
      ))}
    </select>
  );
}
