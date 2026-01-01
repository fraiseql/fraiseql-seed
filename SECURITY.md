# Security Policy

## Supported Versions

| Package | Version | Supported          |
| ------- | ------- | ------------------ |
| fraiseql-uuid | 0.1.x   | :white_check_mark: |
| fraiseql-data | 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### 1. Do NOT Open a Public Issue

Please do not report security vulnerabilities through public GitHub issues.

### 2. Report via GitHub Security Advisories

**Preferred Method**: [Create a Security Advisory](https://github.com/fraiseql/fraiseql-seed/security/advisories/new)

If you prefer email, send details to: **security@fraiseql.dev**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Affected package (fraiseql-uuid, fraiseql-data, or both)
- Suggested fix (if any)

### 3. Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity
  - **Critical**: 24-48 hours
  - **High**: 7 days
  - **Medium**: 30 days
  - **Low**: Next release

## Security Features

### fraiseql-uuid: Secure UUID Generation

**fraiseql-uuid** provides cryptographically secure UUID generation with collision prevention:

1. **UUID v4 Randomness**: Uses `secrets` module for cryptographic randomness
2. **UUID Validation**: Pattern-based validation prevents invalid UUIDs
3. **Collision Detection**: Built-in cache to detect and prevent collisions
4. **Trinity Pattern**: Integer PK + UUID + identifier for data integrity

```python
from fraiseql_uuid import UUIDGenerator

# Cryptographically secure UUID generation
generator = UUIDGenerator(pattern="product")
uuid = generator.generate(instance=1)  # Collision-resistant
```

### fraiseql-data: Secure Seed Data Generation

**fraiseql-data** provides safe seed data generation with security best practices:

1. **SQL Injection Prevention**: All queries use parameterized statements via psycopg3
2. **Schema Introspection**: Read-only database introspection
3. **Constraint Validation**: Enforces CHECK, UNIQUE, and FK constraints
4. **No Data Exposure**: Staging backend works without database connection
5. **Faker Integration**: Production-safe fake data generation

```python
from fraiseql_data import SeedBuilder

# Safe seed data generation
builder = SeedBuilder(conn=conn, schema="public")
builder.introspect()  # Read-only introspection
seeds = builder.build(table_name="users", count=100)
```

## Security Best Practices

### When Using fraiseql-uuid

✅ **DO**:
- Use cryptographically secure UUID generation in production
- Validate UUIDs before database insertion
- Enable collision detection for high-volume scenarios

❌ **DON'T**:
- Don't use predictable patterns for UUID generation
- Don't bypass validation for performance
- Don't store UUIDs without proper indexing

### When Using fraiseql-data

✅ **DO**:
- Use read-only database connections for introspection
- Validate seed data before production use
- Use staging backend for development/testing
- Review generated SQL before execution

❌ **DON'T**:
- Don't use production database for seed generation
- Don't commit seed data with sensitive information
- Don't bypass constraint validation
- Don't execute untrusted seed configurations

## Supply Chain Security

Both packages follow government-grade supply chain security standards:

### SBOM (Software Bill of Materials)

- **Format**: CycloneDX 1.5 (OWASP standard)
- **Signing**: Cosign keyless (Sigstore)
- **Compliance**: US EO 14028, EU NIS2/CRA, PCI-DSS 4.0, ISO 27001

Download SBOMs from [GitHub Releases](https://github.com/fraiseql/fraiseql-seed/releases)

### Dependency Management

- **Automated Scanning**: Weekly dependency vulnerability audits via pip-audit
- **License Compliance**: No GPL dependencies (LGPL/MIT/Apache only)
- **Minimal Dependencies**: Small attack surface
- **Pinned Versions**: Controlled dependency updates

### CI/CD Security

- **Quality Gate**: Automated testing (99/99 tests passing, 86% coverage)
- **Security Scanning**: TruffleHog, Trivy, pip-audit
- **License Auditing**: Automated GPL detection
- **Multi-Python**: Tested on Python 3.11, 3.12, 3.13

## Known Security Considerations

### fraiseql-uuid

- **UUID Collisions**: While extremely rare (1 in 2^122 for UUID v4), collision detection is available
- **Performance**: UUID generation is cryptographically secure but slower than simple incrementing

### fraiseql-data

- **Database Permissions**: Requires read access to `information_schema` for introspection
- **Faker Data**: Generated fake data is not cryptographically random (use for testing only)
- **Constraint Satisfaction**: Complex CHECK constraints may not be fully satisfiable

## Vulnerability Disclosure Policy

We follow **coordinated disclosure**:

1. **Report received**: We acknowledge within 48 hours
2. **Triage**: Severity assessment within 7 days
3. **Fix development**: Timeline based on severity
4. **Testing**: Fix validation and regression testing
5. **Release**: Security patch release
6. **Disclosure**: Public disclosure 30 days after fix or by mutual agreement

## Security Contacts

- **GitHub Security Advisories**: [Create Advisory](https://github.com/fraiseql/fraiseql-seed/security/advisories/new)
- **Email**: security@fraiseql.dev
- **Response Time**: 48 hours

## Acknowledgments

We appreciate security researchers who help keep our projects safe. Security researchers who responsibly disclose vulnerabilities will be acknowledged in:

- Release notes
- Security advisories
- CHANGELOG.md (with permission)

Thank you for helping keep fraiseql-seed secure! 🔒
