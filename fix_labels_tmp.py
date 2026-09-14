from pathlib import Path
import re
labels = {
"Scan fills the fields; review them before saving. A valid passport is required for rooms and payments.": "راجع البيانات المستخرجة قبل الحفظ. يلزم جواز صالح لتخصيص الغرف وتسجيل الدفعات.",
"Save names only ? complete details later": "حفظ الأسماء فقط وإكمال البيانات لاحقاً",
"Additional charge ? increases total": "مبلغ إضافي يزيد الإجمالي",
"Allocates an unassigned part of the existing total; cannot exceed that total. Draft prices build the draft total.": "يخصص جزءاً من الإجمالي الحالي دون تجاوزه. أسعار المسودة تُضاف إلى إجماليها.",
"Adds this amount to the booking total. The change is recorded in the audit history; no payment is taken.": "يُضاف المبلغ إلى إجمالي الحجز ويُسجل التغيير في سجل التدقيق دون تسجيل دفعة.",
"Loading rooms?": "جارٍ تحميل الغرف…",
"Room availability and traveler details are rechecked when you validate. If a room is taken, nothing is partially saved.": "يُعاد التحقق من توفر الغرف والبيانات عند التأكيد. إذا لم تتوفر الغرفة فلن تُحفظ العملية جزئياً.",
"Validate saves the traveler, passport, price and rooms together. No payment is recorded.": "التأكيد يحفظ المسافر والجواز والسعر والغرف معاً دون تسجيل دفعة.",
}
p=Path('frontend/src/features/bookings/booking-traveler-flow.tsx')
s=p.read_text(encoding='utf-8')
s=re.sub(r't\("([^"\n]*)", "([^"\n]*)"\)',lambda m:'t("'+m[1]+'", "'+labels[m[1]]+'")' if m[1] in labels else m[0],s)
s=s.replace('`?????? ??? ?????? (${issues.length}) ? ?????? ?? ?????? ?? ????? ?? ?????`','`بيانات ناقصة (${issues.length}) — أكمل البيانات قبل تخصيص الغرف والدفع`').replace('issues.join(" ? ")','issues.join(" · ")')
p.write_text(s,encoding='utf-8')
p=Path('frontend/src/features/trips/trip-readiness-panel.tsx'); s=p.read_text(encoding='utf-8').replace('????? Excel ? ????????? ?????????','تصدير Excel للمسافرين الفعليين').replace('Export Excel ? real travelers','Export Excel · real travelers'); p.write_text(s,encoding='utf-8')
p=Path('frontend/src/features/notifications/notification-appearance.tsx'); s=p.read_text(encoding='utf-8').replace('ar: "????"','ar: "جاهز"'); p.write_text(s,encoding='utf-8')
