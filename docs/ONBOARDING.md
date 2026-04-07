# Pilot user onboarding

Quick path to try Overage as a **pilot** customer: send traffic through the proxy, authenticate, and review results in the dashboard.

## 1. Install the SDK

Add the Overage Python package to the environment that calls LLM APIs (see the root **README.md** and `sdk/` for package name and version). Use the same Python version your team standardizes on for services that talk to OpenAI or Anthropic.

## 2. Get an API key

Register via the API (see **[API.md](./API.md)**) or the flow your pilot program provides, then create an **API key**. Store it in your secret manager; treat it like any other production credential.

## 3. Patch the OpenAI client

Point your OpenAI-compatible client at the Overage proxy base URL instead of the provider’s default host. Keep your existing provider API key in the request headers as today—Overage forwards to the provider after logging and estimation. Adjust only the **base URL** (and TLS settings) per integration docs.

## 4. View the dashboard

Open the dashboard URL for your environment (local or deployed). Confirm calls appear, review discrepancy summaries and per-call detail, and use this during the pilot to validate behavior against your internal expectations.

For deployment and environment variables, see **[DEPLOYMENT.md](./DEPLOYMENT.md)**.

## Troubleshooting

If calls do not appear in the dashboard, verify the proxy base URL, that your API key is accepted (`401` vs `200` on auth routes), and that outbound TLS to the provider succeeds from your network. Check **[API.md](./API.md)** for health and listing endpoints to confirm traffic is reaching Overage.

## Where to read more

- **Product behavior:** [PRD.md](../PRD.md)
- **System design:** [ARCHITECTURE.md](../ARCHITECTURE.md)
- **Estimation details:** [ESTIMATION.md](./ESTIMATION.md)

For pilot-specific SLAs or support channels, use the contact path provided with your onboarding email.
