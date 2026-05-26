# App Profile Specification

## Purpose

Define the contract for a mimicked enterprise application.

An app profile describes how an enterprise system behaves without requiring changes to core logic.

The app profile is the primary input model for:

- URL generation
- route resolution
- page rendering
- environment behavior
- variants
- templates
- synthetic data

## Scope

Owns:

- application identity
- URL patterns
- routes
- environments
- pages
- templates
- data sources
- variants
- extension metadata

Does not own:

- OAuth/OIDC behavior
- Docker configuration
- Caddy configuration
- hosts file configuration
- CLI behavior

---

## Concepts

### App

A mimicked enterprise system.

Examples:

```text
salesforce
dynamics
servicenow
sap
jira
sharepoint
````

---

### Environment

A deployment target.

Examples:

```text
dev
test
prod
```

---

### Route

A named navigation target.

Examples:

```text
account-detail
incident-list
sales-order
dashboard
```

---

### Page

A rendered view associated with a route.

Examples:

```text
account-page
dashboard-page
ticket-page
```

---

### Template

Reusable HTML layout for rendering a page.

---

### Data provider

Source for synthetic or static data.

Examples:

```text
yaml
json
faker
hybrid
```

---

### Variant

Controlled instability behavior.

Examples:

```text
unstable-selectors
latency-500
empty-data
```

---

## Requirements

### R1

The system shall define applications through configuration.

### R2

The system shall support multiple environments.

### R3

The system shall support multiple routes.

### R4

The system shall support page-template mapping.

### R5

The system shall support data providers.

### R6

The system shall support variants.

### R7

The system shall support deterministic synthetic data.

### R8

The system shall support custom enterprise-hosted URL patterns.

### R9

The system shall support extension-specific metadata.

### R10

Adding a new application shall require no core changes.

---

## Data model

### Application definition

```yaml
id: salesforce
name: Salesforce Mimic

vendor: Salesforce

product: Lightning

description: CRM enterprise mimic

environments:

  dev:
    host: sf-dev.local
    base_path: /

  test:
    host: sf-test.local
    base_path: /sf

routes:

  - id: account-detail
    path: /lightning/r/Account/{id}/view
    methods:
      - GET
    page: account-page

  - id: dashboard
    path: /lightning/page/home
    methods:
      - GET
    page: dashboard-page

pages:

  account-page:
    template: account.html
    layout: default

  dashboard-page:
    template: dashboard.html
    layout: dashboard

data:

  provider: faker

  seed: 12345

variants:

  - unstable-selectors
  - latency-500

metadata:

  icon: salesforce.svg
  tags:
    - crm
    - sales
```

---

## URL patterns

Applications may define multiple URL shapes.

Example:

Public cloud:

```text
https://org.lightning.force.com/lightning
```

Extended:

```text
https://org.lightning.force.com/lightning/r/Account/{RecordId}/view
```

Enterprise-hosted:

```text
https://crm.company.com/lightning/r/Account/{RecordId}/view
```

---

## Route behavior

Input:

```yaml
route: account-detail

parameters:
  id: "001"
```

Processing:

```text
load environment
load route
resolve parameters
apply variant context
load template
load data
render page
```

Output:

```text
http://sf-dev.local/lightning/r/Account/001/view
```

---

## Extension model

Applications should be independently deployable.

Example:

```text
extensions/

    salesforce/
        templates/
        data/
        app.yaml

    dynamics/
        templates/
        data/
        app.yaml
```

---

## Examples

### Salesforce

```yaml
id: salesforce

vendor: Salesforce

product: Lightning

routes:

  - id: account-detail
    path: /lightning/r/Account/{id}/view
```

### ServiceNow

```yaml
id: servicenow

vendor: ServiceNow

product: Workspace

routes:

  - id: incident
    path: /now/workspace/agent/record/incident/{id}
```

### SAP

```yaml
id: sap

vendor: SAP

product: Fiori

routes:

  - id: sales-order
    path: /sap/bc/ui5_ui5/ui2/ushell
```

---

## Validation rules

Required:

```text
id
vendor
product
environment
route
page
template
```

Unique:

```text
application id
route id
page id
```

Reject:

```text
missing templates
duplicate routes
unknown variants
invalid parameters
```

---

## URL resolution

Input:

```yaml
app: salesforce
environment: dev
route: account-detail
parameters:
  id: "001"
query:
  tab: details
```

Processing:

```text
load app
load environment
apply base_path
load route
validate required parameters
substitute path parameters
append query string
produce complete URL
```

Output:

```text
http://sf-dev.local/lightning/r/Account/001/view?tab=details
```

Environment difference example:

```text
dev:   http://sf-dev.local/lightning/r/Account/001/view
test:  http://sf-test.local/sf/lightning/r/Account/001/view
```

---

## Non-goals

* reproducing full vendor products
* defining OAuth behavior
* defining Docker runtime
* defining Caddy routing
* implementing browser automation
