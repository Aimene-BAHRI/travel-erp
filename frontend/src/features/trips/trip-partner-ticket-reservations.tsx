"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Handshake } from "lucide-react";
import { useState } from "react";

import { MutationMessage } from "@/components/forms/mutation-message";
import type { AllocationRecord } from "@/features/partners/types";
import type { Customer } from "@/features/customers/types";
import type { Paginated } from "@/features/reference/types";
import { apiRequest } from "@/lib/api/client";

export function TripPartnerTicketReservations({
  tripId,
}: Readonly<{ tripId: string }>) {
  const cache = useQueryClient();
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [customerId, setCustomerId] = useState("");
  const [quantity, setQuantity] = useState(30);
  const customers = useQuery({
    queryKey: ["company-customers", tripId],
    queryFn: () => apiRequest<Paginated<Customer>>("/customers/?ordering=company_name"),
  });
  const allocations = useQuery({
    queryKey: ["trip-allocations", tripId],
    queryFn: () =>
      apiRequest<Paginated<AllocationRecord>>(
        `/partners/allocations/?trip=${tripId}`,
      ),
  });
  const reserve = useMutation({
    mutationFn: ({ id, quantity }: { id: string; quantity: number }) =>
      apiRequest(`/partners/allocations/${id}/reserve-tickets/`, {
        method: "POST",
        body: JSON.stringify({ quantity }),
      }),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["trip-allocations", tripId] });
      cache.invalidateQueries({ queryKey: ["trip", tripId] });
      cache.invalidateQueries({ queryKey: ["trips"] });
    },
  });
  const reserveCustomer = useMutation({
    mutationFn: () =>
      apiRequest("/partners/allocations/reserve-company-customer-tickets/", {
        method: "POST",
        body: JSON.stringify({ trip: tripId, customer: customerId, quantity }),
      }),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["trip-allocations", tripId] });
      cache.invalidateQueries({ queryKey: ["trip", tripId] });
      cache.invalidateQueries({ queryKey: ["trips"] });
    },
  });
  const ticketAllocations = allocations.data?.results.filter(
    (allocation) => allocation.kind === "TICKETS",
  ) ?? [];

  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <header className="flex items-center gap-2 border-b p-5">
        <Handshake className="size-5 text-cyan-800" />
        <div>
          <h2 className="font-semibold">Partner ticket places</h2>
          <p className="text-sm text-slate-500">
            Reserve places from a partner’s ticket allocation without adding traveler or passport details.
          </p>
        </div>
      </header>
      <MutationMessage error={reserve.error || reserveCustomer.error || allocations.error || customers.error} />
      <div className="grid gap-3 p-5 sm:grid-cols-[1fr_8rem_auto]">
        <label className="text-sm font-medium">
          Company customer
          <select value={customerId} onChange={(event) => setCustomerId(event.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2">
            <option value="">Select a company customer</option>
            {customers.data?.results.filter((item) => item.is_active && item.kind === "COMPANY").map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">
          Ticket places
          <input type="number" min="1" value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} className="mt-1 w-full rounded-lg border px-3 py-2" />
        </label>
        <button type="button" disabled={!customerId || quantity < 1 || reserveCustomer.isPending} onClick={() => reserveCustomer.mutate()} className="self-end rounded-lg bg-cyan-800 px-4 py-2 text-sm text-white disabled:opacity-50">
          Reserve places
        </button>
      </div>
      {allocations.isPending || customers.isPending ? (
        <p className="p-5 text-sm text-slate-500">Loading partner allocations…</p>
      ) : ticketAllocations.length === 0 ? (
        <p className="p-5 text-sm text-slate-500">
          No ticket places have been reserved for this trip yet.
        </p>
      ) : (
        <div className="divide-y">
          {ticketAllocations.map((allocation) => (
            <div
              key={allocation.id}
              className="flex flex-wrap items-center justify-between gap-3 p-5"
            >
              <div>
                <p className="font-medium">{allocation.partner_name}</p>
                <p className="text-sm text-slate-500">
                  {allocation.reserved_quantity} reserved · {allocation.used_quantity} used · {allocation.remaining_quantity} remaining of {allocation.quantity}
                </p>
              </div>
              {allocation.is_active && allocation.remaining_quantity > 0 && (
                <div className="flex items-center gap-2">
                  <input
                    aria-label={`Ticket places to reserve for ${allocation.partner_name}`}
                    type="number"
                    min="1"
                    max={allocation.remaining_quantity}
                    value={quantities[allocation.id] ?? allocation.remaining_quantity}
                    onChange={(event) =>
                      setQuantities((current) => ({
                        ...current,
                        [allocation.id]: Number(event.target.value),
                      }))
                    }
                    className="w-24 rounded-lg border px-3 py-2"
                  />
                  <button
                    type="button"
                    disabled={
                      reserve.isPending ||
                      (quantities[allocation.id] ?? allocation.remaining_quantity) < 1 ||
                      (quantities[allocation.id] ?? allocation.remaining_quantity) > allocation.remaining_quantity
                    }
                    onClick={() =>
                      reserve.mutate({
                        id: allocation.id,
                        quantity: quantities[allocation.id] ?? allocation.remaining_quantity,
                      })
                    }
                    className="rounded-lg bg-cyan-800 px-3 py-2 text-sm text-white disabled:opacity-50"
                  >
                    Reserve places
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
