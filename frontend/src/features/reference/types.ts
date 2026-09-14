export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type Country = { id: string; name: string; code: string };

export type AgencyCurrency = {
  id: string;
  currency: string;
  currency_name: string;
  currency_symbol: string;
  is_enabled: boolean;
  is_accounting: boolean;
};

export type PassengerCategory = {
  id: string;
  code: string;
  name: string;
  requires_bed_by_default: boolean;
  is_system: boolean;
  is_active: boolean;
};

export type PaymentMethod = {
  id: string;
  code: string;
  name: string;
  is_system: boolean;
  is_active: boolean;
};
