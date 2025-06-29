-- pgTAP tests for tenant row-level security
-- This test assumes the migration enabling RLS & policies is applied.

BEGIN;

SELECT plan(4);

-- Create two tenants
SELECT gen_random_uuid()
INTO TEMP TABLE t (id uuid);
INSERT INTO t
VALUES (gen_random_uuid()),
       (gen_random_uuid());

\set
tenant_a `SELECT id FROM t LIMIT 1`
\set tenant_b `SELECT id FROM t OFFSET 1 LIMIT 1`

-- Helper to set tenant_id
CREATE
OR REPLACE FUNCTION _set_tenant(uuid) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
EXECUTE format('SET app.tenant_id = %L', $1);
END;
$$;

-- Create row under tenant A
SELECT _set_tenant(:'tenant_a');
INSERT INTO meter_event (id, tenant_id, meter_name, value, timestamp)
VALUES (gen_random_uuid(), :'tenant_a', 'test_insert', 1, now());

-- Tenant A can see its own row
SELECT is (
    (SELECT count (*) FROM meter_event), 1, 'tenant A sees 1 row'
    );

-- Switch to tenant B and ensure isolation
SELECT _set_tenant(:'tenant_b');
SELECT is (
    (SELECT count (*) FROM meter_event), 0, 'tenant B sees 0 rows'
    );

SELECT finish();
ROLLBACK;
