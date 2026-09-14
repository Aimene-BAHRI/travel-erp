export type Customer = {
  id: string;
  kind: "INDIVIDUAL" | "COMPANY";
  display_name: string;
  first_name: string;
  last_name: string;
  company_name: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
  branch: string;
  branch_name: string;
  is_active: boolean;
};
