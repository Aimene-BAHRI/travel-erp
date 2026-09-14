export const arStatus: Record<string, string> = {
  DRAFT: "مسودة",
  ISSUED: "صادر",
  ACCEPTED: "مقبول",
  EXPIRED: "منتهي",
  CANCELLED: "ملغى",
  OPEN: "مفتوحة",
  PLANNING: "قيد التحضير",
  CLOSED: "مغلقة",
  DEPARTED: "انطلقت",
  COMPLETED: "مكتملة",
  CONFIRMED: "مؤكدة",
  PENDING: "قيد الانتظار",
  PENDING_CLOSING: "بانتظار الإغلاق",
  NEW: "جديد",
  CONTACTED: "تم التواصل",
  QUALIFIED: "مؤهل",
  REQUESTED: "مطلوب",
  CONVERTED: "محول",
  REJECTED: "مرفوض",
};

export function statusAr(value?: string | null) {
  if (!value) return "غير محدد";
  return arStatus[value] ?? value.replaceAll("_", " ");
}
