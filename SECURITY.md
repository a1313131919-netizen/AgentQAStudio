# Security and Responsible Use

## Secrets

- Do not commit API keys, passwords, cookies, private tokens, or internal customer data.
- Agent QA Studio intentionally does not persist the API Bearer Token through its API config saver.
- Browser Auto uses a dedicated browser profile. Treat that directory as sensitive because it may contain session cookies.

## Browser automation

Use Browser Auto only for websites and systems you own or are explicitly authorized to test.

Do not use this project to:

- bypass authentication or authorization,
- defeat CAPTCHAs,
- evade rate limits,
- scrape data you are not allowed to access,
- automate destructive production actions without an approved test plan.

## Test data

Prefer synthetic or dedicated QA data.

Avoid putting real personal, confidential, health, financial, or production secrets into public screenshots, example Test Cases, issues, or reports.

## Vulnerability reports

If you discover a security issue in Agent QA Studio itself, avoid publishing exploit details in a public issue until maintainers have had a reasonable opportunity to review it.
