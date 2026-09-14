export type CurrentUser = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  agency_name: string | null;
  branch: string | null;
  branch_name: string | null;
  role_names: string[];
  is_active: boolean;
  is_platform_admin: boolean;
  permissions: string[];
};

