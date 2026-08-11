# Security Policy

Please report vulnerabilities privately through GitHub Security Advisories. Do not open a public
issue containing credentials, webhook payloads, or exploit details.

Checkpoint 1 supports only GitHub webhook ingestion. It verifies the raw request body with
HMAC-SHA256, stores a minimal event envelope, and has no repository write permission.
