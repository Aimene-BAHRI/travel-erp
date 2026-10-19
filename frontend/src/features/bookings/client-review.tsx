"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { useLocale } from "@/lib/i18n/context";
import { apiRequest } from "@/lib/api/client";
import { MutationMessage } from "@/components/forms/mutation-message";
import type { BookingRecord, CommercialDetails } from "./types";

export function ClientReview({ booking, onChange }: { booking: BookingRecord; onChange: (booking: BookingRecord) => void }) {
  const { locale } = useLocale(); const t = (en: string, ar: string) => locale === 'ar' ? ar : en; const router = useRouter();
  const [details, setDetails] = useState<CommercialDetails>({ source: booking.partner ? 'PARTNER' : 'WALK_IN', source_detail: '', extras: [], payment_plan: 'FULL', installments: [], notes: '', ...booking.commercial_details });
  const [approved, setApproved] = useState(false);
  const [approvedTotal, setApprovedTotal] = useState('');
  const base = booking.travelers.reduce((sum, traveler) => sum + Number(traveler.final_amount), 0);
  const extras = details.extras.reduce((sum, item) => sum + item.quantity * Number(item.unit_price || 0), 0);
  const total = (base + extras).toFixed(4);
  const offerVersion = total + booking.offer_revision;
  const edit = (value: CommercialDetails) => { setDetails(value); setApproved(false); };
  const save = useMutation({ mutationFn: (confirm: boolean) => apiRequest<BookingRecord>(`/bookings/${booking.id}/client-review/`, { method: confirm ? 'POST' : 'PATCH', body: JSON.stringify({ ...details, expected_total: total, expected_revision: booking.offer_revision }) }), onSuccess: (result, confirm) => { onChange(result); if (confirm) router.push(`/bookings/${booking.id}/invoice`); } });
  const input = 'mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm';
  return <section className="space-y-4 rounded-xl border border-cyan-200 bg-white p-5">
    <h2 className="text-lg font-semibold">{t('Final offer · review with the client', 'العرض النهائي · المراجعة مع العميل')}</h2>
    <p className="text-sm text-slate-600">{t('Room choices and traveler prices remain editable until confirmation. Review extras and payment terms here last.', 'يمكن تعديل الغرف وأسعار المسافرين حتى التأكيد. راجع الإضافات وشروط الدفع هنا في النهاية.')}</p>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="text-sm">{t('How did the client find us?', 'كيف تعرّف العميل علينا؟')}<select className={input} value={details.source} disabled={Boolean(booking.partner)} onChange={e => edit({ ...details, source: e.target.value as CommercialDetails['source'] })}>{[['WALK_IN', 'Walk-in', 'زيارة مباشرة'], ['SOCIAL_MEDIA', 'Social media', 'وسائل التواصل'], ...(booking.partner ? [['PARTNER', 'Partner agency', 'وكالة شريكة']] : []), ['REFERRER', 'Referrer', 'عن طريق معرّف'], ['OTHER', 'Other', 'أخرى']].map(([value, en, ar]) => <option key={value} value={value}>{t(en, ar)}</option>)}</select></label>
      <label className="text-sm">{t('Referrer / platform / source details', 'اسم المعرّف / المنصة / تفاصيل المصدر')}<input className={input} value={details.source_detail} onChange={e => edit({ ...details, source_detail: e.target.value })} /></label>
    </div>
    <h3 className="font-medium">{t('Extra services · prices in booking currency', 'الخدمات الإضافية · الأسعار بعملة الحجز')} ({booking.currency_code})</h3>
    {details.extras.map((item, index) => <div key={index} className="grid gap-2 rounded-lg bg-slate-50 p-3 sm:grid-cols-4">
      <label className="text-xs">{t('Service', 'الخدمة')}<select className={input} value={item.service} onChange={e => edit({ ...details, extras: details.extras.map((row, i) => i === index ? { ...row, service: e.target.value as typeof item.service } : row) })}>{[['TGV', 'TGV', 'القطار السريع'], ['SPECIAL_BUS', 'Special bus', 'حافلة خاصة'], ['FOOD', 'Food', 'الإطعام'], ['OTHER', 'Other', 'أخرى']].map(([value, en, ar]) => <option key={value} value={value}>{t(en, ar)}</option>)}</select></label>
      <label className="text-xs">{t('Description', 'التفاصيل')}<input className={input} value={item.description} onChange={e => edit({ ...details, extras: details.extras.map((row, i) => i === index ? { ...row, description: e.target.value } : row) })} /></label>
      <label className="text-xs">{t('Quantity', 'الكمية')}<input className={input} type="number" min={1} value={item.quantity} onChange={e => edit({ ...details, extras: details.extras.map((row, i) => i === index ? { ...row, quantity: Number(e.target.value) } : row) })} /></label>
      <label className="text-xs">{t('Unit price', 'سعر الوحدة')}<input className={input} type="number" min={0} step="0.0001" value={item.unit_price} onChange={e => edit({ ...details, extras: details.extras.map((row, i) => i === index ? { ...row, unit_price: e.target.value } : row) })} /></label>
      <button type="button" className="text-start text-xs text-red-700" onClick={() => edit({ ...details, extras: details.extras.filter((_, i) => i !== index) })}>{t('Remove service', 'حذف الخدمة')}</button>
    </div>)}
    <button type="button" className="text-sm font-medium text-cyan-800" onClick={() => edit({ ...details, extras: [...details.extras, { service: 'TGV', description: 'TGV', quantity: 1, unit_price: '' }] })}>{t('+ Add service', '+ إضافة خدمة')}</button>
    <label className="block text-sm">{t('Payment agreement', 'اتفاق الدفع')}<select className={input} value={details.payment_plan} onChange={e => edit({ ...details, payment_plan: e.target.value as CommercialDetails['payment_plan'] })}><option value="FULL">{t('Full payment', 'الدفع الكامل')}</option><option value="INSTALLMENTS">{t('Installments', 'الدفع بالتقسيط')}</option></select></label>
    {details.payment_plan === 'INSTALLMENTS' && <div className="space-y-2">{details.installments.map((item, index) => <div key={index} className="flex gap-2"><label className="text-xs">{t('Due date', 'تاريخ الاستحقاق')}<input className={input} type="date" value={item.due_date} onChange={e => edit({ ...details, installments: details.installments.map((row, i) => i === index ? { ...row, due_date: e.target.value } : row) })} /></label><label className="text-xs">{t('Amount', 'المبلغ')}<input className={input} type="number" min="0.0001" step="0.0001" value={item.amount} onChange={e => edit({ ...details, installments: details.installments.map((row, i) => i === index ? { ...row, amount: e.target.value } : row) })} /></label><button type="button" onClick={() => edit({ ...details, installments: details.installments.filter((_, i) => i !== index) })}>{t('Remove', 'حذف')}</button></div>)}<button type="button" className="text-sm text-cyan-800" onClick={() => edit({ ...details, installments: [...details.installments, { due_date: '', amount: '' }] })}>{t('+ Add installment', '+ إضافة قسط')}</button><p className="text-xs text-slate-600">{t('Scheduled amounts must equal the final total. This does not record a payment.', 'يجب أن يساوي مجموع الأقساط الإجمالي النهائي. هذا لا يسجل دفعة مالية.')}</p></div>}
    <label className="block text-sm">{t('Agreed notes', 'الملاحظات المتفق عليها')}<textarea className={input} value={details.notes} onChange={e => edit({ ...details, notes: e.target.value })} /></label>
    <div className="rounded-lg bg-cyan-50 p-4"><p>{t('Traveler packages', 'باقات المسافرين')}: {base.toFixed(2)}</p><p>{t('Extra services', 'الخدمات الإضافية')}: {extras.toFixed(2)}</p><p className="text-xl font-bold">{t('Final offer', 'العرض النهائي')}: {Number(total).toFixed(2)} {booking.currency_code}</p></div>
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={approved && approvedTotal === offerVersion} onChange={e => { setApproved(e.target.checked); setApprovedTotal(offerVersion); }} />{t('The client agrees to the rooms, services, final price and payment schedule.', 'وافق العميل على الغرف والخدمات والسعر النهائي وجدول الدفع.')}</label>
    <MutationMessage error={save.error} />
    {!booking.readiness.is_ready && <p className="text-sm text-amber-800">{t('Complete every traveler, valid passport, price and required room before confirmation.', 'أكمل جميع المسافرين والجوازات الصالحة والأسعار والغرف المطلوبة قبل التأكيد.')}</p>}
    <div className="flex flex-wrap gap-2"><button type="button" disabled={save.isPending} onClick={() => save.mutate(false)} className="rounded-lg border px-4 py-2">{t('Save offer as draft', 'حفظ العرض كمسودة')}</button><button type="button" disabled={save.isPending || !approved || approvedTotal !== offerVersion || !booking.readiness.is_ready} onClick={() => save.mutate(true)} className="rounded-lg bg-cyan-800 px-4 py-2 text-white disabled:opacity-40">{t('Client confirms · open invoice', 'تأكيد العميل · فتح الفاتورة')}</button></div>
  </section>;
}
