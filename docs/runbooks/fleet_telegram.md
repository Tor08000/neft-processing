# Fleet Telegram Notifications Runbook

## Overview

Telegram notifications are delivered via the Fleet notification outbox using a bot webhook. Chat bindings are created through bot deep links (`/start <token>`).

## Configure webhook

1. Set environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_BOT_USERNAME`
   - `TELEGRAM_WEBHOOK_SECRET`
   - `TELEGRAM_WEBHOOK_PATH` (default: `/api/internal/telegram/webhook`)
2. Register the webhook with Telegram:

```
POST https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook
{
  "url": "https://<core-api-host>/api/internal/telegram/webhook",
  "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"
}
```

3. Verify webhook configuration:

```
GET https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo
```

Ensure `pending_update_count` is low and `last_error_message` is empty.

## Bind a chat

1. In the client portal, open **Fleet → Notifications → Channels**.
2. Click **Connect Telegram**, select the scope, and generate a link.
3. Click **Open Telegram** to open the bot and confirm the `/start <token>` command.

## Verify secret token

Webhook requests must include the header:

```
X-Telegram-Bot-Api-Secret-Token: <TELEGRAM_WEBHOOK_SECRET>
```

If the header is missing or invalid, the webhook returns `403` and the update is ignored.

## Common issues

| Symptom | Cause | Resolution |
| --- | --- | --- |
| `telegram_permanent_failure` | Bot blocked or chat deleted | Disable the binding and re-bind the chat. |
| `telegram_rate_limited` | Bot exceeded rate limit | Let the outbox retry, or reduce message volume. |
| No bindings appear | Link token expired | Generate a new link in the portal. |

## Replay delivery

If an outbox entry is stuck in `FAILED`, you can re-dispatch it:

```
POST /api/admin/fleet/notifications/outbox/{id}/dispatch
```

(Use an admin token and ensure the binding is active.)
