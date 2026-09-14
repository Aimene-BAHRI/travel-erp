"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Download,
  FileText,
  LoaderCircle,
  Pencil,
  Plus,
  Save,
  Upload,
} from "lucide-react";
import { useState } from "react";

import { MutationMessage } from "@/components/forms/mutation-message";
import type { Country, Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";

import { PassportScanAssistant } from "./passport-scan-assistant";
import type { DocumentRecord, PassportDetail, Traveler } from "./types";

type PassportDraft = Omit<PassportDetail, "id" | "passport_image">;
const blankPassport: PassportDraft = {
  passport_number: "",
  first_name: "",
  middle_name: "",
  last_name: "",
  status: "CURRENT",
  birth_date: "",
  birth_place: "",
  birth_country: null,
  nationality: "",
  gender: "X",
  issue_date: "",
  expiry_date: "",
  issuing_country: "",
  issue_place: "",
  mrz: "",
};

export function TravelerProfile({
  travelerId,
}: Readonly<{ travelerId: string }>) {
  const uiText = useUiText();
  const cache = useQueryClient();
  const [editingTraveler, setEditingTraveler] = useState(false);
  const [details, setDetails] = useState<Partial<Traveler>>({});
  const [editingPassport, setEditingPassport] = useState(false);
  const [passportId, setPassportId] = useState<string | null>(null);
  const [passport, setPassport] = useState<PassportDraft>(blankPassport);
  const [passportImage, setPassportImage] = useState<File | null>(null);
  const [croppedPhoto, setCroppedPhoto] = useState<File | null>(null);
  const [mrzWarnings, setMrzWarnings] = useState<string[]>([]);
  const [photoSource, setPhotoSource] = useState<
    "PASSPORT_AUTO_CROP" | "PASSPORT_MANUAL_CROP"
  >("PASSPORT_MANUAL_CROP");
  const traveler = useQuery({
    queryKey: ["traveler", travelerId],
    queryFn: () => apiRequest<Traveler>(`/travelers/${travelerId}/`),
  });
  const passports = useQuery({
    queryKey: ["traveler-passports", travelerId],
    queryFn: () =>
      apiRequest<Paginated<PassportDetail>>(
        `/travelers/passports/?traveler=${travelerId}`,
      ),
  });
  const documents = useQuery({
    queryKey: ["traveler-documents", travelerId],
    queryFn: () =>
      apiRequest<Paginated<DocumentRecord>>(
        `/documents/?owner_type=TRAVELER&owner_id=${travelerId}`,
      ),
  });
  const countries = useQuery({
    queryKey: ["countries"],
    queryFn: () =>
      apiRequest<Paginated<Country>>("/reference/countries/?ordering=name"),
  });
  const refresh = () => {
    cache.invalidateQueries({ queryKey: ["traveler", travelerId] });
    cache.invalidateQueries({ queryKey: ["traveler-passports", travelerId] });
    cache.invalidateQueries({ queryKey: ["traveler-documents", travelerId] });
  };
  const saveTraveler = useMutation({
    mutationFn: () =>
      apiRequest<Traveler>(`/travelers/${travelerId}/`, {
        method: "PATCH",
        body: JSON.stringify(details),
      }),
    onSuccess: () => {
      setEditingTraveler(false);
      refresh();
    },
  });
  const parseMrz = useMutation({
    mutationFn: () =>
      apiRequest<
        Partial<PassportDraft> & {
          nationality_code?: string;
          issuing_country_code?: string;
          mrz_warnings?: string[];
        }
      >("/travelers/passports/parse-mrz/", {
        method: "POST",
        body: JSON.stringify({ mrz: passport.mrz }),
      }),
    onSuccess: (value) => {
      setMrzWarnings(value.mrz_warnings ?? []);
      const countryId = (code?: string) =>
        countries.data?.results.find(
          (item) =>
            item.code === code || (code === "DZA" && item.code === "DZ"),
        )?.id ?? "";
      setPassport({
        ...passport,
        ...value,
        nationality: countryId(value.nationality_code) || passport.nationality,
        issuing_country:
          countryId(value.issuing_country_code) || passport.issuing_country,
      });
    },
  });
  const savePassport = useMutation({
    mutationFn: async () => {
      const saved = await apiRequest<PassportDetail>(
        passportId
          ? `/travelers/passports/${passportId}/`
          : "/travelers/passports/",
        {
          method: passportId ? "PATCH" : "POST",
          body: JSON.stringify({
            ...passport,
            traveler: travelerId,
            birth_country: passport.birth_country || null,
          }),
        },
      );
      if (passportImage) {
        const document = await uploadDocument(
          passportImage,
          "PASSPORT",
          `Passport ${saved.passport_number}`,
          "PASSPORT",
          saved.id,
          "Traveler profile passport scan",
        );
        await apiRequest(`/travelers/passports/${saved.id}/set-image/`, {
          method: "POST",
          body: JSON.stringify({ document: document.id }),
        });
      }
      if (croppedPhoto) {
        const document = await uploadDocument(
          croppedPhoto,
          "PHOTO",
          `Traveler photo · ${saved.first_name} ${saved.last_name}`,
          "TRAVELER",
          travelerId,
          photoSource,
        );
        await apiRequest(`/travelers/${travelerId}/set-current-photo/`, {
          method: "POST",
          body: JSON.stringify({ document: document.id, source: photoSource }),
        });
      }
      return saved;
    },
    onSuccess: () => {
      setEditingPassport(false);
      setPassportImage(null);
      setCroppedPhoto(null);
      refresh();
    },
  });
  const manualPhoto = useMutation({
    mutationFn: async (file: File) => {
      const document = await uploadDocument(
        file,
        "PHOTO",
        `Traveler photo · ${traveler.data?.display_name ?? travelerId}`,
        "TRAVELER",
        travelerId,
        "MANUAL_UPLOAD",
      );
      return apiRequest(`/travelers/${travelerId}/set-current-photo/`, {
        method: "POST",
        body: JSON.stringify({
          document: document.id,
          source: "MANUAL_UPLOAD",
        }),
      });
    },
    onSuccess: refresh,
  });

  const openTraveler = () => {
    if (!traveler.data) return;
    setDetails({
      first_name: traveler.data.first_name,
      last_name: traveler.data.last_name,
      birth_date: traveler.data.birth_date,
      gender: traveler.data.gender,
      phone: traveler.data.phone,
      email: traveler.data.email,
      address: traveler.data.address,
      notes: traveler.data.notes,
    });
    setEditingTraveler(true);
  };
  const openPassport = (item?: PassportDetail) => {
    setMrzWarnings([]);
    setPassportId(item?.id ?? null);
    setPassport(
      item
        ? {
            passport_number: item.passport_number,
            first_name: item.first_name,
            middle_name: item.middle_name,
            last_name: item.last_name,
            status: item.status,
            birth_date: item.birth_date,
            birth_place: item.birth_place,
            birth_country: item.birth_country,
            nationality: item.nationality,
            gender: item.gender,
            issue_date: item.issue_date,
            expiry_date: item.expiry_date,
            issuing_country: item.issuing_country,
            issue_place: item.issue_place,
            mrz: item.mrz,
          }
        : blankPassport,
    );
    setPassportImage(null);
    setCroppedPhoto(null);
    setEditingPassport(true);
  };

  if (
    traveler.isPending ||
    passports.isPending ||
    documents.isPending ||
    countries.isPending
  )
    return (
      <div className="grid min-h-72 place-items-center">
        <LoaderCircle className="size-8 animate-spin text-cyan-800" />
      </div>
    );
  if (!traveler.data)
    return (
      <p className="rounded-lg bg-red-50 p-4 text-red-700">
        {uiText("Traveler profile is unavailable.")}
      </p>
    );
  return (
    <div className="space-y-6">
      <section className="rounded-xl border bg-white p-6">
        <div className="flex flex-col justify-between gap-5 md:flex-row">
          <div className="flex gap-5">
            {traveler.data.current_photo_url ? (
              <img
                src={traveler.data.current_photo_url}
                alt={traveler.data.display_name}
                className="size-28 rounded-xl border object-cover"
              />
            ) : (
              <div className="grid size-28 place-items-center rounded-xl bg-slate-100 text-xs text-slate-500">
                {uiText("No photo")}
              </div>
            )}
            <div>
              <p className="text-sm text-slate-500">{uiText("Traveler profile")}</p>
              <h1 className="mt-1 text-3xl font-semibold">
                {traveler.data.display_name}
              </h1>
              <p className="mt-2 text-sm text-slate-600">
                {uiText("Managed by")} {traveler.data.branch_name}
              </p>
              <p className="text-xs text-slate-500">
                {uiText("Photo source:")} {uiText(traveler.data.current_photo_source || "none")}
              </p>
            </div>
          </div>
          <div className="space-y-2">
            <button
              onClick={openTraveler}
              className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
            >
              <Pencil className="size-4" />
              {uiText("Edit traveler")}
            </button>
            <label className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm">
              <Upload className="size-4" />
              {uiText("Upload photo")}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) manualPhoto.mutate(file);
                }}
              />
            </label>
          </div>
        </div>
        {editingTraveler && (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              saveTraveler.mutate();
            }}
            className="mt-6 grid gap-4 border-t pt-6 sm:grid-cols-2"
          >
            <Input
              label={uiText("First name")}
              value={String(details.first_name ?? "")}
              onChange={(value) =>
                setDetails({ ...details, first_name: value })
              }
            />
            <Input
              label={uiText("Last name")}
              value={String(details.last_name ?? "")}
              onChange={(value) => setDetails({ ...details, last_name: value })}
            />
            <Input
              label={uiText("Birth date")}
              type="date"
              value={String(details.birth_date ?? "")}
              onChange={(value) =>
                setDetails({ ...details, birth_date: value })
              }
            />
            <label className="text-sm font-medium">
              {uiText("Gender")}
              <select
                value={details.gender}
                onChange={(event) =>
                  setDetails({
                    ...details,
                    gender: event.target.value as Traveler["gender"],
                  })
                }
                className="mt-1 w-full rounded-lg border px-3 py-2"
              >
                <option value="M">{uiText("Male")}</option>
                <option value="F">{uiText("Female")}</option>
                <option value="X">{uiText("Unspecified")}</option>
              </select>
            </label>
            <Input
              label={uiText("Phone")}
              value={String(details.phone ?? "")}
              onChange={(value) => setDetails({ ...details, phone: value })}
            />
            <Input
              label={uiText("Email")}
              type="email"
              value={String(details.email ?? "")}
              onChange={(value) => setDetails({ ...details, email: value })}
            />
            <Input
              label={uiText("Address")}
              value={String(details.address ?? "")}
              onChange={(value) => setDetails({ ...details, address: value })}
            />
            <Input
              label={uiText("Notes")}
              value={String(details.notes ?? "")}
              onChange={(value) => setDetails({ ...details, notes: value })}
            />
            <div className="sm:col-span-2">
              <MutationMessage error={saveTraveler.error} />
              <button className="flex items-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white">
                <Save className="size-4" />
                {uiText("Save traveler")}
              </button>
            </div>
          </form>
        )}
      </section>
      <section className="rounded-xl border bg-white">
        <header className="flex items-center justify-between border-b p-5">
          <div>
            <h2 className="font-semibold">{uiText("Passport history")}</h2>
            <p className="text-sm text-slate-500">
              {uiText("Scan a passport or update legal identity fields.")}
            </p>
          </div>
          <button
            onClick={() => openPassport()}
            className="flex items-center gap-2 rounded-lg bg-cyan-800 px-3 py-2 text-sm font-medium text-white"
          >
            <Plus className="size-4" />
            {uiText("Add passport")}
          </button>
        </header>
        {editingPassport && (
          <PassportEditor
            passport={passport}
            setPassport={setPassport}
            passportImage={passportImage}
            setPassportImage={setPassportImage}
            croppedPhoto={croppedPhoto}
            setPhoto={(file, source) => {
              setCroppedPhoto(file);
              setPhotoSource(source);
            }}
            countries={countries.data?.results ?? []}
            mrzWarnings={mrzWarnings}
            parse={parseMrz}
            save={savePassport}
            onCancel={() => setEditingPassport(false)}
          />
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-start text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-5 py-3">{uiText("Passport")}</th>
                <th className="px-5 py-3">{uiText("Name")}</th>
                <th className="px-5 py-3">{uiText("Issued")}</th>
                <th className="px-5 py-3">{uiText("Expires")}</th>
                <th className="px-5 py-3">{uiText("Status")}</th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y">
              {passports.data?.results.map((item) => (
                <tr key={item.id}>
                  <td className="px-5 py-4 font-mono text-xs">
                    {item.passport_number}
                  </td>
                  <td className="px-5 py-4 font-medium">
                    {[item.first_name, item.middle_name, item.last_name]
                      .filter(Boolean)
                      .join(" ")}
                  </td>
                  <td className="px-5 py-4">{item.issue_date}</td>
                  <td className="px-5 py-4">{item.expiry_date}</td>
                  <td className="px-5 py-4">{uiText(item.status)}</td>
                  <td>
                    <button
                      onClick={() => openPassport(item)}
                      className="text-cyan-800"
                    >
                      {uiText("Edit")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="rounded-xl border bg-white">
        <header className="border-b p-5">
          <h2 className="font-semibold">{uiText("Documents")}</h2>
        </header>
        {documents.data?.results.length ? (
          <ul className="divide-y">
            {documents.data.results.map((document) => (
              <li
                key={document.id}
                className="flex items-center justify-between px-5 py-4"
              >
                <div className="flex items-center gap-3">
                  <FileText className="size-5 text-slate-400" />
                  <div>
                    <p className="font-medium">{document.title}</p>
                    <p className="text-xs text-slate-500">
                      {document.original_filename} ·{" "}
                      {Math.ceil(document.size_bytes / 1024)} KB
                    </p>
                  </div>
                </div>
                <a
                  href={document.download_url}
                  className="flex items-center gap-2 text-sm text-cyan-800"
                >
                  <Download className="size-4" />
                  {uiText("Download")}
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p className="p-6 text-sm text-slate-500">{uiText("No documents attached.")}</p>
        )}
      </section>
    </div>
  );
}

function PassportEditor({
  passport,
  setPassport,
  passportImage,
  setPassportImage,
  croppedPhoto,
  setPhoto,
  countries,
  mrzWarnings,
  parse,
  save,
  onCancel,
}: Readonly<{
  passport: PassportDraft;
  setPassport: (value: PassportDraft) => void;
  passportImage: File | null;
  setPassportImage: (file: File | null) => void;
  croppedPhoto: File | null;
  setPhoto: (
    file: File,
    source: "PASSPORT_AUTO_CROP" | "PASSPORT_MANUAL_CROP",
  ) => void;
  countries: Country[];
  mrzWarnings: string[];
  parse: {
    mutate: () => void;
    isPending: boolean;
    isSuccess: boolean;
    error: Error | null;
  };
  save: { mutate: () => void; isPending: boolean; error: Error | null };
  onCancel: () => void;
}>) {
  const uiText = useUiText();
  const change = (key: keyof PassportDraft, value: string) =>
    setPassport({ ...passport, [key]: value });
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
      className="space-y-5 border-b bg-slate-50 p-5"
    >
      <PassportScanAssistant
        file={passportImage}
        setFile={setPassportImage}
        mrz={passport.mrz}
        setMrz={(value) => change("mrz", value)}
        onPhoto={setPhoto}
      />
      {croppedPhoto && (
        <p className="text-xs text-emerald-700">
          {uiText("Cropped traveler photo ready.")}
        </p>
      )}
      <button
        type="button"
        onClick={() => parse.mutate()}
        disabled={!passport.mrz || parse.isPending}
        className="rounded-lg border bg-white px-3 py-2 text-sm text-cyan-800"
      >
        {uiText("Validate MRZ and fill fields")}
      </button>
      {parse.isSuccess && mrzWarnings.length === 0 && (
        <p className="text-xs text-emerald-700">
          {uiText("Passport number, birth date, expiry date, and the complete MRZ checksum were verified.")}
        </p>
      )}
      {mrzWarnings.length > 0 && (
        <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
          {uiText("Core identity fields were verified and filled. The scanner could not verify")} {mrzWarnings.join(" and ")}{uiText("; compare the filled fields with the passport image before saving.")}
        </p>
      )}
      <div className="grid gap-4 sm:grid-cols-3">
        <Input
          label={uiText("Passport number")}
          value={passport.passport_number}
          onChange={(value) => change("passport_number", value)}
        />
        <Input
          label={uiText("First name")}
          value={passport.first_name}
          onChange={(value) => change("first_name", value)}
        />
        <Input
          label={uiText("Middle name")}
          value={passport.middle_name}
          onChange={(value) => change("middle_name", value)}
        />
        <Input
          label={uiText("Last name")}
          value={passport.last_name}
          onChange={(value) => change("last_name", value)}
        />
        <Input
          label={uiText("Birth date")}
          type="date"
          value={passport.birth_date}
          onChange={(value) => change("birth_date", value)}
        />
        <label className="text-sm font-medium">
          {uiText("Gender")}
          <select
            className="mt-1 w-full rounded-lg border px-3 py-2"
            value={passport.gender}
            onChange={(event) => change("gender", event.target.value)}
          >
            <option value="M">{uiText("Male")}</option>
            <option value="F">{uiText("Female")}</option>
            <option value="X">{uiText("Unspecified")}</option>
          </select>
        </label>
        <CountrySelect
          label={uiText("Nationality")}
          value={passport.nationality}
          countries={countries}
          onChange={(value) => change("nationality", value)}
        />
        <CountrySelect
          label={uiText("Issuing country")}
          value={passport.issuing_country}
          countries={countries}
          onChange={(value) => change("issuing_country", value)}
        />
        <CountrySelect
          label={uiText("Birth country")}
          value={passport.birth_country ?? ""}
          countries={countries}
          optional
          onChange={(value) => change("birth_country", value)}
        />
        <Input
          label={uiText("Issue date")}
          type="date"
          value={passport.issue_date}
          onChange={(value) => change("issue_date", value)}
        />
        <Input
          label={uiText("Expiry date")}
          type="date"
          value={passport.expiry_date}
          onChange={(value) => change("expiry_date", value)}
        />
        <Input
          label={uiText("Issue place")}
          value={passport.issue_place}
          onChange={(value) => change("issue_place", value)}
        />
        <Input
          label={uiText("Birth place")}
          value={passport.birth_place}
          onChange={(value) => change("birth_place", value)}
        />
      </div>
      <MutationMessage error={save.error ?? parse.error} />
      <div className="flex gap-2">
        <button
          disabled={save.isPending}
          className="rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white"
        >
          {uiText("Save passport and photo")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border px-4 py-2 text-sm"
        >
          {uiText("Cancel")}
        </button>
      </div>
    </form>
  );
}

async function uploadDocument(
  file: File,
  category: string,
  title: string,
  ownerType: string,
  ownerId: string,
  purpose: string,
) {
  const body = new FormData();
  body.append("file", file);
  body.append("category", category);
  body.append("title", title);
  body.append("owner_type", ownerType);
  body.append("owner_id", ownerId);
  body.append("purpose", purpose);
  return apiRequest<DocumentRecord>("/documents/", { method: "POST", body });
}
function Input({
  label,
  value,
  onChange,
  type = "text",
}: Readonly<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}>) {
  const uiText = useUiText();
  return (
    <label className="text-sm font-medium">
      {label}
      <input
        required={
          ![
            "Notes",
            "Address",
            "Phone",
            "Email",
            "Middle name",
            "Issue place",
            "Birth place",
          ].map(uiText).includes(label)
        }
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-lg border px-3 py-2"
      />
    </label>
  );
}
function CountrySelect({
  label,
  value,
  countries,
  onChange,
  optional = false,
}: Readonly<{
  label: string;
  value: string;
  countries: Country[];
  onChange: (value: string) => void;
  optional?: boolean;
}>) {
  const uiText = useUiText();
  return (
    <label className="text-sm font-medium">
      {label}
      <select
        required={!optional}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-lg border px-3 py-2"
      >
        <option value="">{uiText("Select country")}</option>
        {countries.map((country) => (
          <option key={country.id} value={country.id}>
            {country.name}
          </option>
        ))}
      </select>
    </label>
  );
}
