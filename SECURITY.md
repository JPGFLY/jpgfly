# Security Policy

## Public repository boundary

This repository contains source code only. Production credentials, model nodes, tunnels,
operator configuration, hosted service IDs, private endpoints, and private training artifacts
must stay outside Git.

## Reporting

If you discover a vulnerability that could expose a real JPGFLY deployment, do not publish
working credentials, private endpoints, personal data, or exploit details in a public issue.
Use GitHub's private vulnerability reporting / security advisory features when available.

## Deployment guidance

- Generate unique secrets for every deployment.
- Keep secrets in the hosting platform's secret store or local environment.
- Do not expose Ollama/FLM endpoints directly to the public internet without authentication.
- Bind local-only services to loopback unless remote access is explicitly required.
- Put public deployments behind HTTPS.
- Treat any copied `.env` or pairing token as sensitive.
- Never reuse the operator's production credentials in a fork.


## Local model-service boundary

Keep optional model services loopback-only unless you intentionally place an authenticated boundary in front of them.

Typical local ports:

- Ollama/Qwen: `127.0.0.1:11434`
- FLM bridge: `127.0.0.1:4680`
- authenticated model gateway: `127.0.0.1:4681`
- MaleCNS service: `127.0.0.1:4690`
- ZebraCNS service: `127.0.0.1:4770`

Do not expose raw Ollama, FLM, MaleCNS or ZebraCNS endpoints directly to the public internet. If remote access is required, use a narrow authenticated gateway, separate credentials from application control credentials, TLS, request-size limits, and a route allowlist.

The Fly Brain itself is Python and can continue painting during short language/model outages. A genuine Candidate Fly Brain decision failure switches to the independent DUMB DUMB pure-Python emergency painter. Finished Rooms remain normal through 35% actual emergency-fallback decisions; only a ratio above 35% is archived as DUMB DUMB.
