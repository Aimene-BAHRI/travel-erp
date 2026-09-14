# Permissions

Authentication, role definitions, and branch scope will be implemented in Phase 1.

The non-negotiable authorization rules are:

- An authenticated business user belongs to exactly one agency.
- Agency scope is derived on the backend and cannot be selected by the client.
- A branch user is scoped to their branch unless an explicit permission grants broader access.
- Agency-level users may access multiple branches only through explicit permissions.
- Cross-agency relationships and access are rejected and tested.

Agency roles are configurable collections of Django permissions. Protected system roles may be
introduced through data migrations when shared defaults are needed. Agency roles cannot change a
user's tenant; tenant scope is always evaluated separately from capability permissions.

Customers, travelers, passports, and documents are filtered by the authenticated user's agency.
Branch users default to their own branch unless granted the corresponding `view_all_*` capability.
Possessing a model permission never bypasses agency isolation.
