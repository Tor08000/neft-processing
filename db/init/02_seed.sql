INSERT INTO clients(id, tenant_id, name) VALUES (1,1,'Demo Client') ON CONFLICT DO NOTHING;
INSERT INTO wallets(id, tenant_id, client_id, currency, balance, hold) VALUES (1,1,1,'RUB',100000,0) ON CONFLICT DO NOTHING;
INSERT INTO cards(id, tenant_id, client_id, wallet_id, token, status) VALUES (1,1,1,1,'CARD123','ACTIVE') ON CONFLICT DO NOTHING;

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
