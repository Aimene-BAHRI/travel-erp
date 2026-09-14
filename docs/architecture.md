# Architecture

Travel ERP is a modular monolith with a Django REST API, a Next.js frontend, and PostgreSQL as
the system of record. Business modules remain independently understandable while sharing one
deployment and one transactional database.

## Architectural boundaries

1. API views translate HTTP requests and responses.
2. Application services coordinate business use cases and transactions.
3. Domain models enforce durable invariants.
4. Selectors encapsulate reusable read queries.
5. Permission policies enforce agency and branch scope on the backend.

## Dependency direction

Reference data and organizations are foundational. Transactional domains may depend on them,
but foundational domains must not import transactional domains. Cross-domain writes are
coordinated through explicit application services.

## Tenancy

Every agency-owned record must carry an agency relationship directly or have an unambiguous,
enforced ownership path. Tenant filtering and object authorization are mandatory, and
cross-agency rejection will be covered by integration tests.

Platform administrators are agency-neutral and are not ordinary ERP users. Tenant APIs derive
agency scope from authenticated agency users and do not expose cross-agency platform operations.
