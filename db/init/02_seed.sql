INSERT INTO clients(id, tenant_id, name, email, full_name, status)
VALUES (1,1,'Demo Client','demo@client.neft','Demo Client','ACTIVE') ON CONFLICT DO NOTHING;
INSERT INTO wallets(id, tenant_id, client_id, currency, balance, hold) VALUES (1,1,1,'RUB',100000,0) ON CONFLICT DO NOTHING;
INSERT INTO cards(id, tenant_id, client_id, wallet_id, token, status) VALUES (1,1,1,1,'CARD123','ACTIVE') ON CONFLICT DO NOTHING;

INSERT INTO client_cards(id, client_id, card_id, pan_masked, status)
VALUES
  (1,1,'CARD123','**** 3123','ACTIVE'),
  (2,1,'CARD987','**** 4987','ACTIVE')
ON CONFLICT DO NOTHING;

INSERT INTO client_operations(id, client_id, card_id, operation_type, status, amount, currency, performed_at, fuel_type)
VALUES
  (1,1,'CARD123','AUTH','success',18000,'RUB', now() - interval '1 day','diesel'),
  (2,1,'CARD123','CAPTURE','pending',7200,'RUB', now() - interval '2 days','gasoline'),
  (3,1,'CARD987','REFUND','failed',1500,'RUB', now() - interval '3 days','diesel'),
  (4,1,'CARD987','AUTH','success',22000,'RUB', now() - interval '4 days','diesel'),
  (5,1,'CARD123','AUTH','success',12000,'RUB', now() - interval '5 days','gasoline'),
  (6,1,'CARD123','CAPTURE','success',9500,'RUB', now() - interval '6 days','diesel'),
  (7,1,'CARD987','AUTH','pending',6400,'RUB', now() - interval '7 days','gasoline'),
  (8,1,'CARD987','CAPTURE','success',8300,'RUB', now() - interval '8 days','diesel'),
  (9,1,'CARD123','REFUND','success',2100,'RUB', now() - interval '9 days','gasoline'),
  (10,1,'CARD987','AUTH','success',5400,'RUB', now() - interval '10 days','diesel')
ON CONFLICT DO NOTHING;

INSERT INTO client_limits(id, client_id, limit_type, amount, currency, used_amount, period_start, period_end)
VALUES
  (1,1,'daily',50000,'RUB',18000, current_date, current_date + interval '1 day'),
  (2,1,'weekly',250000,'RUB',62000, current_date - interval '3 days', current_date + interval '4 days'),
  (3,1,'monthly',1000000,'RUB',240000, date_trunc('month', current_date), date_trunc('month', current_date) + interval '1 month')
ON CONFLICT DO NOTHING;

INSERT INTO partners(id, tenant_id, name, type) VALUES (1,1,'Demo Partner','OIL') ON CONFLICT DO NOTHING;
INSERT INTO azs(id, tenant_id, partner_id, name, address, region) VALUES (1,1,1,'Demo AZS 1','Address 1','MSK') ON CONFLICT DO NOTHING;
INSERT INTO azs(id, tenant_id, partner_id, name, address, region) VALUES (2,1,1,'Demo AZS 2','Address 2','SPB') ON CONFLICT DO NOTHING;
INSERT INTO pos(id, tenant_id, azs_id, terminal_id, vendor) VALUES (1,1,1,'POS-1','DemoVendor') ON CONFLICT DO NOTHING;

INSERT INTO products(id, tenant_id, code, name, uom) VALUES (1,1,'AI95','АИ-95','L') ON CONFLICT DO NOTHING;
INSERT INTO products(id, tenant_id, code, name, uom) VALUES (2,1,'AI92','АИ-92','L') ON CONFLICT DO NOTHING;
INSERT INTO products(id, tenant_id, code, name, uom) VALUES (3,1,'DT','ДТ','L') ON CONFLICT DO NOTHING;

INSERT INTO price_list(tenant_id, azs_id, product_id, version, price, status)
VALUES (1,1,1,1,56.00,'ACTIVE'),(1,1,2,1,54.00,'ACTIVE'),(1,1,3,1,60.00,'ACTIVE')
ON CONFLICT DO NOTHING;

-- 6 правил: карта/клиент/АЗС/по времени/velocity/сегмент(пример)
INSERT INTO rules(tenant_id, scope, subject_id, selector, window, metric, value, uom, policy, priority, enabled)
VALUES
(1,'CARD','CARD123','{"product":"AI95"}','DAILY','LITERS',200,'L','HARD_DECLINE',10,TRUE),
(1,'CLIENT','1','{"hour":[0,1,2,3,4,5]}',NULL,'AMOUNT',NULL,NULL,'SOFT_DECLINE',50,TRUE),
(1,'AZS','1','{"azs_id":1}',NULL,'COUNT',NULL,NULL,'ALLOW',100,TRUE),
(1,'CARD','CARD123','{"hour":[22,23,0,1,2,3]}',NULL,'COUNT',NULL,NULL,'SOFT_DECLINE',20,TRUE),
(1,'CARD','CARD123','{"velocity":"30m"}',NULL,'COUNT',NULL,NULL,'SOFT_DECLINE',30,TRUE),
(1,'SEGMENT','TIER_A','{"product":"DT"}',NULL,'AMOUNT',NULL,NULL,'APPLY_DISCOUNT',40,TRUE)
ON CONFLICT DO NOTHING;
