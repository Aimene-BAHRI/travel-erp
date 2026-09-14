"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BedDouble,
  CheckCircle2,
  GripVertical,
  Printer,
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { FormDialog } from "@/components/forms/form-dialog";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { RoomTypeRecord } from "@/features/catalog/types";
import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";

function useAllocationText() {
  const { locale } = useLocale();
  return (en: string, ar: string) => locale === "ar" ? ar : en;
}

const allocationLabels: Record<string, [string, string]> = {
  M: ["Male", "ذكر"], F: ["Female", "أنثى"], X: ["Unspecified", "غير محدد"],
  Male: ["Male", "ذكور"], Female: ["Female", "إناث"], Unspecified: ["Unspecified", "غير محدد"],
  ADULT: ["Adult", "بالغ"], CHILD: ["Child", "طفل"], INFANT: ["Infant", "رضيع"],
  ANY: ["Any travelers", "جميع المسافرين"], MALE_ONLY: ["Male only", "ذكور فقط"],
  FEMALE_ONLY: ["Female only", "إناث فقط"], FAMILY: ["Family / approved mixed", "عائلة / مختلط بموافقة"],
};

function allocationLabel(value: string, t: (en: string, ar: string) => string) {
  const pair = allocationLabels[value];
  return pair ? t(...pair) : value;
}

import type {
  AccommodationPlan,
  AccommodationTravelerRecord,
  TripAllocationRoomRecord,
} from "./types";

type RoomDraft = {
  trip_hotel: string;
  room_type: string;
  label: string;
  actual_room_number: string;
  standard_beds: number;
  occupancy_policy: TripAllocationRoomRecord["occupancy_policy"];
  notes: string;
};

const emptyRoom: RoomDraft = {
  trip_hotel: "",
  room_type: "",
  label: "",
  actual_room_number: "",
  standard_beds: 1,
  occupancy_policy: "ANY",
  notes: "",
};

export function TripAccommodationAllocation({
  tripId,
}: Readonly<{ tripId: string }>) {
  const t = useAllocationText();
  const cache = useQueryClient();
  const [selectedStopId, setSelectedStopId] = useState("");
  const [selectedHotelId, setSelectedHotelId] = useState("");
  const [selectedTravelerId, setSelectedTravelerId] = useState("");
  const [groupBy, setGroupBy] = useState<"booking" | "gender">("booking");
  const [showAssigned, setShowAssigned] = useState(false);
  const [roomOpen, setRoomOpen] = useState(false);
  const [roomDraft, setRoomDraft] = useState<RoomDraft>(emptyRoom);
  const plan = useQuery({
    queryKey: ["trip-accommodation-plan", tripId],
    queryFn: () =>
      apiRequest<AccommodationPlan>(`/trips/${tripId}/accommodation-plan/`),
  });
  const roomTypes = useQuery({
    queryKey: ["room-types"],
    queryFn: () =>
      apiRequest<Paginated<RoomTypeRecord>>(
        "/catalog/room-types/?ordering=sort_order,name",
      ),
  });
  const refresh = () =>
    cache.invalidateQueries({ queryKey: ["trip-accommodation-plan", tripId] });

  const selectedStop = plan.data?.stops.find(
    (stop) => stop.id === selectedStopId,
  );
  const selectedHotel = selectedStop?.hotels.find(
    (hotel) => hotel.id === selectedHotelId,
  );
  useEffect(() => {
    if (!selectedStopId && plan.data?.stops[0])
      setSelectedStopId(plan.data.stops[0].id);
  }, [plan.data, selectedStopId]);
  useEffect(() => {
    if (
      selectedStop &&
      !selectedStop.hotels.some((hotel) => hotel.id === selectedHotelId)
    ) {
      setSelectedHotelId(selectedStop.hotels[0]?.id ?? "");
    }
  }, [selectedHotelId, selectedStop]);

  const saveRoom = useMutation({
    mutationFn: () =>
      apiRequest<TripAllocationRoomRecord>("/trips/allocation-rooms/", {
        method: "POST",
        body: JSON.stringify({ ...roomDraft, extra_beds: 0 }),
      }),
    onSuccess: () => {
      setRoomOpen(false);
      setRoomDraft(emptyRoom);
      refresh();
    },
  });
  const assign = useMutation({
    mutationFn: ({
      roomId,
      travelerId,
      bedNumber,
    }: {
      roomId: string;
      travelerId: string;
      bedNumber: number;
    }) =>
      apiRequest(`/trips/allocation-rooms/${roomId}/assign/`, {
        method: "POST",
        body: JSON.stringify({
          booking_traveler: travelerId,
          bed_number: bedNumber,
        }),
      }),
    onSuccess: () => {
      setSelectedTravelerId("");
      refresh();
    },
  });
  const addBed = useMutation({
    mutationFn: (room: TripAllocationRoomRecord) =>
      apiRequest(`/trips/allocation-rooms/${room.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ extra_beds: room.extra_beds + 1 }),
      }),
    onSuccess: refresh,
  });
  const removeAssignment = useMutation({
    mutationFn: (id: string) =>
      apiRequest(`/trips/room-assignments/${id}/`, { method: "DELETE" }),
    onSuccess: refresh,
  });
  const deleteRoom = useMutation({
    mutationFn: (id: string) =>
      apiRequest(`/trips/allocation-rooms/${id}/`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  const visibleTravelers = (plan.data?.travelers ?? []).filter((traveler) =>
    traveler.required_stops.includes(selectedStopId) &&
    (showAssigned || !traveler.assignments.some((item) => item.stop === selectedStopId)),
  );
  const groups = useMemo(() => {
    return visibleTravelers.reduce<
      Record<string, AccommodationTravelerRecord[]>
    >((result, traveler) => {
      const key =
        groupBy === "booking"
          ? `${traveler.booking_code} · ${traveler.group_name}`
          : traveler.gender === "M"
            ? "Male"
            : traveler.gender === "F"
              ? "Female"
              : "Unspecified";
      (result[key] ??= []).push(traveler);
      return result;
    }, {});
  }, [groupBy, visibleTravelers]);

  const openRoom = () => {
    if (!selectedHotel) return;
    const defaultType = roomTypes.data?.results.find((item) => item.is_active);
    setRoomDraft({
      ...emptyRoom,
      trip_hotel: selectedHotel.id,
      room_type: defaultType?.id ?? "",
      standard_beds: defaultType?.default_standard_beds ?? 1,
    });
    setRoomOpen(true);
  };
  const placeTraveler = (
    roomId: string,
    bedNumber: number,
    draggedId?: string,
  ) => {
    const travelerId = draggedId || selectedTravelerId;
    if (travelerId) assign.mutate({ roomId, travelerId, bedNumber });
  };

  if (!plan.data)
    return (
      <section className="rounded-xl border bg-white p-6 text-sm text-slate-500">
        {t("Loading accommodation allocation…", "جارٍ تحميل توزيع السكن…")}
      </section>
    );
  return (
    <section
      id="accommodation-allocation"
      className="rounded-xl border border-slate-200 bg-white"
    >
      <header className="flex flex-wrap items-center justify-between gap-4 border-b p-5">
        <div>
          <h2 className="flex items-center gap-2 font-semibold">
            <BedDouble className="size-5 text-cyan-800" />
            {t("Trip accommodation allocation", "توزيع السكن للرحلة")}
          </h2>
          <p className="text-sm text-slate-500">
            {t("Allocate every confirmed traveler once at each hotel stay.", "وزّع كل مسافر مؤكد على غرفة في كل إقامة فندقية.")}
          </p>
        </div>
        <div
          className={`rounded-full px-3 py-1 text-sm font-medium ${plan.data.summary.is_complete ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}
        >
          {plan.data.summary.assignment_count} /{" "}
          {plan.data.summary.required_assignment_count} {t("placements", "توزيع")}{" "}
          {plan.data.summary.is_complete && (
            <CheckCircle2 className="ms-1 inline size-4" />
          )}
        </div>
      </header>
      {!plan.data.stops.length ? (
        <p className="p-6 text-sm text-amber-800">
          {t("Assign at least one hotel to an itinerary stop first.", "أضف فندقًا واحدًا على الأقل إلى إحدى محطات الرحلة أولًا.")}
        </p>
      ) : (
        <>
          <nav className="flex gap-2 overflow-x-auto border-b p-4">
            {plan.data.stops.map((stop) => (
              <div
                key={stop.id}
                className={`flex shrink-0 items-stretch overflow-hidden rounded-lg border ${stop.id === selectedStopId ? "border-cyan-700 bg-cyan-50 text-cyan-900" : "border-slate-200"}`}
              >
                <button
                  onClick={() => setSelectedStopId(stop.id)}
                  className="px-4 py-2 text-start text-sm"
                >
                  <b>
                    {stop.order}. {stop.city_name}
                  </b>
                  <span className="ms-2 text-xs">
                    {stop.assigned_count}/{plan.data.summary.traveler_count}
                  </span>
                  <p className="text-xs text-slate-500">
                    {stop.arrival_date} → {stop.departure_date}
                  </p>
                </button>
                <Link
                  href={`/trips/${tripId}/accommodation/${stop.id}`}
                  title={t(`Print or download ${stop.city_name} accommodation list`, `طباعة أو تحميل قائمة السكن في ${stop.city_name}`)}
                  className="grid place-items-center border-s px-3 text-cyan-800 hover:bg-cyan-100"
                >
                  <Printer className="size-4" />
                  <span className="sr-only">{t("Print", "طباعة")} {stop.city_name}</span>
                </Link>
              </div>
            ))}
          </nav>
          {selectedStop && (
            <div className="grid min-h-[480px] gap-0 xl:grid-cols-[340px_1fr]">
              <aside className="border-e bg-slate-50 p-4">
                <div className="flex items-center justify-between">
                  <h3 className="flex items-center gap-2 font-semibold">
                    <Users className="size-4" />
                    {t("Travelers", "المسافرون")}
                  </h3>
                  <span className="text-xs text-slate-500">
                    {selectedStop.unassigned_count} {t("unassigned", "غير موزع")}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <select
                    value={groupBy}
                    onChange={(event) =>
                      setGroupBy(event.target.value as typeof groupBy)
                    }
                    className="rounded-lg border bg-white px-2 py-2 text-xs"
                  >
                    <option value="booking">{t("Group by booking", "تجميع حسب الحجز")}</option>
                    <option value="gender">{t("Group by gender", "تجميع حسب الجنس")}</option>
                  </select>
                  <label className="flex items-center gap-2 rounded-lg border bg-white px-2 text-xs">
                    <input
                      type="checkbox"
                      checked={showAssigned}
                      onChange={(event) =>
                        setShowAssigned(event.target.checked)
                      }
                    />
                    {t("Show assigned", "إظهار المسافرين الموزعين")}
                  </label>
                </div>
                <div className="mt-4 max-h-[600px] space-y-4 overflow-y-auto">
                  {Object.entries(groups).map(([name, travelers]) => (
                    <div key={name}>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {allocationLabel(name, t)}
                      </p>
                      <div className="space-y-2">
                        {travelers.map((traveler) => {
                          const assigned = traveler.assignments.find(
                            (item) => item.stop === selectedStopId,
                          );
                          const preference = traveler.preferences.find(
                            (item) => item.stop === selectedStopId,
                          );
                          return (
                            <button
                              type="button"
                              draggable={traveler.eligible_for_room}
                              disabled={!traveler.eligible_for_room}
                              onDragStart={(event) =>
                                event.dataTransfer.setData(
                                  "text/traveler",
                                  traveler.id,
                                )
                              }
                              onClick={() => setSelectedTravelerId(traveler.id)}
                              key={traveler.id}
                              className={`w-full cursor-grab rounded-lg border bg-white p-3 text-start text-sm shadow-sm ${selectedTravelerId === traveler.id ? "border-cyan-700 ring-2 ring-cyan-100" : "border-slate-200"}`}
                            >
                              <span className="flex items-start gap-2">
                                <GripVertical className="mt-0.5 size-4 text-slate-400" />
                                <TravelerAvatar
                                  name={traveler.name}
                                  photoUrl={traveler.photo_url}
                                />
                                <span className="min-w-0">
                                  <b className="block truncate">
                                    {traveler.name}
                                  </b>
                                  <span className="text-xs text-slate-500">
                                    {allocationLabel(traveler.gender, t)} ·{" "}
                                    {allocationLabel(traveler.passenger_category, t)}
                                  </span>
                                  {!traveler.eligible_for_room && <span className="block text-xs text-amber-800">{t("Complete identity, valid passport and price first", "أكمل الهوية والجواز الصالح والسعر أولاً")}</span>}
                                  {preference && (
                                    <span className="block text-xs text-cyan-800">
                                      {t("Purchased:", "الغرفة المحجوزة:")} {preference.room_type}
                                    </span>
                                  )}
                                  {assigned && (
                                    <span className="block text-xs text-emerald-700">
                                      {t("Already placed", "تم التوزيع")}
                                    </span>
                                  )}
                                </span>
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                  {!visibleTravelers.length && (
                    <p className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800">
                      {t("All travelers are allocated for this stay.", "تم توزيع جميع المسافرين لهذه الإقامة.")}
                    </p>
                  )}
                </div>
              </aside>
              <div className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-2">
                    {selectedStop.hotels.map((hotel) => (
                      <button
                        key={hotel.id}
                        onClick={() => setSelectedHotelId(hotel.id)}
                        className={`rounded-lg border px-3 py-2 text-sm ${hotel.id === selectedHotelId ? "border-cyan-700 bg-cyan-50" : ""}`}
                      >
                        {hotel.hotel_name}
                        {hotel.is_primary && t(" · Primary", " · رئيسي")}
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={openRoom}
                    disabled={!selectedHotel}
                    className="inline-flex items-center gap-1 rounded-lg bg-cyan-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    <Plus className="size-4" />
                    {t("Create room", "إضافة غرفة")}
                  </button>
                </div>
                {selectedHotel && (
                  <div className="mt-5 grid gap-4 lg:grid-cols-2">
                    {selectedHotel.rooms.map((room) => (
                      <RoomCard
                        key={room.id}
                        room={room}
                        selectedTravelerId={selectedTravelerId}
                        onPlace={placeTraveler}
                        onAddBed={() => addBed.mutate(room)}
                        onRemove={removeAssignment.mutate}
                        onDelete={() => deleteRoom.mutate(room.id)}
                      />
                    ))}
                    {!selectedHotel.rooms.length && (
                      <div className="col-span-full rounded-xl border-2 border-dashed p-10 text-center text-sm text-slate-500">
                        {t("No allocation rooms yet. Create the first room for", "لا توجد غرف توزيع بعد. أضف أول غرفة في")}{" "}
                        {selectedHotel.hotel_name}.
                      </div>
                    )}
                  </div>
                )}
                <MutationMessage
                  error={
                    (assign.error ||
                      addBed.error ||
                      removeAssignment.error ||
                      deleteRoom.error) as Error | null
                  }
                />
              </div>
            </div>
          )}
        </>
      )}
      <FormDialog
        open={roomOpen}
        onClose={() => setRoomOpen(false)}
        title={t("Create allocation room", "إضافة غرفة للتوزيع")}
        description={t("Create a planned room now; the physical room number can be added later.", "أضف غرفة مخططة الآن، ويمكن إدخال رقم الغرفة الفعلي لاحقًا.")}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault();
            saveRoom.mutate();
          }}
          className="space-y-4"
        >
          <label className="block text-sm font-medium">
            {t("Room type", "نوع الغرفة")}
            <select
              required
              value={roomDraft.room_type}
              onChange={(event) => {
                const type = roomTypes.data?.results.find(
                  (item) => item.id === event.target.value,
                );
                setRoomDraft({
                  ...roomDraft,
                  room_type: event.target.value,
                  standard_beds:
                    type?.default_standard_beds ?? roomDraft.standard_beds,
                });
              }}
              className="mt-1 w-full rounded-lg border px-3 py-2"
            >
              <option value="">{t("Select room type", "اختر نوع الغرفة")}</option>
              {roomTypes.data?.results
                .filter((item) => item.is_active)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
            </select>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("Planning label", "اسم الغرفة المخطط")}>
              <input
                required
                value={roomDraft.label}
                onChange={(event) =>
                  setRoomDraft({ ...roomDraft, label: event.target.value })
                }
              />
            </Field>
            <Field label={t("Actual room number", "رقم الغرفة الفعلي")}>
              <input
                value={roomDraft.actual_room_number}
                onChange={(event) =>
                  setRoomDraft({
                    ...roomDraft,
                    actual_room_number: event.target.value,
                  })
                }
              />
            </Field>
            <Field label={t("Standard beds", "الأسرة الأساسية")}>
              <input
                required
                min={1}
                type="number"
                value={roomDraft.standard_beds}
                onChange={(event) =>
                  setRoomDraft({
                    ...roomDraft,
                    standard_beds: Number(event.target.value),
                  })
                }
              />
            </Field>
            <label className="block text-sm font-medium">
              {t("Occupancy policy", "سياسة الإشغال")}
              <select
                value={roomDraft.occupancy_policy}
                onChange={(event) =>
                  setRoomDraft({
                    ...roomDraft,
                    occupancy_policy: event.target
                      .value as RoomDraft["occupancy_policy"],
                  })
                }
                className="mt-1 w-full rounded-lg border px-3 py-2"
              >
                <option value="ANY">{t("Any travelers", "جميع المسافرين")}</option>
                <option value="MALE_ONLY">{t("Male only", "ذكور فقط")}</option>
                <option value="FEMALE_ONLY">{t("Female only", "إناث فقط")}</option>
                <option value="FAMILY">{t("Family / approved mixed", "عائلة / مختلط بموافقة")}</option>
              </select>
            </label>
          </div>
          <Field label={t("Notes", "ملاحظات")}>
            <textarea
              value={roomDraft.notes}
              onChange={(event) =>
                setRoomDraft({ ...roomDraft, notes: event.target.value })
              }
            />
          </Field>
          <MutationMessage error={saveRoom.error} />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setRoomOpen(false)}
              className="rounded-lg border px-4 py-2 text-sm"
            >
              {t("Cancel", "إلغاء")}
            </button>
            <button
              disabled={saveRoom.isPending}
              className="rounded-lg bg-cyan-800 px-4 py-2 text-sm font-medium text-white"
            >
              {t("Create room", "إضافة غرفة")}
            </button>
          </div>
        </form>
      </FormDialog>
    </section>
  );
}

function RoomCard({
  room,
  selectedTravelerId,
  onPlace,
  onAddBed,
  onRemove,
  onDelete,
}: Readonly<{
  room: TripAllocationRoomRecord;
  selectedTravelerId: string;
  onPlace: (roomId: string, bed: number, traveler?: string) => void;
  onAddBed: () => void;
  onRemove: (id: string) => void;
  onDelete: () => void;
}>) {
  const t = useAllocationText();
  return (
    <article className="rounded-xl border border-slate-200">
      <header className="flex items-start justify-between border-b p-4">
        <div>
          <h4 className="font-semibold">
            {room.label}
            {room.actual_room_number && ` · ${room.actual_room_number}`}
          </h4>
          <p className="text-xs text-slate-500">
            {room.room_type_name} · {room.capacity} {t("beds", "أسرة")} ·{" "}
            {allocationLabel(room.occupancy_policy, t)}
          </p>
        </div>
        <button
          onClick={onDelete}
          disabled={room.assignments.length > 0}
          title={
            room.assignments.length
              ? t("Move travelers before deleting", "انقل المسافرين قبل حذف الغرفة")
              : t("Delete room", "حذف الغرفة")
          }
          className="text-red-600 disabled:opacity-30"
        >
          <Trash2 className="size-4" />
        </button>
      </header>
      <div className="grid gap-2 p-4 sm:grid-cols-2">
        {Array.from({ length: room.capacity }, (_, index) => index + 1).map(
          (bed) => {
            const occupant = room.assignments.find(
              (item) => item.bed_number === bed,
            );
            return (
              <div
                key={bed}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  onPlace(
                    room.id,
                    bed,
                    event.dataTransfer.getData("text/traveler"),
                  );
                }}
                onClick={() => !occupant && onPlace(room.id, bed)}
                className={`min-h-20 rounded-lg border-2 p-3 text-sm ${occupant ? "border-emerald-200 bg-emerald-50" : selectedTravelerId ? "cursor-pointer border-dashed border-cyan-400 bg-cyan-50" : "border-dashed border-slate-200"}`}
              >
                <p className="text-xs text-slate-400">
                  {bed > room.standard_beds
                    ? `${t("Extra bed", "سرير إضافي")} ${bed - room.standard_beds}`
                    : `${t("Bed", "سرير")} ${bed}`}
                </p>
                {occupant ? (
                  <div className="mt-2 flex items-start justify-between">
                    <span className="flex min-w-0 items-start gap-2">
                      <TravelerAvatar
                        name={occupant.traveler_name}
                        photoUrl={occupant.traveler_photo_url}
                        compact
                      />
                      <span className="min-w-0">
                        <b className="block">{occupant.traveler_name}</b>
                        <span className="text-xs">
                          {occupant.booking_code} · {allocationLabel(occupant.gender, t)}
                        </span>
                      </span>
                    </span>
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        onRemove(occupant.id);
                      }}
                      className="text-xs text-red-600"
                    >
                      {t("Remove", "إزالة")}
                    </button>
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">
                    {t("Drop or select a traveler", "اسحب مسافرًا هنا أو اختره ثم اضغط")}
                  </p>
                )}
              </div>
            );
          },
        )}
      </div>
      <footer className="border-t p-3">
        <button
          onClick={onAddBed}
          className="inline-flex items-center gap-1 text-sm font-medium text-cyan-800"
        >
          <Plus className="size-4" />
          {t("Add extra bed", "إضافة سرير إضافي")}
        </button>
      </footer>
    </article>
  );
}

function TravelerAvatar({
  name,
  photoUrl,
  compact = false,
}: Readonly<{ name: string; photoUrl: string | null; compact?: boolean }>) {
  const t = useAllocationText();
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
  return photoUrl ? (
    <img
      src={photoUrl}
      alt={t(`${name} profile`, `صورة ${name}`)}
      className={`${compact ? "size-9" : "size-10"} shrink-0 rounded-full object-cover ring-1 ring-slate-200`}
    />
  ) : (
    <span
      aria-label={t(`${name} initials`, `الأحرف الأولى من اسم ${name}`)}
      className={`${compact ? "size-9 text-[10px]" : "size-10 text-xs"} grid shrink-0 place-items-center rounded-full bg-cyan-100 font-semibold text-cyan-800`}
    >
      {initials || "?"}
    </span>
  );
}

function Field({
  label,
  children,
}: Readonly<{ label: string; children: React.ReactNode }>) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <div className="mt-1 [&>*]:w-full [&>*]:rounded-lg [&>*]:border [&>*]:px-3 [&>*]:py-2">
        {children}
      </div>
    </label>
  );
}
