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

## Named sets

Three named data sets are supported:

| Set | Seed | Default count per entity | Purpose |
|---|---|---|---|
| `default` | 42 | 20 | Standard fixtures; first record is the SAMPLE_PARAMS anchor |
| `large` | 42 | 200 | Volume/pagination testing |
| `dynamic` | random | 20 | Randomised smoke tests |

The active set is selected at startup via the `HARNESS_DATA_SET` environment variable (default: `default`).

## Output path

Generated files are written to `data/{set}/{app}/{entity}.json`.

Example: `data/default/salesforce/accounts.json`

## Config

```yaml
data:
  app: salesforce
  provider: faker
  seed: 42
  entities:
    accounts:
      count: 20
    contacts:
      count: 20
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

## Anchor injection

The first record in every `data/default/{app}/{entity}.json` file uses IDs that match the `SAMPLE_PARAMS` values defined in the route configuration. This guarantees that detail-page URLs in nav items resolve to a real record in the default set.

Example: if `SAMPLE_PARAMS` defines `id: "001"`, then `accounts.json` record at index 0 will have `"id": "001"`.

## Single-app seeding

The `--app` flag restricts generation to one app:

```text
uv run python -m src.data_gen --app salesforce --set default
```

## Hybrid provider

Combines static records and generated fields.

```yaml
provider: hybrid
static: data/default/salesforce/accounts.json
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
