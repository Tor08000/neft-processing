# Fuel Domain v1 (Fleet-first)

## Overview
Fuel v1 introduces fleet-first fuel operations for B2B clients. The domain supports vehicles, drivers, card groups, fuel cards, limits, risk decisions, ledger postings, billing aggregation, and audit/legal graph links.

## Core flow
1. Authorize fuel transaction:
   - Resolve card → network/station.
   - Resolve vehicle/driver (payload or card linkage).
   - Apply limits (CARD → VEHICLE → DRIVER → CARD_GROUP → CLIENT).
   - Evaluate Risk v4 (DecisionEngine) with fuel-specific context.
   - Persist `fuel_transactions` as `AUTHORIZED`, `REVIEW_REQUIRED`, or `DECLINED`.
2. Settle:
   - Post internal ledger entries (CLIENT_AR → PROVIDER_PAYABLE).
   - Mark transaction `SETTLED`.
3. Reverse:
   - Post reversal ledger entries.
   - Mark transaction `REVERSED`.

## Data model
- Fleet: `fleet_vehicles`, `fleet_drivers`
- Fuel domain: `fuel_card_groups`, `fuel_cards`, `fuel_networks`, `fuel_stations`, `fuel_limits`, `fuel_transactions`

## Audit & legal graph
Each fuel transaction emits audit events and creates legal graph links:
- `FUEL_TX_AUTHORIZED`, `FUEL_TX_DECLINED`, `FUEL_TX_REVIEW_REQUIRED`, `FUEL_TX_SETTLED`, `FUEL_TX_REVERSED`
- Links: `FUEL_TRANSACTION` → `CARD`, `VEHICLE`, `FUEL_STATION`, `RISK_DECISION`
