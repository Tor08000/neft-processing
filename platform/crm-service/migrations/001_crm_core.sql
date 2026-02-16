CREATE TABLE IF NOT EXISTS crm_contacts (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  first_name text NOT NULL,
  last_name text NOT NULL,
  email text NOT NULL,
  phone text,
  position text,
  status text NOT NULL DEFAULT 'active',
  owner_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_crm_contacts_tenant_email ON crm_contacts(tenant_id, email);
CREATE INDEX IF NOT EXISTS ix_crm_contacts_tenant_entity ON crm_contacts(tenant_id, entity_id);

CREATE TABLE IF NOT EXISTS crm_pipelines (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crm_stages (
  id uuid PRIMARY KEY,
  pipeline_id uuid NOT NULL REFERENCES crm_pipelines(id) ON DELETE CASCADE,
  name text NOT NULL,
  position int NOT NULL,
  probability int NOT NULL
);

CREATE TABLE IF NOT EXISTS crm_deals (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  contact_id uuid REFERENCES crm_contacts(id),
  pipeline_id uuid NOT NULL REFERENCES crm_pipelines(id),
  stage_id uuid NOT NULL REFERENCES crm_stages(id),
  title text NOT NULL,
  amount numeric(14,2) NOT NULL,
  currency text NOT NULL,
  status text NOT NULL DEFAULT 'open',
  owner_id uuid NOT NULL,
  expected_close_date date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_crm_deals_tenant_stage ON crm_deals(tenant_id, stage_id);
CREATE INDEX IF NOT EXISTS ix_crm_deals_tenant_owner ON crm_deals(tenant_id, owner_id);

CREATE TABLE IF NOT EXISTS crm_tasks (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  related_type text NOT NULL,
  related_id uuid NOT NULL,
  title text NOT NULL,
  description text,
  due_date timestamptz,
  status text NOT NULL DEFAULT 'open',
  priority text,
  assigned_to uuid NOT NULL,
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crm_comments (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  related_type text NOT NULL,
  related_id uuid NOT NULL,
  message text NOT NULL,
  author_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crm_audit_log (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  action text NOT NULL,
  old_data jsonb,
  new_data jsonb,
  actor_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outbox_events (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz
);
