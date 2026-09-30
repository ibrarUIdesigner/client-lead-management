# Gmail integration setup

This workspace can send outreach through a connected Gmail account and sync
replies into lead records.

## Google Cloud configuration

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. Enable **Gmail API** (APIs & Services → Library).
4. Configure the **OAuth consent screen**:
   - User type: **External** is fine for a personal tool.
   - Publishing status: leave as **Testing**.
   - Add your own Google account under **Test users**.
   - Scopes used by this app (requested at connect time):
     - `https://www.googleapis.com/auth/gmail.send`
     - `https://www.googleapis.com/auth/gmail.readonly`
     - `openid` and `email` (account identity)
5. Create an **OAuth 2.0 Client ID** (APIs & Services → Credentials):
   - Application type: **Web application** (recommended) or Desktop.
   - Authorized redirect URI (must match env):
     - Local: `http://localhost:8000/api/v1/gmail/oauth/callback`
6. Copy the client ID and client secret into `.env`.

## Environment variables

```env
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/gmail/oauth/callback
GMAIL_FRONTEND_REDIRECT_URL=http://localhost:5175/settings
TOKEN_ENCRYPTION_KEY=...   # Fernet key; required in production
GMAIL_SYNC_ENABLED=true
GMAIL_SYNC_INTERVAL_MINUTES=3
```

Generate an encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Restart the API after changing env vars.

## Personal-use notes

- Apps in **Testing** do not need Google verification, but refresh tokens can
  expire after about 7 days of inactivity for unverified apps. Reconnect from
  Settings if the status shows **Needs reauthorization**.
- Only test users listed on the consent screen can connect.
- Do not request `https://mail.google.com/` or `gmail.modify`; send + readonly
  are enough for sending and history-based reply sync.
- History cursors can expire (often after about a week). The sync job recovers
  with a bounded recent-message resync when Gmail returns HTTP 404.

## Product behavior

- **Connect / Disconnect** live on the Settings page.
- Sending from a lead stores lead id, connected account id, recipient, Gmail
  message id, thread id, RFC Message-ID, and sent time. Lead status advances to
  **Contacted** when allowed by the forward-only pipeline rules.
- Gmail accepting `messages.send` is recorded as sent, not as confirmed delivery.
- Background sync runs on an interval (default 3 minutes) via APScheduler.
- Human replies set **Replied**, update last-reply time, show unread, and cancel
  open follow-ups. Out-of-office, bounce, and opt-out are handled separately.
- Replies are never auto-marked Interested. Advanced stages such as Meeting,
  Proposal, or Won are preserved.

## Security

- OAuth `state` is validated and short-lived.
- Access and refresh tokens are encrypted at rest with `TOKEN_ENCRYPTION_KEY`.
- Logs include account/message ids only — never tokens or email bodies.
- Disconnect clears stored credentials and stops sync for that account.
