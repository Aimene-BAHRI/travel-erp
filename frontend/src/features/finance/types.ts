export interface FinancialTransactionRecord {
  id: string;
  booking: string;
  booking_code: string;
  number: string;
  kind: "PAYMENT" | "REFUND" | "REVERSAL";
  amount: string;
  currency_code: string;
  booking_exchange_rate: string;
  booking_amount: string;
  signed_booking_amount: string;
  booking_currency_code: string;
  payment_method_name: string;
  transaction_date: string;
  created_at: string;
  reference: string;
  notes: string;
  allocations: Array<{
    id: string;
    booking_traveler: string;
    traveler_name: string;
    amount: string;
  }>;
}

export interface FinancialSummary {
  booking_total: string;
  paid_amount: string;
  remaining_amount: string;
  currency: string;
  accounting_total: string;
  accounting_paid_amount: string;
  accounting_remaining_amount: string;
  accounting_currency: string;
  traveler_balances: Array<{
    booking_traveler: string;
    traveler_name: string;
    total_amount: string;
    paid_amount: string;
    remaining_amount: string;
  }>;
}

export interface PaymentReceipt {
  receipt_number: string;
  agency_name: string;
  agency_logo: string | null;
  branch_name: string;
  booking_code: string;
  customer_name: string;
  customer_phone: string;
  trip_name: string;
  amount_in_words_ar: string;
  hotels: string[];
  room_types: string[];
  financial_summary: FinancialSummary;
  transaction: FinancialTransactionRecord;
}

export interface ExchangeRateRecord {
  id: string;
  source_currency: string;
  target_currency: string;
  rate: string;
  effective_date: string;
  source_reference: string;
  notes: string;
  created_at: string;
}

export interface ExpensePaymentRecord {
  id: string;
  number: string;
  kind: "PAYMENT" | "REVERSAL";
  signed_expense_amount: string;
  currency_code: string;
  payment_method_name: string;
  payment_date: string;
}

export interface TripExpenseRecord {
  id: string;
  trip: string;
  supplier: string | null;
  supplier_name: string | null;
  category: "HOTEL" | "FLIGHT" | "TRANSPORT" | "VISA" | "GUIDE" | "OTHER";
  description: string;
  amount: string;
  currency: string;
  currency_code: string;
  paid_amount: string;
  remaining_amount: string;
  due_date: string | null;
  status: "PLANNED" | "APPROVED" | "CANCELLED";
  notes: string;
  payments: ExpensePaymentRecord[];
}

export type CashEntryCategory =
  | "OTHER_INCOME"
  | "OWNER_FUNDS"
  | "OPERATING_COST"
  | "TAX"
  | "SALARY"
  | "TRANSFER"
  | "TRIP_ADVANCE"
  | "OTHER_EXPENSE";

export interface CashEntry {
  id: string;
  number: string;
  direction: "IN" | "OUT";
  category: CashEntryCategory;
  description: string;
  amount: string | number;
  currency: string;
  entry_date: string;
  reference: string;
  notes: string;
}

export interface CashFlowReport {
  trip: string | null;
  totals_by_currency: Record<string, { inflow: string | number; outflow: string | number; net: string | number }>;
  entries: Array<{
    number: string;
    date: string;
    kind: string;
    description: string;
    recipient_name: string;
    source_amount: string | number | null;
    source_currency: string | null;
    exchange_rate: string | number | null;
    currency: string;
    amount: string | number;
  }>;
}
