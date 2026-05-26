# Keycloak OIDC Reference

## Discovery

```text
GET http://idp.local/realms/harness/.well-known/openid-configuration
```

## Standard endpoints

All endpoints are under:

```text
http://idp.local/realms/harness/protocol/openid-connect/
```

### Authorize

```http
GET /realms/harness/protocol/openid-connect/auth
```

Query:

```text
client_id
redirect_uri
response_type=code
scope=openid
state
nonce
```

### Token

```http
POST /realms/harness/protocol/openid-connect/token
```

### User info

```http
GET /realms/harness/protocol/openid-connect/userinfo
```

### JWKS

```http
GET /realms/harness/protocol/openid-connect/certs
```

### Logout

```http
POST /realms/harness/protocol/openid-connect/logout
```

## Realm import

```http
POST /admin/realms
Authorization: Bearer <admin-token>
Content-Type: application/json
```

Body: realm export JSON from `infra/keycloak/harness-realm.json`

## Auth flows in use

| Flow | Use case |
|------|----------|
| Authorization Code | Browser automation, UiPath |
| Client Credentials | harness-api internal, CLI |

## Keycloak admin console

```text
http://idp.local/admin
```

Default dev credentials:

```text
admin / admin
```
