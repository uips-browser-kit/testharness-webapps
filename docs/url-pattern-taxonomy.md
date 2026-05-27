# Enterprise URL Pattern Taxonomy

Reference table of URL pattern types encountered in enterprise environments.

Used to classify app profiles in the catalog and inform routing and matching design decisions.

## Web application routing

| Pattern | Minimal form | Typical use | Server-visible |
|---------|-------------|-------------|----------------|
| Traditional path routing | `https://app.com/products/123` | Websites, REST-style apps | Yes |
| Query parameter routing | `https://app.com?page=orders&id=123` | Legacy web apps, Dynamics | Yes |
| Single-page application (SPA) | `https://app.com/orders/123` | React, Angular, Vue | Yes — path only |
| Hash routing | `https://app.com/#/orders/123` | Older SPAs, SAP Fiori navigation | No — hash not sent to server |
| Deep link with state | `https://app.com/open?id=123` | Mobile and workflow apps | Yes |

## Enterprise SaaS

| Pattern | Minimal form | Typical use | Server-visible |
|---------|-------------|-------------|----------------|
| Canvas App | `https://apps.powerapps.com/play/{AppId}` | Power Apps | Yes |
| Model-driven App | `https://org.crm.dynamics.com/main.aspx?appid={AppId}&pagetype=entityrecord&id={RecordId}` | Dynamics 365, Dataverse | Yes |
| SharePoint-style | `https://tenant.sharepoint.com/sites/{SiteName}` | Collaboration platforms | Yes |
| Embedded application | `https://portal.company.com/apps/{AppSlug}` | Enterprise portals, intranet | Yes |

## API and services

| Pattern | Minimal form | Typical use | Server-visible |
|---------|-------------|-------------|----------------|
| REST API endpoint | `https://api.company.com/v1/orders/123` | Service APIs | Yes |
| Graph-style API | `https://graph.company.com/users/123` | Entity relationship APIs | Yes |
| Microservice gateway | `https://gateway.company.com/orders/123` | API gateways | Yes |

## Authentication flows

| Pattern | Minimal form | Typical use | Server-visible |
|---------|-------------|-------------|----------------|
| SSO redirect | `https://login.company.com/auth` | SAML, OIDC entry point | Yes |
| OAuth callback | `https://app.com/callback?code={Code}&state={State}` | OAuth 2.0 authorization code | Yes |

## Protocol handlers

| Pattern | Minimal form | Typical use | Server-visible |
|---------|-------------|-------------|----------------|
| Desktop launch URL | `myapp://open/123` | Native apps, Citrix | No — OS-handled |
| Custom protocol | `teams://chat` | Teams, Outlook integrations | No — OS-handled |

## Content and BI

| Pattern | Minimal form | Typical use | Server-visible |
|---------|-------------|-------------|----------------|
| Report / dashboard | `https://reports.company.com/report/{ReportId}` | BI platforms (Power BI, Tableau) | Yes |
| Document-based | `https://docs.company.com/doc/{DocId}` | Content management systems | Yes |

---

## Notes for harness design

**Hash routing (SAP Fiori, older SPAs):** The fragment (`#...`) is never sent to the server. The harness models the navigation intent as a query parameter on the server side. The hash form is documented in the catalog but cannot be matched server-side.

**Custom protocol and desktop launch URLs (`myapp://`, `teams://`):** Not HTTP — not handled by the harness. Out of scope.

**OAuth callback:** The harness does not implement the authorization server. Keycloak handles the callback. The harness may need to recognise the redirect URI pattern in config to avoid misrouting.

**Query-only navigation (Dynamics, Oracle):** Path is static; all record identity is in query params. The matcher must treat the path as fixed and extract identity from the query string.
