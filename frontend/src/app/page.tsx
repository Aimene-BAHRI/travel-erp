import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { PublicHome } from "@/features/public/public-home";

export default async function HomePage() {
  const cookieStore = await cookies();
  if (cookieStore.has("travel_erp_access") || cookieStore.has("travel_erp_refresh"))
    redirect("/dashboard");
  return <PublicHome />;
}
