@echo off
setlocal

echo [1/4] Starting stack...
docker compose up -d gateway core-api logistics-service integration-hub

echo [2/4] Fleet list 200...
curl -i -X POST http://localhost/api/logistics/v1/fleet/list -H "Content-Type: application/json" -d "{\"limit\":10,\"offset\":0}"

echo [3/4] Trip create idempotent...
curl -i -X POST http://localhost/api/logistics/v1/trips/create -H "Content-Type: application/json" -H "Idempotency-Key: demo-trip-1" -d "{\"trip_id\":\"trip-1\",\"vehicle_id\":\"veh-1\",\"route_id\":\"route-1\"}"
curl -i -X POST http://localhost/api/logistics/v1/trips/create -H "Content-Type: application/json" -H "Idempotency-Key: demo-trip-1" -d "{\"trip_id\":\"trip-1\",\"vehicle_id\":\"veh-1\",\"route_id\":\"route-1\"}"

echo [4/4] Check logs...
docker compose logs --tail=100 logistics-service integration-hub

endlocal
