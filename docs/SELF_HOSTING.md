# Self-hosting

The safe default is fully local.

1. Copy `.env.example` to `.env` but do not commit `.env`.
2. Start in procedural mode first.
3. If enabling an external model endpoint, use your own endpoint and authentication.
4. Keep model services private unless you deliberately deploy an authenticated gateway.
5. Use a unique random control token for any public deployment.
6. Terminate public traffic with HTTPS.

This repository deliberately contains no production JPGFLY node URL, tunnel configuration,
or hosted service identifier.
