# Vehicle Profile & Service Recommendations v1

## Goal
Create a client-facing vehicle profile (“car social page”) that automatically estimates mileage from fuel transactions and produces explainable service recommendations tied to real usage.

## Product concept
### Vehicle page (“Profile”)
Each vehicle is a standalone entity with its own history.

Profile includes:
- brand / model / year
- engine / fuel type
- VIN (optional)
- plate number (optional)
- start odometer
- current estimated odometer
- usage style
- fuel history
- recommendations history
- service history

### Why it works
- Client sees value (care, not ads)
- Recommendations are backed by data
- Partners receive “right time” leads (e.g. “time for service”)
- NEFT becomes the vehicle ownership hub, not just a fuel card

## Data model
### Vehicle
`vehicles`
- `id UUID PK`
- `tenant_id UUID`
- `client_id UUID`
- `brand TEXT`
- `model TEXT`
- `year INT`
- `engine_type TEXT` — petrol, diesel, hybrid, electric
- `engine_volume NUMERIC`
- `fuel_type TEXT` — AI92, AI95, DT
- `vin TEXT NULL`
- `plate_number TEXT NULL`
- `start_odometer_km NUMERIC NOT NULL`
- `current_odometer_km NUMERIC NOT NULL`
- `odometer_source TEXT` — MANUAL, ESTIMATED, MIXED
- `avg_consumption_l_per_100km NUMERIC NULL`
- `usage_type TEXT` — city, highway, mixed, aggressive
- `created_at TIMESTAMPTZ`
- `updated_at TIMESTAMPTZ`

### Vehicle ↔ fuel card linkage
`vehicle_cards`
- `vehicle_id UUID`
- `card_id UUID`
- `linked_at TIMESTAMPTZ`
- `PRIMARY KEY(vehicle_id, card_id)`

### Mileage history (append-only)
`vehicle_mileage_events`
- `id UUID PK`
- `vehicle_id UUID`
- `source TEXT` — FUEL_TXN, MANUAL_UPDATE, SERVICE_EVENT
- `fuel_txn_id UUID NULL`
- `liters NUMERIC NULL`
- `estimated_km NUMERIC NULL`
- `odometer_before NUMERIC`
- `odometer_after NUMERIC`
- `created_at TIMESTAMPTZ`

### Service intervals (reference, not partner-specific)
`service_intervals`
- `id UUID PK`
- `brand TEXT`
- `model TEXT`
- `engine_type TEXT`
- `service_type TEXT` — OIL_CHANGE, FILTERS, BRAKES, TIMING, ETC
- `interval_km NUMERIC`
- `interval_months INT NULL`
- `description TEXT`

### Recommendation history
`vehicle_recommendations`
- `id UUID PK`
- `vehicle_id UUID`
- `service_type TEXT`
- `recommended_at_km NUMERIC`
- `current_km NUMERIC`
- `status TEXT` — ACTIVE, ACCEPTED, DONE, DISMISSED
- `reason TEXT`
- `partner_id UUID NULL`
- `created_at TIMESTAMPTZ`

## Mileage engine (v1)
### Base formula
Estimated mileage is derived from fuel transactions:

```
estimated_km = (liters / avg_consumption) * 100
```

Where:
- `liters` comes from fuel transactions
- `avg_consumption`:
  - initially from vehicle profile
  - fallback to defaults by `engine_type` when missing
  - adjusts over time using a moving average

### Algorithm
On each fuel transaction:
1. If the card is linked to a vehicle:
2. Calculate `estimated_km`.
3. Append a `vehicle_mileage_event`.
4. Update `current_odometer_km`.
5. Check service intervals for recommendations.

### Manual correction
Client can provide real odometer data:
- create a `MANUAL_UPDATE` event
- update future estimation
- mark `odometer_source = MIXED`

## Service recommendation engine
### Recommendation logic
For each `service_interval`:

```
if current_km >= last_service_km + interval_km - threshold:
    recommend
```

Threshold examples:
- Oil change: 500–1000 km
- Brakes: 2000 km

### Explainability
Each recommendation includes a human-readable reason, e.g.

> “You have driven 9,800 km since your last oil change. The average interval is 10,000 km.”

### Partner linkage
If matching partners are available, include offers based on:
- region
- rating
- partner tier
- active promotions (C1)
- sponsored placements (C3)

## API
### Vehicle profile
- `POST /api/client/vehicles`
- `GET /api/client/vehicles`
- `GET /api/client/vehicles/{id}`
- `PATCH /api/client/vehicles/{id}`

### Mileage
- `GET /api/client/vehicles/{id}/mileage`
- `GET /api/client/vehicles/{id}/events`

### Recommendations
- `GET /api/client/vehicles/{id}/recommendations`
- `POST /api/client/vehicles/{id}/recommendations/{rec_id}/accept`
- `POST /api/client/vehicles/{id}/recommendations/{rec_id}/dismiss`

## UI / UX
### Client portal: “My vehicles”
Card layout shows:
- brand / model
- current mileage
- service status (🟢 🟡 🔴)

### Vehicle page (“social page”)
Blocks:
- vehicle photo (optional)
- key parameters
- mileage chart
- recent refuels
- “What to do next” list
- “Book service” CTA

### Marketplace integration
Each recommendation can display:
- partner name
- price / promotion
- distance
- rating
- badges (C2)

## Jobs
Nightly:
- recompute `avg_consumption`
- recompute mileage
- generate recommendations

On fuel transaction:
- realtime mileage update
- interval check

## Trust / audit
Append-only storage:
- mileage events
- manual corrections
- recommendation events

Each event chain:
- `hash`
- `signature`
- `prev_hash`

## Monetization
Partners pay for:
- service booking leads (CPA)
- promoted placement (C3)

Clients receive:
- discounts
- bonuses
- trust

## Done criteria
- ✅ Client can create a vehicle
- ✅ Mileage is calculated automatically
- ✅ Client sees current mileage
- ✅ System recommends service based on real usage
- ✅ Recommendations are explainable
- ✅ Partner offers are reachable
- ✅ All events are audit-bound
