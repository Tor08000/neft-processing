BEGIN;

-- =========================================================
-- 1) PLANS (version 1) — upsert (idempotent)
-- =========================================================
INSERT INTO subscription_plans (code, version, title, description, is_active)
VALUES
  ('FREE',       1, 'FREE / BASIC',   'Вход и ознакомление', TRUE),
  ('CONTROL',    1, 'CONTROL',        'Операционный контроль', TRUE),
  ('INTEGRATE',  1, 'INTEGRATE',      'Интеграция и масштаб', TRUE),
  ('ENTERPRISE', 1, 'ENTERPRISE',     'Ответственность и гарантии (по договору)', TRUE)
ON CONFLICT (code, version) DO UPDATE
SET title = EXCLUDED.title,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active;

-- =========================================================
-- 2) ADD-ONS catalog — upsert
-- (платные интеграции/возможности; gating будет через feature_key=ADDON_ELIGIBLE)
-- =========================================================
INSERT INTO addons (code, title, description, billing_type, default_price, currency, is_active)
VALUES
  ('integration.helpdesk.zendesk', 'Helpdesk: Zendesk', 'Outbound+Inbound sync для Zendesk', 'RECURRING', 15000.00, 'RUB', TRUE),
  ('integration.erp.accounting',   'ERP/Accounting интеграция', 'Интеграции 1C/SAP/Oracle (контрактно)', 'RECURRING', 50000.00, 'RUB', TRUE),
  ('integration.api.webhooks',     'API/Webhooks расширенные', 'Расширенные webhooks/API квоты/эндпоинты', 'RECURRING', 20000.00, 'RUB', TRUE),
  ('feature.export.priority',      'Priority/Streaming exports', 'Приоритетные экспорты/стриминг', 'RECURRING', 10000.00, 'RUB', TRUE)
ON CONFLICT (code) DO UPDATE
SET title = EXCLUDED.title,
    description = EXCLUDED.description,
    billing_type = EXCLUDED.billing_type,
    default_price = EXCLUDED.default_price,
    currency = EXCLUDED.currency,
    is_active = EXCLUDED.is_active;

-- =========================================================
-- 3) SUPPORT PLANS — upsert
-- =========================================================
INSERT INTO support_plans (code, sla_targets, included_channels, escalation_enabled)
VALUES
  ('STANDARD', '{"first_response_minutes": null, "resolution_minutes": null}', ARRAY['portal'], FALSE),
  ('PRIORITY', '{"first_response_minutes": 120, "resolution_minutes": 1440}', ARRAY['portal','email'], TRUE),
  ('DEDICATED','{"first_response_minutes": 60,  "resolution_minutes": 480}',  ARRAY['portal','email','phone'], TRUE)
ON CONFLICT (code) DO UPDATE
SET sla_targets = EXCLUDED.sla_targets,
    included_channels = EXCLUDED.included_channels,
    escalation_enabled = EXCLUDED.escalation_enabled;

-- =========================================================
-- 4) SLO TIERS — upsert
-- A/B/C tiers для Enterprise
-- =========================================================
INSERT INTO slo_tiers (code, included_slos_json, penalties_json)
VALUES
  ('A_MONITORING',
   '{"exports":"monitoring","email":"monitoring","support":"monitoring","schedules":"monitoring"}',
   NULL),
  ('B_COMMITTED',
   '{"exports":"committed","email":"committed","support":"committed","schedules":"committed"}',
   '{"credits":"manual"}'),
  ('C_GUARANTEED',
   '{"exports":"guaranteed","email":"guaranteed","support":"guaranteed","schedules":"guaranteed"}',
   '{"credits":"contractual"}')
ON CONFLICT (code) DO UPDATE
SET included_slos_json = EXCLUDED.included_slos_json,
    penalties_json = EXCLUDED.penalties_json;

-- =========================================================
-- 5) PLAN FEATURES (Feature gates) — upsert per plan
-- availability: ENABLED / DISABLED / LIMITED / ADDON_ELIGIBLE
-- =========================================================

-- helper: clean old feature rows for v1 re-seed (optional, leave commented if you prefer purely upsert)
-- DELETE FROM subscription_plan_features WHERE plan_id IN (SELECT id FROM subscription_plans WHERE version=1);

-- ---------- FREE ----------
INSERT INTO subscription_plan_features (plan_id, feature_key, availability, limits_json)
SELECT p.id, v.feature_key, v.availability, v.limits_json::jsonb
FROM subscription_plans p
JOIN (VALUES
  ('feature.portal.core',                'ENABLED', NULL),
  ('feature.portal.entities',            'ENABLED', NULL),
  ('feature.export.async_csv',           'ENABLED', NULL),
  ('feature.notifications.in_app',       'ENABLED', NULL),
  ('feature.access.rbac_abac',           'ENABLED', NULL),
  ('feature.audit.basic',                'ENABLED', NULL),

  ('feature.analytics.summary',          'ENABLED', NULL),
  ('feature.analytics.drilldown',        'DISABLED', NULL),
  ('feature.analytics.advanced',         'DISABLED', NULL),

  ('feature.reports.csv',                'DISABLED', NULL),
  ('feature.reports.xlsx',               'DISABLED', NULL),
  ('feature.reports.retention',          'DISABLED', NULL),

  ('feature.export.async',               'ENABLED', NULL),
  ('feature.export.progress',            'DISABLED', NULL),
  ('feature.export.eta',                 'DISABLED', NULL),
  ('feature.export.large_100k',          'DISABLED', NULL),
  ('feature.export.streaming_priority',  'DISABLED', NULL),

  ('feature.dashboards.user',            'DISABLED', NULL),
  ('feature.dashboards.health',          'DISABLED', NULL),
  ('feature.dashboards.custom',          'DISABLED', NULL),

  -- integrations (paid)
  ('integration.helpdesk.outbound',      'DISABLED', NULL),
  ('integration.helpdesk.inbound',       'DISABLED', NULL),
  ('integration.erp.accounting',         'DISABLED', NULL),
  ('integration.api.webhooks',           'DISABLED', NULL),

  ('support.internal',                   'ENABLED', NULL),
  ('support.email_notifications',        'LIMITED', '{"email_events":"critical_only"}'),
  ('slo.monitoring.readonly',            'DISABLED', NULL),
  ('slo.tiers',                          'DISABLED', NULL),
  ('sla.contractual',                    'DISABLED', NULL),
  ('support.priority',                   'DISABLED', NULL),
  ('support.incident_escalation',        'DISABLED', NULL)
) AS v(feature_key, availability, limits_json)
ON TRUE
WHERE p.code='FREE' AND p.version=1
ON CONFLICT (plan_id, feature_key) DO UPDATE
SET availability = EXCLUDED.availability,
    limits_json = EXCLUDED.limits_json;

-- ---------- CONTROL ----------
INSERT INTO subscription_plan_features (plan_id, feature_key, availability, limits_json)
SELECT p.id, v.feature_key, v.availability, v.limits_json::jsonb
FROM subscription_plans p
JOIN (VALUES
  ('feature.portal.core',                'ENABLED', NULL),
  ('feature.portal.entities',            'ENABLED', NULL),
  ('feature.export.async_csv',           'ENABLED', NULL),
  ('feature.notifications.in_app',       'ENABLED', NULL),
  ('feature.access.rbac_abac',           'ENABLED', NULL),
  ('feature.audit.basic',                'ENABLED', NULL),

  ('feature.analytics.summary',          'ENABLED', NULL),
  ('feature.analytics.drilldown',        'ENABLED', NULL),
  ('feature.analytics.advanced',         'DISABLED', NULL),

  ('feature.reports.csv',                'ENABLED', NULL),
  ('feature.reports.xlsx',               'DISABLED', NULL),
  ('feature.reports.retention',          'DISABLED', NULL),

  ('feature.export.async',               'ENABLED', NULL),
  ('feature.export.progress',            'ENABLED', NULL),
  ('feature.export.eta',                 'ENABLED', NULL),
  ('feature.export.large_100k',          'DISABLED', NULL),
  ('feature.export.streaming_priority',  'DISABLED', NULL),

  ('feature.dashboards.user',            'ENABLED', NULL),
  ('feature.dashboards.health',          'DISABLED', NULL),
  ('feature.dashboards.custom',          'DISABLED', NULL),

  -- integrations (paid)
  ('integration.helpdesk.outbound',      'DISABLED', NULL),
  ('integration.helpdesk.inbound',       'DISABLED', NULL),
  ('integration.erp.accounting',         'DISABLED', NULL),
  ('integration.api.webhooks',           'DISABLED', NULL),

  ('support.internal',                   'ENABLED', NULL),
  ('support.email_notifications',        'ENABLED', NULL),
  ('slo.monitoring.readonly',            'DISABLED', NULL),
  ('slo.tiers',                          'DISABLED', NULL),
  ('sla.contractual',                    'DISABLED', NULL),
  ('support.priority',                   'DISABLED', NULL),
  ('support.incident_escalation',        'DISABLED', NULL)
) AS v(feature_key, availability, limits_json)
ON TRUE
WHERE p.code='CONTROL' AND p.version=1
ON CONFLICT (plan_id, feature_key) DO UPDATE
SET availability = EXCLUDED.availability,
    limits_json = EXCLUDED.limits_json;

-- ---------- INTEGRATE ----------
INSERT INTO subscription_plan_features (plan_id, feature_key, availability, limits_json)
SELECT p.id, v.feature_key, v.availability, v.limits_json::jsonb
FROM subscription_plans p
JOIN (VALUES
  ('feature.portal.core',                'ENABLED', NULL),
  ('feature.portal.entities',            'ENABLED', NULL),
  ('feature.export.async_csv',           'ENABLED', NULL),
  ('feature.notifications.in_app',       'ENABLED', NULL),
  ('feature.access.rbac_abac',           'ENABLED', NULL),
  ('feature.audit.basic',                'ENABLED', NULL),

  ('feature.analytics.summary',          'ENABLED', NULL),
  ('feature.analytics.drilldown',        'ENABLED', NULL),
  ('feature.analytics.advanced',         'DISABLED', NULL),

  ('feature.reports.csv',                'ENABLED', NULL),
  ('feature.reports.xlsx',               'ENABLED', NULL),
  ('feature.reports.retention',          'ENABLED', NULL),

  ('feature.export.async',               'ENABLED', NULL),
  ('feature.export.progress',            'ENABLED', NULL),
  ('feature.export.eta',                 'ENABLED', NULL),
  ('feature.export.large_100k',          'ENABLED', NULL),
  ('feature.export.streaming_priority',  'DISABLED', NULL),

  ('feature.dashboards.user',            'ENABLED', NULL),
  ('feature.dashboards.health',          'ENABLED', NULL),
  ('feature.dashboards.custom',          'DISABLED', NULL),

  -- integrations (paid add-ons)
  ('integration.helpdesk.outbound',      'ADDON_ELIGIBLE', NULL),
  ('integration.helpdesk.inbound',       'ADDON_ELIGIBLE', NULL),
  ('integration.erp.accounting',         'DISABLED', NULL),
  ('integration.api.webhooks',           'DISABLED', NULL),

  ('support.internal',                   'ENABLED', NULL),
  ('support.email_notifications',        'ENABLED', NULL),
  ('slo.monitoring.readonly',            'ENABLED', NULL),
  ('slo.tiers',                          'DISABLED', NULL),
  ('sla.contractual',                    'DISABLED', NULL),
  ('support.priority',                   'DISABLED', NULL),
  ('support.incident_escalation',        'DISABLED', NULL)
) AS v(feature_key, availability, limits_json)
ON TRUE
WHERE p.code='INTEGRATE' AND p.version=1
ON CONFLICT (plan_id, feature_key) DO UPDATE
SET availability = EXCLUDED.availability,
    limits_json = EXCLUDED.limits_json;

-- ---------- ENTERPRISE ----------
INSERT INTO subscription_plan_features (plan_id, feature_key, availability, limits_json)
SELECT p.id, v.feature_key, v.availability, v.limits_json::jsonb
FROM subscription_plans p
JOIN (VALUES
  ('feature.portal.core',                'ENABLED', NULL),
  ('feature.portal.entities',            'ENABLED', NULL),
  ('feature.export.async_csv',           'ENABLED', NULL),
  ('feature.notifications.in_app',       'ENABLED', NULL),
  ('feature.access.rbac_abac',           'ENABLED', NULL),
  ('feature.audit.basic',                'ENABLED', NULL),

  ('feature.analytics.summary',          'ENABLED', NULL),
  ('feature.analytics.drilldown',        'ENABLED', NULL),
  ('feature.analytics.advanced',         'ENABLED', NULL),

  ('feature.reports.csv',                'ENABLED', NULL),
  ('feature.reports.xlsx',               'ENABLED', NULL),
  ('feature.reports.retention',          'ENABLED', NULL),

  ('feature.export.async',               'ENABLED', NULL),
  ('feature.export.progress',            'ENABLED', NULL),
  ('feature.export.eta',                 'ENABLED', NULL),
  ('feature.export.large_100k',          'ENABLED', NULL),
  ('feature.export.streaming_priority',  'ADDON_ELIGIBLE', NULL),

  ('feature.dashboards.user',            'ENABLED', NULL),
  ('feature.dashboards.health',          'ENABLED', NULL),
  ('feature.dashboards.custom',          'ENABLED', NULL),

  -- integrations (paid add-ons)
  ('integration.helpdesk.outbound',      'ADDON_ELIGIBLE', NULL),
  ('integration.helpdesk.inbound',       'ADDON_ELIGIBLE', NULL),
  ('integration.erp.accounting',         'ADDON_ELIGIBLE', NULL),
  ('integration.api.webhooks',           'ADDON_ELIGIBLE', NULL),

  ('support.internal',                   'ENABLED', NULL),
  ('support.email_notifications',        'ENABLED', NULL),
  ('slo.monitoring.readonly',            'ENABLED', NULL),
  ('slo.tiers',                          'ENABLED', NULL),
  ('sla.contractual',                    'ENABLED', NULL),
  ('support.priority',                   'ENABLED', NULL),
  ('support.incident_escalation',        'ENABLED', NULL)
) AS v(feature_key, availability, limits_json)
ON TRUE
WHERE p.code='ENTERPRISE' AND p.version=1
ON CONFLICT (plan_id, feature_key) DO UPDATE
SET availability = EXCLUDED.availability,
    limits_json = EXCLUDED.limits_json;

-- =========================================================
-- 6) PRICING CATALOG (optional but useful) — upsert-like insert
-- Note: pricing_catalog has no unique constraint; keep this as "append-only"
-- If you want strict upsert, add UNIQUE(item_type,item_id,effective_from) and update accordingly.
-- =========================================================

-- Usage meters (minimal seed)
INSERT INTO usage_meters (code, title, unit)
VALUES
  ('exports_jobs', 'Exports jobs', 'шт'),
  ('exports_rows', 'Exports rows', 'строк')
ON CONFLICT (code) DO NOTHING;

-- Plans pricing (placeholder numbers; adjust)
INSERT INTO pricing_catalog (item_type, item_id, currency, price_monthly, price_yearly, effective_from, effective_to)
SELECT 'PLAN', p.id, 'RUB',
       CASE p.code
         WHEN 'FREE' THEN 0.00
         WHEN 'CONTROL' THEN 9900.00
         WHEN 'INTEGRATE' THEN 29900.00
         WHEN 'ENTERPRISE' THEN NULL
       END,
       CASE p.code
         WHEN 'FREE' THEN 0.00
         WHEN 'CONTROL' THEN 9900.00 * 10
         WHEN 'INTEGRATE' THEN 29900.00 * 10
         WHEN 'ENTERPRISE' THEN NULL
       END,
       now(), NULL
FROM subscription_plans p
WHERE p.version=1
  AND p.code IN ('FREE','CONTROL','INTEGRATE','ENTERPRISE');

-- Usage pricing (placeholder numbers; adjust)
INSERT INTO pricing_catalog (item_type, item_id, currency, price_monthly, price_yearly, effective_from, effective_to)
SELECT 'USAGE_METER', m.id, 'RUB',
       CASE m.code
         WHEN 'exports_jobs' THEN 1.00
         WHEN 'exports_rows' THEN 0.01
       END,
       NULL,
       now(), NULL
FROM usage_meters m
WHERE m.code IN ('exports_jobs', 'exports_rows');

-- Add-ons pricing (placeholder)
INSERT INTO pricing_catalog (item_type, item_id, currency, price_monthly, price_yearly, effective_from, effective_to)
SELECT 'ADDON', a.id, a.currency,
       a.default_price,
       a.default_price * 10,
       now(), NULL
FROM addons a
WHERE a.is_active = TRUE;

COMMIT;
