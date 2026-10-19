"use client";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n/context";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { RoomTypeRecord } from "@/features/catalog/types";
import type { Paginated } from "@/features/reference/types";
import type { AccommodationPlan, TripAllocationRoomRecord } from "@/features/trips/types";

export function InlineRoomCreator({ stop, onCreated }: { stop: AccommodationPlan['stops'][number]; onCreated: (room: TripAllocationRoomRecord) => void }) {
  const { locale } = useLocale(); const t = (en: string, ar: string) => locale === 'ar' ? ar : en;
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ trip_hotel: stop.hotels[0]?.id ?? '', room_type: '', label: '', standard_beds: 2, extra_beds: 0, occupancy_policy: 'ANY' });
  const types = useQuery({ queryKey: ['booking-room-types'], enabled: open, queryFn: async () => {
    const first = await apiRequest<Paginated<RoomTypeRecord>>('/catalog/room-types/'); const results = [...first.results]; let next = first.next;
    while (next) { const page = await apiRequest<Paginated<RoomTypeRecord>>(`/catalog/room-types/${new URL(next, 'http://localhost').search}`); results.push(...page.results); next = page.next; }
    return results.filter(item => item.is_active);
  }});
  const create = useMutation({ mutationFn: () => apiRequest<TripAllocationRoomRecord>('/trips/allocation-rooms/', { method: 'POST', body: JSON.stringify(draft) }), onSuccess: room => { onCreated(room); setOpen(false); setDraft({ ...draft, label: '' }); } });
  return <div className="my-2 rounded-lg border p-3 text-sm">
    <button type="button" onClick={() => setOpen(!open)} className="font-medium text-cyan-800">{open ? t('Cancel new room', 'إلغاء الغرفة الجديدة') : t('+ Create room here', '+ إنشاء غرفة هنا')}</button>
    {open && <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <label>{t('Hotel', 'الفندق')}<select className="w-full rounded border p-2" value={draft.trip_hotel} onChange={e => setDraft({ ...draft, trip_hotel: e.target.value })}>{stop.hotels.map(hotel => <option key={hotel.id} value={hotel.id}>{hotel.hotel_name}</option>)}</select></label>
      <label>{t('Room type', 'نوع الغرفة')}<select className="w-full rounded border p-2" value={draft.room_type} onChange={e => { const type = types.data?.find(item => item.id === e.target.value); setDraft({ ...draft, room_type: e.target.value, standard_beds: type?.default_standard_beds ?? 2 }); }}><option value="">{t('Select', 'اختر')}</option>{types.data?.map(type => <option key={type.id} value={type.id}>{type.name}</option>)}</select></label>
      <label>{t('Room label', 'تسمية الغرفة')}<input className="w-full rounded border p-2" value={draft.label} onChange={e => setDraft({ ...draft, label: e.target.value })} /></label>
      <label>{t('Beds', 'عدد الأسرّة')}<input type="number" min={1} max={50} className="w-full rounded border p-2" value={draft.standard_beds} onChange={e => setDraft({ ...draft, standard_beds: Number(e.target.value) })} /></label>
      <label>{t('Occupancy', 'الإشغال')}<select className="w-full rounded border p-2" value={draft.occupancy_policy} onChange={e => setDraft({ ...draft, occupancy_policy: e.target.value })}>{[['ANY', 'Any', 'عام'], ['MALE_ONLY', 'Men', 'رجال'], ['FEMALE_ONLY', 'Women', 'نساء'], ['FAMILY', 'Family', 'عائلة']].map(([value, en, ar]) => <option key={value} value={value}>{t(en, ar)}</option>)}</select></label>
      <p className="text-xs text-slate-500 sm:col-span-2">{t('Add only a room your agency has arranged with the hotel. This records inventory; it does not reserve a room with the hotel.', 'أضف غرفة متفقاً عليها مع الفندق. هذا يسجلها في النظام ولا يحجزها لدى الفندق تلقائياً.')}</p>
      <button type="button" disabled={create.isPending || !draft.label.trim() || !draft.trip_hotel || !draft.room_type || draft.standard_beds < 1} onClick={() => create.mutate()} className="rounded bg-cyan-800 p-2 text-white disabled:opacity-50">{t('Create and select', 'إنشاء واختيار')}</button>
      <MutationMessage error={create.error || types.error} />
    </div>}
  </div>;
}
