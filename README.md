# JARVIS Bridge — Android app-launch integration 1.1

## What is implemented
- FastAPI service protected by a Bearer API key.
- Fixed allowlist of app-launch actions: WhatsApp Business, Camera, Instagram, Gmail and Android Settings.
- Each action maps to a private MacroDroid webhook stored only in Render environment variables; callers cannot submit arbitrary URLs.
- SQLite request-ID deduplication to prevent accidental repeated dispatches.
- `/health` reports configured action identifiers, never webhook values.
- `openapi.yaml` describes the current ChatGPT Action contract.

## Important deployment status
Code changes to the connected GitHub `main` branch trigger Render's configured auto-deploy. The server can only execute actions whose webhook environment variables are configured. The existing WhatsApp webhook setting is preserved. Four additional MacroDroid webhooks must be created on the phone and configured in Render before those actions work end-to-end.

## Render environment variables
Keep these values private; do not commit them or paste them into chat:
- `JARVIS_API_KEY`: long random secret (32 bytes or more).
- `MACRODROID_OPEN_WHATSAPP_URL`: existing private WhatsApp webhook (preserve).
- `MACRODROID_OPEN_CAMERA_URL`: private Camera-launch webhook.
- `MACRODROID_OPEN_INSTAGRAM_URL`: private Instagram-launch webhook.
- `MACRODROID_OPEN_GMAIL_URL`: private Gmail-launch webhook.
- `MACRODROID_OPEN_SETTINGS_URL`: private Android Settings-launch webhook.
- `REQUEST_TIMEOUT_SECONDS=8`.
- `JARVIS_IDEMPOTENCY_DB=/data/jarvis.sqlite3` on a persistent disk.

The four new webhook variables are intentionally not populated automatically: they must be generated in MacroDroid on the phone. Never reuse the WhatsApp webhook for a different action; it triggers the WhatsApp macro.

## MacroDroid setup on the Samsung phone
Create one separate macro for each new action:
1. Name it clearly, e.g. `JARVIS - Abrir Câmera`.
2. Use a private MacroDroid HTTP/webhook trigger supported by the installed version.
3. Add action: Applications → Launch Application → select the target app. For Settings, choose the Android Settings app.
4. Copy that macro's unique webhook URL into the matching Render environment variable above.
5. Test each webhook directly from MacroDroid before connecting it to the API.
6. Keep MacroDroid's background/battery permissions configured so macros can run reliably.

Do not expose webhook URLs in OpenAPI, prompts, public repositories or screenshots.

## API contract
POST `/v1/actions/execute`, authenticated with `Authorization: Bearer <JARVIS_API_KEY>`.
Body example: `{"action":"open_camera","request_id":"unique-id-123"}`.
Allowed actions: `open_whatsapp`, `open_camera`, `open_instagram`, `open_gmail`, `open_settings`.
A request ID must be unique per new command. Reusing it will not dispatch another action. Legacy clients may still send `confirmation: true`.

## Validation
Run `pip install -r requirements.txt && pytest -q`.
A successful API/webhook response proves only that MacroDroid's webhook responded; it does not prove visually that Android opened the app. End-to-end validation requires a real phone and the private webhooks.

## Security boundaries
This bridge is for launching apps only. It does not read messages, send messages, access Gmail content, take photos, change system settings, make purchases, delete data, or bypass Android permissions. Those capabilities require separate scoped integrations and appropriate authorization.
