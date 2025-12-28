# CRM Risk Profile Examples

## Canonical definition schema

```json
{
  "version": 1,
  "profile_id": "fuel_default_v4",
  "scope": {
    "applies_to": ["FUEL_TX_AUTHORIZE", "FUEL_TX_SETTLE"],
    "client_override_allowed": true
  },
  "policy_binding": {
    "risk_policy_id": "FUEL_DEFAULT_V4",
    "threshold_set_id": "fuel_default_v4",
    "shadow_enabled": false
  },
  "signal_inputs": {
    "use_logistics_signals": true,
    "use_fuel_analytics_signals": true,
    "logistics_signal_window_hours": 24,
    "max_signal_severity_used": true
  },
  "review_policy": {
    "review_required_behavior": "AUTH_WITH_REVIEW",
    "settle_requires_admin_approval": true
  },
  "explain": {
    "include_thresholds": true,
    "include_policy": true,
    "include_top_factors": true,
    "max_factors": 5
  }
}
```

## fuel_default_v4

```json
{
  "version": 1,
  "profile_id": "fuel_default_v4",
  "scope": {
    "applies_to": ["FUEL_TX_AUTHORIZE", "FUEL_TX_SETTLE"],
    "client_override_allowed": true
  },
  "policy_binding": {
    "risk_policy_id": "FUEL_DEFAULT_V4",
    "threshold_set_id": "fuel_default_v4",
    "shadow_enabled": false
  },
  "signal_inputs": {
    "use_logistics_signals": true,
    "use_fuel_analytics_signals": true,
    "logistics_signal_window_hours": 24,
    "max_signal_severity_used": true
  },
  "review_policy": {
    "review_required_behavior": "AUTH_WITH_REVIEW",
    "settle_requires_admin_approval": true
  },
  "thresholds_hint": {
    "allow_max": 40,
    "review_max": 60,
    "block_min": 80
  },
  "explain": {
    "include_thresholds": true,
    "include_policy": true,
    "include_top_factors": true,
    "max_factors": 5
  }
}
```

## fuel_high_risk_v4

```json
{
  "version": 1,
  "profile_id": "fuel_high_risk_v4",
  "scope": {
    "applies_to": ["FUEL_TX_AUTHORIZE", "FUEL_TX_SETTLE"],
    "client_override_allowed": true
  },
  "policy_binding": {
    "risk_policy_id": "FUEL_HIGH_RISK_V4",
    "threshold_set_id": "fuel_high_risk_v4",
    "shadow_enabled": false
  },
  "signal_inputs": {
    "use_logistics_signals": true,
    "use_fuel_analytics_signals": true,
    "logistics_signal_window_hours": 48,
    "max_signal_severity_used": true,
    "severity_multiplier": 1.2
  },
  "review_policy": {
    "review_required_behavior": "AUTH_WITH_REVIEW",
    "settle_requires_admin_approval": true
  },
  "thresholds_hint": {
    "allow_max": 30,
    "review_max": 55,
    "block_min": 75
  },
  "explain": {
    "include_thresholds": true,
    "include_policy": true,
    "include_top_factors": true,
    "max_factors": 7
  }
}
```

## enterprise_fuel_v4

```json
{
  "version": 1,
  "profile_id": "enterprise_fuel_v4",
  "scope": {
    "applies_to": ["FUEL_TX_AUTHORIZE", "FUEL_TX_SETTLE", "ACCOUNTING_EXPORT_CONFIRM", "DOCUMENT_FINALIZE"],
    "client_override_allowed": false
  },
  "policy_binding": {
    "risk_policy_id": "ENTERPRISE_FUEL_V4",
    "threshold_set_id": "enterprise_fuel_v4",
    "shadow_enabled": true
  },
  "signal_inputs": {
    "use_logistics_signals": true,
    "use_fuel_analytics_signals": true,
    "logistics_signal_window_hours": 72,
    "max_signal_severity_used": true,
    "severity_multiplier": 1.3
  },
  "review_policy": {
    "review_required_behavior": "AUTH_WITH_REVIEW",
    "settle_requires_admin_approval": true,
    "final_actions_require_override_reason": true
  },
  "thresholds_hint": {
    "allow_max": 25,
    "review_max": 50,
    "block_min": 70
  },
  "explain": {
    "include_thresholds": true,
    "include_policy": true,
    "include_top_factors": true,
    "include_signal_summary": true,
    "max_factors": 10
  },
  "compliance_mode": {
    "persist_explain_snapshot": true,
    "require_decision_hash": true,
    "audit_visibility": "INTERNAL"
  }
}
```
