export type PassportSummary = {
  passport_image_url: string | null;
  id: string;
  passport_number: string;
  full_name: string;
  status: "CURRENT" | "EXPIRED" | "REPLACED";
  birth_date: string;
  expiry_date: string;
  nationality_code: string;
  gender: "F" | "M" | "X";
};

export type Traveler = {
  id: string;
  display_name: string;
  first_name: string;
  last_name: string;
  birth_date: string | null;
  gender: "F" | "M" | "X";
  phone: string;
  email: string;
  address: string;
  notes: string;
  branch_name: string;
  branch: string;
  created_at: string;
  updated_at: string;
  current_photo: string | null;
  current_photo_url: string | null;
  current_photo_source:
    "PASSPORT_AUTO_CROP" | "PASSPORT_MANUAL_CROP" | "MANUAL_UPLOAD" | "";
  current_passport: PassportSummary | null;
  is_active: boolean;
};

export type DocumentRecord = {
  id: string;
  category: string;
  title: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  download_url: string;
  created_at: string;
};

export type PassportDetail = {
  id: string;
  passport_number: string;
  first_name: string;
  middle_name: string;
  last_name: string;
  status: "CURRENT" | "EXPIRED" | "REPLACED";
  birth_date: string;
  birth_place: string;
  birth_country: string | null;
  nationality: string;
  gender: "F" | "M" | "X";
  issue_date: string;
  expiry_date: string;
  issuing_country: string;
  issue_place: string;
  mrz: string;
  passport_image: string | null;
};
