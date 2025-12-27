# Fuel Limits Model

## Scopes (priority order)
1. CARD  
2. VEHICLE  
3. DRIVER  
4. CARD_GROUP  
5. CLIENT  

## Limit types
- AMOUNT (minor units)
- VOLUME (ml)
- COUNT (transactions)

## Periods
- DAILY (MSK calendar day)
- WEEKLY (ISO week)
- MONTHLY (calendar month)

## Explain payload
If a limit is exceeded, API returns:
```
{
  "decline_code": "LIMIT_EXCEEDED_AMOUNT",
  "limit_explain": {
    "scope_type": "CARD",
    "scope_id": "card-123",
    "limit_type": "AMOUNT",
    "period": "DAILY",
    "limit": 500000,
    "used": 490000,
    "attempt": 20000,
    "remaining": 10000
  }
}
```
