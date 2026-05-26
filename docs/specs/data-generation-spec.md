# Data Generation Specification

## Purpose

Define how deterministic synthetic data is produced for enterprise mimics.

## Owns

- seed handling
- static data loading
- Faker data generation
- hybrid data composition

## Does not own

- page rendering
- route matching
- metrics storage

## Providers

```text
yaml
json
faker
hybrid
```

## Requirements

### R1

Data generation shall be deterministic for the same seed.

### R2

Each app may define its own data model.

### R3

Generated data shall be local only.

### R4

Data shall not contain real personal data.

## Config

```yaml
data:
  app: salesforce
  provider: faker
  seed: 12345
  entities:
    accounts:
      count: 50
    contacts:
      count: 200
```

## Output

```json
{
  "accounts": [
    {
      "id": "001",
      "name": "Example GmbH",
      "status": "active"
    }
  ]
}
```

## Seed behavior

Same input:

```text
app
provider
seed
entity config
```

must produce same output.

## Hybrid provider

Combines static records and generated fields.

```yaml
provider: hybrid
static: data/enterprise/salesforce/accounts.yaml
faker:
  contacts:
    count: 100
```

## Validation

Reject:

```text
missing provider
invalid seed
unknown entity
invalid static file
non-deterministic provider
```
