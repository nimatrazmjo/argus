-- deploy/tenancy/tenant-policies.sql
-- Multi-tenancy Row-Level Security (RLS) policies and query resource quotas

-- 1. Create Tenant Users
CREATE USER IF NOT EXISTS tenant_alpha IDENTIFIED WITH plaintext_password BY 'alpha123';
CREATE USER IF NOT EXISTS tenant_beta IDENTIFIED WITH plaintext_password BY 'beta123';
CREATE USER IF NOT EXISTS tenant_quota_test IDENTIFIED WITH plaintext_password BY 'quota123';

-- 2. Grant Read Privileges
GRANT SELECT ON default.* TO tenant_alpha;
GRANT SELECT ON default.* TO tenant_beta;
GRANT SELECT ON default.* TO tenant_quota_test;
GRANT SELECT ON signoz_traces.* TO tenant_alpha, tenant_beta;
GRANT SELECT ON signoz_logs.* TO tenant_alpha, tenant_beta;
GRANT SELECT ON signoz_metrics.* TO tenant_alpha, tenant_beta;

-- 3. Row Policies for default.otel_traces
CREATE ROW POLICY IF NOT EXISTS tenant_isolation_traces ON default.otel_traces
    FOR SELECT USING (
        currentUser() = 'default'
        OR ResourceAttributes['tenant_id'] = currentUser()
    ) TO tenant_alpha, tenant_beta;

-- 4. Row Policies for default.otel_logs
CREATE ROW POLICY IF NOT EXISTS tenant_isolation_logs ON default.otel_logs
    FOR SELECT USING (
        currentUser() = 'default'
        OR ResourceAttributes['tenant_id'] = currentUser()
    ) TO tenant_alpha, tenant_beta;

-- 5. Row Policies for default.otel_metrics_gauge
CREATE ROW POLICY IF NOT EXISTS tenant_isolation_metrics ON default.otel_metrics_gauge
    FOR SELECT USING (
        currentUser() = 'default'
        OR ResourceAttributes['tenant_id'] = currentUser()
    ) TO tenant_alpha, tenant_beta;

-- 6. Production Per-Tenant Resource Quota (Noisy-Neighbor Protection)
CREATE QUOTA IF NOT EXISTS tenant_quota
    KEYED BY user_name
    FOR INTERVAL 1 HOUR
        MAX EXECUTION TIME = 30,
        MAX READ ROWS = 10000000,
        MAX READ BYTES = 10737418240
    TO tenant_alpha, tenant_beta;

-- 7. Strict Test Quota for Edge-Case Verification
CREATE QUOTA IF NOT EXISTS strict_test_quota
    KEYED BY user_name
    FOR INTERVAL 1 HOUR
        MAX READ ROWS = 10
    TO tenant_quota_test;
