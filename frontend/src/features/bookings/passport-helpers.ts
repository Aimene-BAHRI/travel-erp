export type PassportPhoto = { file: File; source: "PASSPORT_AUTO_CROP" | "PASSPORT_MANUAL_CROP" };
export async function encodePassportScan(file: File | null) {
  if (!file) return undefined;
  if (file.size > 10 * 1024 * 1024) throw new Error("Full passport image must be 10 MB or smaller.");
  const data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = () => reject(new Error("Could not read the full passport image."));
    reader.readAsDataURL(file);
  });
  return { data };
}
export async function encodePassportPhoto(photo: PassportPhoto | null) {
  if (!photo) return undefined;
  const data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = () => reject(new Error("Could not read the cropped photo."));
    reader.readAsDataURL(photo.file);
  });
  return { data, source: photo.source };
}

export function suggestedIssueDate(expiry: string, years: number) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(expiry)) return "";
  const [year, month, day] = expiry.split("-").map(Number);
  const target = year - years;
  const lastDay = new Date(Date.UTC(target, month, 0)).getUTCDate();
  return `${target}-${String(month).padStart(2, "0")}-${String(Math.min(day, lastDay)).padStart(2, "0")}`;
}

export function passportYears(birth: string, today = new Date()) {
  if (!birth) return 10;
  const [year, month, day] = birth.split("-").map(Number);
  const age = today.getFullYear() - year - (today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day) ? 1 : 0);
  return age >= 18 ? 10 : 5;
}
