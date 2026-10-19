"use client";

import { ClientReview } from "./client-review";
import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  BadgePercent,
  BedDouble,
  FileScan,
  Plus,
  Trash2,
  UserPlus,
} from "lucide-react";
import { useState } from "react";

import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { DocumentRecord } from "@/features/travelers/types";
import { PassportScanAssistant } from "@/features/travelers/passport-scan-assistant";
import type { HotelPriceRecord } from "@/features/pricing/types";
import type { Country, Paginated } from "@/features/reference/types";
import type { AccommodationPlan } from "@/features/trips/types";
import { apiRequest } from "@/lib/api/client";
import { useOperationalText } from "@/lib/i18n/operational";

import type { BookingRecord, BookingTravelerRecord } from "./types";

const field = "rounded-lg border border-slate-300 px-3 py-2 text-sm";
const primary =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-40";
type PersonDraft = {
  first_name: string;
  last_name: string;
  phone: string;
  birth_date: string;
  gender: "M" | "F" | "X";
  is_customer_contact: boolean;
};
type PassportDraft = {
  passport_number: string;
  first_name: string;
  middle_name: string;
  last_name: string;
  birth_date: string;
  gender: "M" | "F" | "X";
  nationality: string;
  issuing_country: string;
  birth_country: string;
  birth_place: string;
  issue_date: string;
  expiry_date: string;
  issue_place: string;
  mrz: string;
};
const blankPassport: PassportDraft = {
  passport_number: "",
  first_name: "",
  middle_name: "",
  last_name: "",
  birth_date: "",
  gender: "X",
  nationality: "",
  issuing_country: "",
  birth_country: "",
  birth_place: "",
  issue_date: "",
  expiry_date: "",
  issue_place: "",
  mrz: "",
};

export function BookingDraftWorkspace({
  booking,
  onChange,
}: Readonly<{
  booking: BookingRecord;
  onChange: (booking: BookingRecord) => void;
}>) {
  const t = useOperationalText();
  const [person, setPerson] = useState<PersonDraft>({
    first_name: "",
    last_name: "",
    phone: "",
    birth_date: "",
    gender: "X",
    is_customer_contact: false,
  });
  const [contact, setContact] = useState({
    first_name: booking.customer_first_name,
    last_name: booking.customer_last_name,
    phone: booking.customer_phone,
    email: booking.customer_email,
    address: booking.customer_address,
  });
  const [passportTraveler, setPassportTraveler] =
    useState<BookingTravelerRecord | null>(null);
  const [passportOpen, setPassportOpen] = useState(false);
  const [passport, setPassport] = useState<PassportDraft>(blankPassport);
  const [passportImage, setPassportImage] = useState<File | null>(null);
  const [travelerPhoto, setTravelerPhoto] = useState<File | null>(null);
  const [travelerPhotoSource, setTravelerPhotoSource] = useState<
    "PASSPORT_AUTO_CROP" | "PASSPORT_MANUAL_CROP"
  >("PASSPORT_MANUAL_CROP");
  const [charge, setCharge] = useState({
    booking_traveler_id: "",
    kind: "SERVICE",
    description: "Final package price",
    source_price: "",
    base_amount: "",
  });
  const [discount, setDiscount] = useState({
    chargeId: "",
    kind: "AMOUNT",
    value: "",
    reason: "",
  });
  const [roomDraft, setRoomDraft] = useState({
    trip_hotel: "",
    room_type: "",
    label: "",
    capacity: "2",
    notes: "",
  });
  const countries = useQuery({
    queryKey: ["countries"],
    queryFn: () =>
      apiRequest<Paginated<Country>>("/reference/countries/?ordering=name"),
  });
  const prices = useQuery({
    queryKey: ["hotel-prices", booking.trip],
    queryFn: () =>
      apiRequest<Paginated<HotelPriceRecord>>(
        `/pricing/hotel-prices/?trip=${booking.trip}`,
      ),
  });
  const accommodationPlan = useQuery({
    queryKey: ["draft-accommodation-plan", booking.trip],
    queryFn: () =>
      apiRequest<AccommodationPlan>(
        `/trips/${booking.trip}/accommodation-plan/`,
      ),
  });
  const roomTypes = useQuery({
    queryKey: ["booking-room-types"],
    queryFn: () =>
      apiRequest<Paginated<{ id: string; name: string }>>(
        "/catalog/room-types/?ordering=sort_order,name",
      ),
  });
  const reload = () => apiRequest<BookingRecord>(`/bookings/${booking.id}/`);
  const saveContact = useMutation({
    mutationFn: () =>
      apiRequest<BookingRecord>(`/bookings/${booking.id}/customer-contact/`, {
        method: "PATCH",
        body: JSON.stringify(contact),
      }),
    onSuccess: onChange,
  });
  const addTraveler = useMutation({
    mutationFn: () =>
      apiRequest<BookingRecord>(`/bookings/${booking.id}/inline-travelers/`, {
        method: "POST",
        body: JSON.stringify({
          ...person,
          bed_requirement:
            categoryFor(person.birth_date, booking.return_date) === "INF"
              ? "NOT_REQUIRED"
              : "REQUIRED",
        }),
      }),
    onSuccess: (result) => {
      onChange(result);
      setPerson({
        first_name: "",
        last_name: "",
        phone: "",
        birth_date: "",
        gender: "X",
        is_customer_contact: false,
      });
    },
  });
  const removeTraveler = useMutation({
    mutationFn: async (id: string) => {
      await apiRequest<void>(`/bookings/${booking.id}/travelers/${id}/`, {
        method: "DELETE",
      });
      return reload();
    },
    onSuccess: onChange,
  });
  const savePassport = useMutation({
    mutationFn: async () => {
      let targetTraveler = passportTraveler;
      if (!targetTraveler) {
        const withTraveler = await apiRequest<BookingRecord>(
          `/bookings/${booking.id}/inline-travelers/`,
          {
            method: "POST",
            body: JSON.stringify({
              first_name: passport.first_name,
              last_name: passport.last_name,
              birth_date: passport.birth_date,
              gender: passport.gender,
              bed_requirement:
                categoryFor(passport.birth_date, booking.return_date) === "INF"
                  ? "NOT_REQUIRED"
                  : "REQUIRED",
              is_customer_contact: false,
            }),
          },
        );
        const existingIds = new Set(booking.travelers.map((item) => item.id));
        targetTraveler =
          withTraveler.travelers.find((item) => !existingIds.has(item.id)) ??
          null;
        if (!targetTraveler)
          throw new Error(t("The scanned traveler could not be created."));
      }
      const result = await apiRequest<BookingRecord>(
        `/bookings/${booking.id}/travelers/${targetTraveler.id}/passport/`,
        {
          method: targetTraveler.passport_id ? "PATCH" : "POST",
          body: JSON.stringify({
            ...passport,
            birth_country: passport.birth_country || null,
            status: "CURRENT",
          }),
        },
      );
      const updated = result.travelers.find(
        (item) => item.id === targetTraveler.id,
      );
      if (passportImage && updated?.passport_id) {
        const body = new FormData();
        body.append("file", passportImage);
        body.append("category", "PASSPORT");
        body.append(
          "title",
          `Passport ${updated.passport_number ?? updated.traveler_name}`,
        );
        body.append("owner_type", "PASSPORT");
        body.append("owner_id", updated.passport_id);
        body.append("purpose", "Booking passport scan");
        const passportDocument = await apiRequest<DocumentRecord>(
          "/documents/",
          {
            method: "POST",
            body,
          },
        );
        await apiRequest(
          `/travelers/passports/${updated.passport_id}/set-image/`,
          {
            method: "POST",
            body: JSON.stringify({ document: passportDocument.id }),
          },
        );
      }
      if (travelerPhoto && updated) {
        const body = new FormData();
        body.append("file", travelerPhoto);
        body.append("category", "PHOTO");
        body.append("title", `Traveler photo · ${updated.traveler_name}`);
        body.append("owner_type", "TRAVELER");
        body.append("owner_id", updated.traveler);
        body.append("purpose", travelerPhotoSource);
        const photoDocument = await apiRequest<DocumentRecord>("/documents/", {
          method: "POST",
          body,
        });
        await apiRequest(`/travelers/${updated.traveler}/set-current-photo/`, {
          method: "POST",
          body: JSON.stringify({
            document: photoDocument.id,
            source: travelerPhotoSource,
          }),
        });
      }
      return result;
    },
    onSuccess: (result) => {
      onChange(result);
      setPassportTraveler(null);
      setPassportOpen(false);
      setPassportImage(null);
      setTravelerPhoto(null);
    },
  });
  const addCharge = useMutation({
    mutationFn: () =>
      apiRequest<BookingRecord>(`/bookings/${booking.id}/charges/`, {
        method: "POST",
        body: JSON.stringify({
          ...charge,
          source_price: charge.source_price || null,
          currency: booking.currency,
        }),
      }),
    onSuccess: (result) => {
      onChange(result);
      setCharge({ ...charge, base_amount: "" });
    },
  });
  const removeCharge = useMutation({
    mutationFn: async (id: string) => {
      await apiRequest<void>(`/bookings/${booking.id}/charges/${id}/`, {
        method: "DELETE",
      });
      return reload();
    },
    onSuccess: onChange,
  });
  const addDiscount = useMutation({
    mutationFn: () =>
      apiRequest<BookingRecord>(
        `/bookings/${booking.id}/charges/${discount.chargeId}/discounts/`,
        { method: "POST", body: JSON.stringify(discount) },
      ),
    onSuccess: (result) => {
      onChange(result);
      setDiscount({ chargeId: "", kind: "AMOUNT", value: "", reason: "" });
    },
  });
  const removeDiscount = useMutation({
    mutationFn: async ({ chargeId, id }: { chargeId: string; id: string }) => {
      await apiRequest<void>(
        `/bookings/${booking.id}/charges/${chargeId}/discounts/${id}/`,
        { method: "DELETE" },
      );
      return reload();
    },
    onSuccess: onChange,
  });
  const addRoom = useMutation({
    mutationFn: () =>
      apiRequest<BookingRecord>(`/bookings/${booking.id}/rooms/`, {
        method: "POST",
        body: JSON.stringify({
          ...roomDraft,
          capacity: Number(roomDraft.capacity),
        }),
      }),
    onSuccess: (result) => {
      onChange(result);
      setRoomDraft({
        trip_hotel: "",
        room_type: "",
        label: "",
        capacity: "2",
        notes: "",
      });
    },
  });
  const removeRoom = useMutation({
    mutationFn: async (id: string) => {
      await apiRequest<void>(`/bookings/${booking.id}/rooms/${id}/`, {
        method: "DELETE",
      });
      return reload();
    },
    onSuccess: onChange,
  });
  const assignRoomTraveler = useMutation({
    mutationFn: ({
      roomId,
      travelerId,
    }: {
      roomId: string;
      travelerId: string;
    }) =>
      apiRequest<BookingRecord>(
        `/bookings/${booking.id}/rooms/${roomId}/travelers/`,
        {
          method: "POST",
          body: JSON.stringify({ booking_traveler_id: travelerId }),
        },
      ),
    onSuccess: onChange,
  });
  const removeRoomTraveler = useMutation({
    mutationFn: async ({
      roomId,
      assignmentId,
    }: {
      roomId: string;
      assignmentId: string;
    }) => {
      await apiRequest<void>(
        `/bookings/${booking.id}/rooms/${roomId}/travelers/${assignmentId}/`,
        { method: "DELETE" },
      );
      return reload();
    },
    onSuccess: onChange,
  });
  const error =
    addTraveler.error ??
    removeTraveler.error ??
    savePassport.error ??
    addCharge.error ??
    removeCharge.error ??
    addDiscount.error ??
    removeDiscount.error ??
    addRoom.error ??
    removeRoom.error ??
    assignRoomTraveler.error ??
    removeRoomTraveler.error ??
    saveContact.error;
  const openPassport = (traveler: BookingTravelerRecord) => {
    const defaultCountry =
      countries.data?.results.find((item) => ["DZ", "DZA"].includes(item.code))
        ?.id ??
      countries.data?.results[0]?.id ??
      "";
    setPassportTraveler(traveler);
    setPassportOpen(true);
    setPassport(
      traveler.passport_details ?? {
        ...blankPassport,
        first_name: traveler.traveler_name.split(" ")[0] ?? "",
        last_name: traveler.traveler_name.split(" ").slice(1).join(" "),
        birth_date: traveler.birth_date ?? "",
        gender: traveler.gender,
        nationality: defaultCountry,
        issuing_country: defaultCountry,
      },
    );
    setPassportImage(null);
    setTravelerPhoto(null);
    savePassport.reset();
  };
  const openScannedTraveler = () => {
    setPassportTraveler(null);
    setPassport(blankPassport);
    setPassportImage(null);
    setTravelerPhoto(null);
    savePassport.reset();
    setPassportOpen(true);
  };
  const prefillCustomer = () =>
    setPerson({
      first_name: booking.customer_first_name,
      last_name: booking.customer_last_name,
      phone: booking.customer_phone,
      birth_date: "",
      gender: "X",
      is_customer_contact: true,
    });
  const pickHotelPrice = (id: string) => {
    const selected = prices.data?.results.find((item) => item.id === id);
    setCharge({
      ...charge,
      source_price: id,
      kind: "ACCOMMODATION",
      description: selected
        ? `${selected.hotel_name} · ${selected.room_type_name}`
        : "Accommodation",
      base_amount: selected?.amount ?? "",
    });
  };
  const selectedPriceTraveler = booking.travelers.find(
    (item) => item.id === charge.booking_traveler_id,
  );
  const compatibleHotelPrices = (prices.data?.results ?? []).filter(
    (item) =>
      !selectedPriceTraveler ||
      item.passenger_category === selectedPriceTraveler.passenger_category,
  );
  const hotelOptions = (accommodationPlan.data?.stops ?? []).flatMap((stop) =>
    stop.hotels.map((hotel) => ({
      id: hotel.id,
      label: `${stop.city_name} · ${hotel.hotel_name}`,
    })),
  );
  const selectedRoomType = roomTypes.data?.results.find(
    (item) => item.id === roomDraft.room_type,
  );

  return (
    <div className="space-y-6">
      <Readiness booking={booking} />
      <Step
        title={t("1. Customer contact")}
        hint={t(
          "The customer may or may not travel, but the agency must be able to contact them later.",
        )}
      >
        <div className="grid gap-3 p-5 md:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_1fr_auto]">
          <input
            className={field}
            placeholder={t("First name")}
            value={contact.first_name}
            onChange={(event) =>
              setContact({ ...contact, first_name: event.target.value })
            }
          />
          <input
            className={field}
            placeholder={t("Last name")}
            value={contact.last_name}
            onChange={(event) =>
              setContact({ ...contact, last_name: event.target.value })
            }
          />
          <input
            className={field}
            placeholder={t("Phone")}
            value={contact.phone}
            onChange={(event) =>
              setContact({ ...contact, phone: event.target.value })
            }
          />
          <input
            className={field}
            type="email"
            placeholder={t("Email")}
            value={contact.email}
            onChange={(event) =>
              setContact({ ...contact, email: event.target.value })
            }
          />
          <button
            className={primary}
            disabled={
              !(contact.phone || contact.email) || saveContact.isPending
            }
            onClick={() => saveContact.mutate()}
          >
            {t("Save contact")}
          </button>
          <input
            className={`${field} md:col-span-2 lg:col-span-4`}
            placeholder={t("Address (optional)")}
            value={contact.address}
            onChange={(event) =>
              setContact({ ...contact, address: event.target.value })
            }
          />
          {!booking.travelers.some((item) => item.is_customer_contact) &&
            booking.customer_first_name && (
              <button
                className="rounded-lg border px-3 py-2 text-sm text-cyan-800"
                onClick={prefillCustomer}
              >
                {t("Customer is traveling")}
              </button>
            )}
        </div>
        <MutationMessage error={saveContact.error} />
      </Step>
      <Step
        title={t("2. Travelers")}
        hint={`${t("Age category is calculated on the return date:")} ${booking.return_date}. ${t("Passports can be scanned now or completed later in follow-up.")}`}
      >
        <div className="flex justify-end px-5 pt-5">
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-cyan-300 bg-cyan-50 px-3 py-2 text-sm font-medium text-cyan-900"
            onClick={openScannedTraveler}
          >
            <FileScan className="size-4" />
            {t("Add traveler from passport scan")}
          </button>
        </div>
        <div className="grid gap-3 p-5 lg:grid-cols-[1fr_1fr_150px_120px_100px_auto]">
          <input
            className={field}
            placeholder={t("First name")}
            value={person.first_name}
            onChange={(event) =>
              setPerson({ ...person, first_name: event.target.value })
            }
          />
          <input
            className={field}
            placeholder={t("Last name")}
            value={person.last_name}
            onChange={(event) =>
              setPerson({ ...person, last_name: event.target.value })
            }
          />
          <input
            className={field}
            type="date"
            value={person.birth_date}
            onChange={(event) =>
              setPerson({ ...person, birth_date: event.target.value })
            }
          />
          <select
            className={field}
            value={person.gender}
            onChange={(event) =>
              setPerson({
                ...person,
                gender: event.target.value as PersonDraft["gender"],
              })
            }
          >
            <option value="X">{t("Gender")}</option>
            <option value="M">{t("Male")}</option>
            <option value="F">{t("Female")}</option>
          </select>
          <span className="grid place-items-center rounded-lg bg-slate-100 text-sm font-semibold">
            {t(categoryFor(person.birth_date, booking.return_date) ?? "—")}
          </span>
          <button
            className={primary}
            disabled={
              !(person.first_name || person.last_name) || !person.birth_date
            }
            onClick={() => addTraveler.mutate()}
          >
            <UserPlus className="size-4" />
            {t("Add")}
          </button>
        </div>
        <div className="divide-y">
          {booking.travelers.map((item) => (
            <TravelerRow
              key={item.id}
              traveler={item}
              currency={booking.currency_code}
              onPassport={() => openPassport(item)}
              onRemove={() => removeTraveler.mutate(item.id)}
            />
          ))}
        </div>
      </Step>
      <Step
        title={t("3. Rooms and occupancy")}
        hint={t(
          "Create or replace room groups while the client is deciding. The room capacity can change without freezing the booking price.",
        )}
      >
        <div className="grid gap-3 p-5 lg:grid-cols-[1fr_1fr_150px_1fr_auto]">
          <select
            className={field}
            value={roomDraft.trip_hotel}
            onChange={(event) =>
              setRoomDraft({ ...roomDraft, trip_hotel: event.target.value })
            }
          >
            <option value="">{t("Hotel stop")}</option>
            {hotelOptions.map((hotel) => (
              <option key={hotel.id} value={hotel.id}>
                {hotel.label}
              </option>
            ))}
          </select>
          <select
            className={field}
            value={roomDraft.room_type}
            onChange={(event) =>
              setRoomDraft({ ...roomDraft, room_type: event.target.value })
            }
          >
            <option value="">{t("Room type")}</option>
            {roomTypes.data?.results.map((type) => (
              <option key={type.id} value={type.id}>
                {type.name}
              </option>
            ))}
          </select>
          <input
            className={field}
            type="number"
            min="1"
            value={roomDraft.capacity}
            onChange={(event) =>
              setRoomDraft({ ...roomDraft, capacity: event.target.value })
            }
            placeholder={t("Capacity")}
            aria-label={t("Capacity")}
          />
          <input
            className={field}
            value={roomDraft.label}
            onChange={(event) =>
              setRoomDraft({ ...roomDraft, label: event.target.value })
            }
            placeholder={t("Room label, e.g. Room 1")}
          />
          <button
            className={primary}
            disabled={
              !roomDraft.trip_hotel ||
              !roomDraft.room_type ||
              !roomDraft.label ||
              addRoom.isPending
            }
            onClick={() => addRoom.mutate()}
          >
            <Plus className="size-4" />
            {t("Add room")}
          </button>
        </div>
        <MutationMessage
          error={accommodationPlan.error || roomTypes.error || addRoom.error}
        />
        {selectedRoomType && (
          <p className="px-5 pb-3 text-xs text-slate-500">
            {selectedRoomType.name} ·{" "}
            {t("capacity is editable for this booking")}
          </p>
        )}
        <div className="divide-y">
          {booking.room_groups.map((room) => (
            <div
              key={room.id}
              className="grid gap-3 p-4 lg:grid-cols-[1fr_1fr_220px_auto] lg:items-center"
            >
              <div>
                <p className="flex items-center gap-2 font-medium">
                  <BedDouble className="size-4 text-cyan-700" />
                  {room.label}
                </p>
                <p className="text-sm text-slate-500">
                  {room.hotel_name} · {room.room_type_name} · {room.capacity}{" "}
                  {t("places")}
                </p>
              </div>
              <div className="text-sm">
                {room.traveler_assignments.length ? (
                  room.traveler_assignments.map((assignment) => (
                    <span
                      key={assignment.id}
                      className="mr-2 inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-1"
                    >
                      {assignment.traveler_name}
                      <button
                        className="text-red-700"
                        onClick={() =>
                          removeRoomTraveler.mutate({
                            roomId: room.id,
                            assignmentId: assignment.id,
                          })
                        }
                        aria-label={t("Remove traveler")}
                      >
                        x
                      </button>
                    </span>
                  ))
                ) : (
                  <span className="text-slate-500">
                    {t("No travelers assigned yet")}
                  </span>
                )}
              </div>
              <select
                className={field}
                value=""
                onChange={(event) => {
                  if (event.target.value)
                    assignRoomTraveler.mutate({
                      roomId: room.id,
                      travelerId: event.target.value,
                    });
                }}
                disabled={room.traveler_assignments.length >= room.capacity}
              >
                <option value="">{t("Assign traveler")}</option>
                {booking.travelers
                  .filter(
                    (traveler) =>
                      !traveler.room_assignments.some(
                        (assignment) => assignment.room_group === room.id,
                      ),
                  )
                  .map((traveler) => (
                    <option key={traveler.id} value={traveler.id}>
                      {traveler.traveler_name}
                    </option>
                  ))}
              </select>
              <button
                className="text-sm text-red-700"
                onClick={() => removeRoom.mutate(room.id)}
              >
                {t("Remove room")}
              </button>
            </div>
          ))}
          {!booking.room_groups.length && (
            <p className="p-5 text-sm text-slate-500">
              {t(
                "No rooms added yet. Add one here when the client chooses an occupancy.",
              )}
            </p>
          )}
        </div>
      </Step>
      <Step
        title={t("4. Final price per traveler")}
        hint={t(
          "Add the final package price or detailed service lines, then apply a fixed or percentage reduction with a reason.",
        )}
      >
        <div className="grid gap-3 p-5 lg:grid-cols-3">
          <select
            className={field}
            value={charge.booking_traveler_id}
            onChange={(event) =>
              setCharge({
                ...charge,
                booking_traveler_id: event.target.value,
                source_price: "",
                base_amount: "",
              })
            }
          >
            <option value="">{t("Traveler")}</option>
            {booking.travelers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.traveler_name}
              </option>
            ))}
          </select>
          <select
            className={field}
            value={charge.source_price}
            onChange={(event) => pickHotelPrice(event.target.value)}
          >
            <option value="">{t("Custom final price")}</option>
            {compatibleHotelPrices.map((item) => (
              <option key={item.id} value={item.id}>
                {item.hotel_name} · {item.room_type_name} ·{" "}
                {t(item.passenger_category_name)} · {t(item.bed_basis)} ·{" "}
                {item.amount} {item.currency_code}
              </option>
            ))}
          </select>
          <select
            className={field}
            value={charge.kind}
            onChange={(event) =>
              setCharge({ ...charge, kind: event.target.value })
            }
          >
            <option value="SERVICE">{t("Package / service")}</option>
            <option value="ACCOMMODATION">{t("Accommodation")}</option>
            <option value="TRANSPORT">{t("Transport")}</option>
            <option value="VISA">{t("Visa")}</option>
            <option value="OTHER">{t("Other")}</option>
          </select>
          <input
            className={field}
            value={charge.description}
            onChange={(event) =>
              setCharge({ ...charge, description: event.target.value })
            }
            placeholder={t("Description")}
          />
          <input
            className={field}
            min="0"
            step="0.0001"
            type="number"
            value={charge.base_amount}
            onChange={(event) =>
              setCharge({ ...charge, base_amount: event.target.value })
            }
            placeholder={t("Selling amount")}
          />
          <button
            className={primary}
            disabled={
              !charge.booking_traveler_id ||
              !charge.description ||
              !charge.base_amount
            }
            onClick={() => addCharge.mutate()}
          >
            <Plus className="size-4" />
            {t("Add price")}
          </button>
        </div>
        <div className="divide-y">
          {booking.travelers.map((traveler) => (
            <div key={traveler.id} className="p-4">
              <div className="flex justify-between">
                <b>{traveler.traveler_name}</b>
                <b>
                  {traveler.final_amount} {booking.currency_code}
                </b>
              </div>
              {traveler.charges.map((item) => (
                <div
                  key={item.id}
                  className="mt-2 rounded bg-slate-50 p-3 text-sm"
                >
                  <div className="flex justify-between">
                    <span>
                      {item.description}
                      <small className="block text-slate-500">
                        {t("Base")} {item.base_amount} · {t("Reduction")}{" "}
                        {item.discount_amount}
                      </small>
                    </span>
                    <span>
                      <b>
                        {item.final_amount} {item.currency_code}
                      </b>
                      <button
                        className="ml-3 text-cyan-800"
                        onClick={() =>
                          setDiscount({ ...discount, chargeId: item.id })
                        }
                      >
                        {t("Reduction")}
                      </button>
                      <button
                        className="ml-3 text-red-700"
                        onClick={() => removeCharge.mutate(item.id)}
                      >
                        <Trash2 className="inline size-4" />
                      </button>
                    </span>
                  </div>
                  {item.discounts.map((cut) => (
                    <div
                      key={cut.id}
                      className="mt-2 flex justify-between text-xs text-slate-500"
                    >
                      <span>
                        {cut.reason} · {cut.kind} {cut.value}
                      </span>
                      <button
                        className="text-red-700"
                        onClick={() =>
                          removeDiscount.mutate({
                            chargeId: item.id,
                            id: cut.id,
                          })
                        }
                      >
                        {t("Remove")}
                      </button>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </Step>
      {discount.chargeId && (
        <Step
          title={t("5. Apply reduction")}
          hint={t("Every commercial reduction remains traceable.")}
        >
          <div className="grid gap-3 p-5 md:grid-cols-[140px_160px_1fr_auto]">
            <select
              className={field}
              value={discount.kind}
              onChange={(event) =>
                setDiscount({ ...discount, kind: event.target.value })
              }
            >
              <option value="AMOUNT">{t("Fixed amount")}</option>
              <option value="PERCENT">{t("Percentage")}</option>
            </select>
            <input
              className={field}
              min="0"
              type="number"
              value={discount.value}
              onChange={(event) =>
                setDiscount({ ...discount, value: event.target.value })
              }
              placeholder={t("Value")}
            />
            <input
              className={field}
              value={discount.reason}
              onChange={(event) =>
                setDiscount({ ...discount, reason: event.target.value })
              }
              placeholder={t("Reason / authorization note")}
            />
            <button
              className={primary}
              disabled={!discount.value || !discount.reason}
              onClick={() => addDiscount.mutate()}
            >
              <BadgePercent className="size-4" />
              {t("Apply")}
            </button>
          </div>
        </Step>
      )}
      <ClientReview booking={booking} onChange={onChange} />
      <MutationMessage error={error} />
      <PassportDialog
        bookingId={booking.id}
        open={passportOpen}
        traveler={passportTraveler}
        draft={passport}
        setDraft={setPassport}
        countries={countries.data?.results ?? []}
        image={passportImage}
        setImage={setPassportImage}
        photo={travelerPhoto}
        setPhoto={(file, source) => {
          setTravelerPhoto(file);
          setTravelerPhotoSource(source);
        }}
        save={savePassport}
        onClose={() => {
          setPassportTraveler(null);
          setPassportOpen(false);
        }}
      />
    </div>
  );
}

function Readiness({ booking }: Readonly<{ booking: BookingRecord }>) {
  const uiText = useUiText();
  const t = useOperationalText();
  const r = booking.readiness;
  const commercialItems = [
    ["Travelers", r.traveler_count, r.traveler_count > 0],
    ["Missing prices", r.missing_prices, r.missing_prices === 0],
    [
      "Price category mismatches",
      r.price_category_mismatches,
      r.price_category_mismatches === 0,
    ],
  ] as const;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section
        className={`rounded-xl border p-5 ${r.commercial_ready ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}
      >
        <h2 className="font-semibold">{t("Commercial confirmation")}</h2>
        <p className="text-sm">
          {uiText("Customer contact:")}{" "}
          {r.contact_complete ? t("complete") : t("missing phone or email")}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {commercialItems.map(([label, value, good]) => (
            <span
              key={label}
              className={`rounded-full px-3 py-1 text-xs font-medium ${good ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}
            >
              {t(label)}: {value}
            </span>
          ))}
        </div>
      </section>
      <section className="rounded-xl border border-blue-200 bg-blue-50 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">{t("Operational follow-up")}</h2>
            <p className="text-sm text-blue-900">
              {t("These items do not prevent commercial confirmation.")}
            </p>
          </div>
          <a
            href={`/trips/${booking.trip}#accommodation-allocation`}
            className="text-sm font-medium text-cyan-800 underline"
          >
            {t("Open Allocation tab")}
          </a>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-full bg-white px-3 py-1 text-xs text-slate-700">
            {t("Missing passports:")} {r.missing_passports}
          </span>
          <span className="rounded-full bg-white px-3 py-1 text-xs text-slate-700">
            {t("Invalid passports:")} {r.invalid_passports}
          </span>
          <span className="rounded-full bg-white px-3 py-1 text-xs text-slate-700">
            {t("Allocation:")} {t(r.allocation_status)}
          </span>
          <span className="rounded-full bg-white px-3 py-1 text-xs text-slate-700">
            {t("Placements:")} {r.completed_room_assignments}/
            {r.required_room_assignments}
          </span>
        </div>
        {r.operational_ready && (
          <p className="mt-3 text-xs font-medium text-emerald-700">
            {t("Passport and accommodation follow-up is complete.")}
          </p>
        )}
      </section>
    </div>
  );
}
function TravelerRow({
  traveler,
  currency,
  onPassport,
  onRemove,
}: Readonly<{
  traveler: BookingTravelerRecord;
  currency: string;
  onPassport: () => void;
  onRemove: () => void;
}>) {
  const t = useOperationalText();
  const passportColor = traveler.passport_is_valid
    ? "text-emerald-700"
    : "text-red-700";
  return (
    <div className="grid gap-3 p-4 md:grid-cols-[1fr_1fr_auto]">
      <div>
        <div className="flex items-center gap-2">
          <b>{traveler.traveler_name}</b>
          {traveler.is_customer_contact && (
            <span className="rounded-full bg-cyan-50 px-2 py-1 text-xs text-cyan-800">
              {t("Customer")}
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500">
          {t(traveler.gender_display)} · {t("age on return")}{" "}
          {traveler.age_on_return ?? "—"} ·{" "}
          <b>{t(traveler.derived_passenger_category ?? "—")}</b>
        </p>
      </div>
      <div>
        <p className={`text-sm ${passportColor}`}>
          {traveler.passport_number
            ? `${traveler.passport_number} · ${t("expires")} ${traveler.passport_expiry_date}`
            : t("Passport missing")}
        </p>
        <p className="text-xs text-slate-500">
          {t("Required until")} {traveler.passport_required_until} ·{" "}
          {traveler.final_amount} {currency} ·{" "}
          {t("allocation follows confirmation")}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <button
          className="inline-flex items-center gap-1 text-sm text-cyan-800"
          onClick={onPassport}
        >
          <FileScan className="size-4" />
          {traveler.passport_id
            ? t("Edit passport")
            : t("Scan / enter passport")}
        </button>
        <button className="text-red-700" onClick={onRemove}>
          <Trash2 className="size-4" />
        </button>
      </div>
    </div>
  );
}
function PassportDialog({
  bookingId,
  open,
  traveler,
  draft,
  setDraft,
  countries,
  image,
  setImage,
  photo,
  setPhoto,
  save,
  onClose,
}: Readonly<{
  bookingId: string;
  open: boolean;
  traveler: BookingTravelerRecord | null;
  draft: PassportDraft;
  setDraft: (draft: PassportDraft) => void;
  countries: Country[];
  image: File | null;
  setImage: (file: File | null) => void;
  photo: File | null;
  setPhoto: (
    file: File,
    source: "PASSPORT_AUTO_CROP" | "PASSPORT_MANUAL_CROP",
  ) => void;
  save: { mutate: () => void; isPending: boolean; error: Error | null };
  onClose: () => void;
}>) {
  const t = useOperationalText();
  const [mrzWarnings, setMrzWarnings] = useState<string[]>([]);
  const change = (key: keyof PassportDraft, value: string) => {
    if (key === "mrz") setMrzWarnings([]);
    setDraft({ ...draft, [key]: value });
  };
  const parse = useMutation({
    mutationFn: () =>
      apiRequest<
        Partial<PassportDraft> & {
          nationality_code?: string;
          issuing_country_code?: string;
          mrz_warnings?: string[];
        }
      >(`/bookings/${bookingId}/parse-passport-mrz/`, {
        method: "POST",
        body: JSON.stringify({ mrz: draft.mrz }),
      }),
    onSuccess: (value) => {
      setMrzWarnings(value.mrz_warnings ?? []);
      const countryId = (code?: string) =>
        countries.find(
          (item) =>
            item.code === code || (code === "DZA" && item.code === "DZ"),
        )?.id ?? "";
      setDraft({
        ...draft,
        ...value,
        nationality: countryId(value.nationality_code) || draft.nationality,
        issuing_country:
          countryId(value.issuing_country_code) || draft.issuing_country,
      });
    },
  });
  return (
    <FormDialog
      open={open}
      onClose={onClose}
      title={
        traveler
          ? `${t("Passport")} · ${traveler.traveler_name}`
          : t("Add traveler from passport")
      }
      description={
        traveler
          ? t(
              "Upload the passport scan and verify every legal field before saving.",
            )
          : t(
              "OCR fills the identity fields first; saving creates both the traveler and passport.",
            )
      }
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
        className="space-y-4"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <PassportScanAssistant
              file={image}
              setFile={setImage}
              mrz={draft.mrz}
              setMrz={(value) => change("mrz", value)}
              onPhoto={setPhoto}
            />
            {photo && (
              <p className="mt-2 text-xs text-emerald-700">
                {t("Cropped traveler photo ready:")} {photo.name}
              </p>
            )}
            <button
              type="button"
              disabled={!draft.mrz.trim() || parse.isPending}
              onClick={() => parse.mutate()}
              className="mt-2 rounded-lg border px-3 py-2 text-sm text-cyan-800 disabled:opacity-40"
            >
              {t("Validate MRZ and fill passport data")}
            </button>
            {parse.isSuccess && mrzWarnings.length === 0 && (
              <p className="mt-2 text-xs text-emerald-700">
                {t(
                  "Passport number, birth date, expiry date, and the complete MRZ checksum were verified.",
                )}
              </p>
            )}
            {mrzWarnings.length > 0 && (
              <p className="mt-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
                {t(
                  "Core identity fields were verified and filled. Review these unverified fields against the passport image before saving:",
                )}{" "}
                {mrzWarnings.join(t(" and "))}
              </p>
            )}
          </div>
          <Field label={t("Passport number")}>
            <input
              required
              className="input uppercase"
              value={draft.passport_number}
              onChange={(event) =>
                change("passport_number", event.target.value)
              }
            />
          </Field>
          <Field label={t("First name")}>
            <input
              required
              className="input"
              value={draft.first_name}
              onChange={(event) => change("first_name", event.target.value)}
            />
          </Field>
          <Field label={t("Middle name")}>
            <input
              className="input"
              value={draft.middle_name}
              onChange={(event) => change("middle_name", event.target.value)}
            />
          </Field>
          <Field label={t("Last name")}>
            <input
              required
              className="input"
              value={draft.last_name}
              onChange={(event) => change("last_name", event.target.value)}
            />
          </Field>
          <Field label={t("Birth date")}>
            <input
              required
              type="date"
              className="input"
              value={draft.birth_date}
              onChange={(event) => change("birth_date", event.target.value)}
            />
          </Field>
          <SelectField
            label={t("Gender")}
            value={draft.gender}
            onChange={(value) => change("gender", value)}
            options={[
              ["M", "Male"],
              ["F", "Female"],
              ["X", "Unspecified"],
            ]}
          />
          <CountryField
            label={t("Nationality")}
            value={draft.nationality}
            countries={countries}
            onChange={(value) => change("nationality", value)}
          />
          <CountryField
            label={t("Issuing country")}
            value={draft.issuing_country}
            countries={countries}
            onChange={(value) => change("issuing_country", value)}
          />
          <Field label={t("Issue date")}>
            <input
              required
              type="date"
              className="input"
              value={draft.issue_date}
              onChange={(event) => change("issue_date", event.target.value)}
            />
          </Field>
          <Field label={t("Expiry date")}>
            <input
              required
              type="date"
              className="input"
              value={draft.expiry_date}
              onChange={(event) => change("expiry_date", event.target.value)}
            />
          </Field>
          <Field label={t("Birth place")}>
            <input
              className="input"
              value={draft.birth_place}
              onChange={(event) => change("birth_place", event.target.value)}
            />
          </Field>
          <Field label={t("Issue place")}>
            <input
              className="input"
              value={draft.issue_place}
              onChange={(event) => change("issue_place", event.target.value)}
            />
          </Field>
        </div>
        <MutationMessage error={save.error ?? parse.error} />
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border px-4 py-2"
          >
            {t("Cancel")}
          </button>
          <button disabled={save.isPending} className={primary}>
            {t("Save passport")}
          </button>
        </div>
      </form>
    </FormDialog>
  );
}
function Step({
  title,
  hint,
  children,
}: Readonly<{ title: string; hint: string; children: React.ReactNode }>) {
  return (
    <section className="rounded-xl border bg-white">
      <header className="border-b p-5">
        <h2 className="font-semibold">{title}</h2>
        <p className="text-sm text-slate-500">{hint}</p>
      </header>
      {children}
    </section>
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
      <div className="mt-1 [&_.input]:w-full [&_.input]:rounded-lg [&_.input]:border [&_.input]:px-3 [&_.input]:py-2">
        {children}
      </div>
    </label>
  );
}
function SelectField({
  label,
  value,
  onChange,
  options,
}: Readonly<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[][];
}>) {
  const t = useOperationalText();
  return (
    <Field label={label}>
      <select
        required
        className="input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((item) => (
          <option key={item[0]} value={item[0]}>
            {t(item[1])}
          </option>
        ))}
      </select>
    </Field>
  );
}
function CountryField({
  label,
  value,
  countries,
  onChange,
}: Readonly<{
  label: string;
  value: string;
  countries: Country[];
  onChange: (value: string) => void;
}>) {
  const t = useOperationalText();
  return (
    <Field label={label}>
      <select
        required
        className="input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{t("Select country")}</option>
        {countries.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>
    </Field>
  );
}
function categoryFor(
  birth: string,
  returned: string,
): "INF" | "CHD" | "ADT" | null {
  if (!birth || !returned) return null;
  const born = new Date(`${birth}T00:00:00`);
  const end = new Date(`${returned}T00:00:00`);
  let age = end.getFullYear() - born.getFullYear();
  if (
    end.getMonth() < born.getMonth() ||
    (end.getMonth() === born.getMonth() && end.getDate() < born.getDate())
  )
    age -= 1;
  return age < 2 ? "INF" : age < 12 ? "CHD" : "ADT";
}
