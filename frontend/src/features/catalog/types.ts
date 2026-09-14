export type HotelRecord = {
  id: string;
  name: string;
  city: string;
  city_name: string;
  country_code: string;
  star_rating: number | null;
  address: string;
  phone: string;
  email: string;
  website: string;
  check_in_time: string | null;
  check_out_time: string | null;
  notes: string;
  room_count: number;
  is_active: boolean;
};

export type RoomRecord = {
  id: string;
  hotel: string;
  room_type: string;
  number: string;
  floor: string;
  room_type_name: string;
  standard_beds: number;
  max_extra_beds: number;
  maximum_beds: number;
  notes: string;
  is_active: boolean;
};

export type RoomTypeRecord = {
  id: string;
  code: string;
  name: string;
  default_standard_beds: number;
  description: string;
  sort_order: number;
  is_active: boolean;
};

export type SupplierRecord = {
  id: string;
  name: string;
  legal_name: string;
  registration_number: string;
  tax_number: string;
  contact_name: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
  is_active: boolean;
};

export type AirlineRecord = {
  id: string;
  name: string;
  iata_code: string | null;
  icao_code: string | null;
  country_code: string | null;
};
