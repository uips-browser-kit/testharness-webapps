# Variant Model

## Purpose

Define how controlled instability and runtime differences are modeled across enterprise application mimics.

Variants allow automation developers to test behavior under realistic but deterministic changes.

## Scope

Owns:

- UI instability variants
- navigation behavior variants
- data visibility variants
- latency variants
- error variants
- authentication state signals

Does not own:

- OAuth/OIDC flows
- token issuance
- browser automation behavior
- production fault injection

## Concepts

### Variant

A named runtime modification applied to an application, route, page, or response.

### Variant group

A category of related variants.

Example:

```text
selector
layout
latency
auth
data
error
````

### Active variant

The variant selected for a request.

### Deterministic variant

A variant selected predictably using configuration, seed, header, or query parameter.

## Requirements

### R1

The system shall support variants configured outside core code.

### R2

The system shall support variants at application level.

### R3

The system shall support variants at route level.

### R4

The system shall support variants at page level.

### R5

The system shall allow variants to be activated by headers.

Example:

```text
X-Harness-Variant: unstable-selectors
```

### R6

The system shall allow variants to be activated by configuration.

### R7

The system shall allow deterministic variant selection using seeds.

### R8

The system shall record active variants in metrics.

### R9

The system shall not change canonical route identity when a variant is active.

### R10

The system shall reject unknown variants.

### R11

The system shall allow multiple compatible variants to be active together.

### R12

The system shall reject incompatible variant combinations.

## Variant types

### Selector variant

Changes element identifiers, classes, labels, or DOM attributes.

Example:

```text
stable selector → unstable selector
```

### Layout variant

Changes visible arrangement while preserving route identity.

Example:

```text
table layout → card layout
```

### Latency variant

Adds deterministic response delay.

Example:

```text
500ms delay
```

### Error variant

Returns configured error responses.

Example:

```text
HTTP 500
HTTP 503
empty result
```

### Data variant

Changes available or visible synthetic records.

Example:

```text
full dataset
partial dataset
empty dataset
```

### Auth signal variant

Simulates authentication-related application behavior.

Example:

```text
session expired screen
access denied page
role restricted content
```

OAuth/OIDC remains owned by Fake IdP.

## Data model

### Variant

```yaml
id: unstable-selectors
group: selector
scope:
  app: salesforce
  routes:
    - account-detail
compatible_with:
  - latency-500
  - partial-data
incompatible_with:
  - stable-selectors
effects:
  selectors:
    mode: randomized
```

### Active variant context

```yaml
request_id: req-001
app: salesforce
environment: dev
route: account-detail
variants:
  - unstable-selectors
  - latency-500
seed: 12345
```

## Behavior

### Selection order

Variant selection should use this priority:

```text
1. explicit request header
2. explicit query parameter
3. environment configuration
4. app default
5. platform default
```

### Request processing

Input:

```text
GET /lightning/r/Account/001/view
X-Harness-Variant: unstable-selectors
```

Processing:

```text
identify route
load compatible variants
validate requested variant
apply variant context
render modified page
record metrics
```

Output:

```text
Rendered account detail page with unstable selectors
```

## Configuration example

```yaml
variants:
  - id: unstable-selectors
    group: selector
    description: Changes DOM attributes and generated IDs.
    scope:
      apps:
        - salesforce
      routes:
        - account-detail
    activation:
      headers:
        - X-Harness-Variant
    effects:
      selectors:
        mode: randomized
        seed_required: true
```

## Examples

### Header-selected variant

```text
X-Harness-Variant: unstable-selectors
```

Result:

```text
Page renders with changed selectors.
```

### Config-selected variant

```yaml
environments:
  dev:
    default_variants:
      - latency-500
```

Result:

```text
All dev requests include 500ms latency.
```

### Incompatible variants

```text
stable-selectors
unstable-selectors
```

Result:

```text
400 incompatible variants
```

## Metrics

Each request metric shall include:

```yaml
request_id: req-001
app: salesforce
environment: dev
route: account-detail
variants:
  - unstable-selectors
duration_ms: 142
status_code: 200
```

## Non-goals

* Random uncontrolled failures
* Production-grade chaos engineering
* Authentication protocol simulation
* Browser automation implementation
* Vendor-perfect UI reproduction
