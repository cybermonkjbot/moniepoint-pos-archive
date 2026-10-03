# Moniepoint client authentication

Reviewed 3 October 2026 for the ERPNext `moniepoint_pos` integration. Scope is the public client-ID/client-secret contract and environment hosts. No credentials, screenshots or site configuration were read. No authentication, credential provisioning or transaction requests were sent.

## Conclusion

The legacy JSON exchange at `POST /v1/auth` is documented. An exact, explicitly labelled sandbox/production host pair is **not established** by the reviewed official pages. `expiresIn` units are also unspecified. Keep this authentication mode separate from the modern API-key mode, and leave environment selection and expiry conversion unresolved until an official contract supplies those details. [S1, S2, S3]

## Request and response

S2 specifies `POST {base_url}/v1/auth`, no Authorization header, and `Content-Type: application/json`. Both fields below are required strings. The placeholders are not credentials. [S2]

```json
{
  "clientId": "<client-id>",
  "clientSecret": "<client-secret>"
}
```

This is a JSON body, not HTTP Basic authentication or a form-encoded `grant_type=client_credentials` request. Neither a grant field nor a requested scope appears in the documented request. [S2]

| Response field | Documented shape and interpretation |
| --- | --- |
| `accessToken` | String. Use its value in `Authorization: Bearer <accessToken>` for subsequent API calls. [S2] |
| `tokenType` | The success example contains an object, `{"value":"bearer"}`, not a string. Read `tokenType.value`; do not insert or stringify the whole object in the header. This shape is example-backed, not a formal response schema. [S2] |
| `expiresIn` | Numeric example `8699`. The accompanying note identifies it as expiry information, but defines no unit, reference time or fixed lifetime. Seconds, milliseconds and an absolute timestamp cannot be established from this page. A relative lifetime is an interpretation of the name, not a verified provider contract. [S2] |
| `scope`, `jti` | Present in the success example. Neither is documented as an additional request input. [S2] |

Do not hard-code `8699` or implement token-cache timing from an assumed unit. No refresh-token endpoint or refresh procedure is specified in the reviewed authentication material. S1 explicitly says deleting a client invalidates tokens generated with that client's credentials. [S1, S2]

## Environment hosts

S1 requires choosing an environment when creating a client and names Sandbox for setup/testing, but supplies no base URLs. S2's "Moniepoint Environments" section contains one unlabelled base-URL line. Its visible text concatenates to `https://channel.moniepoint.com`, while the two adjacent links have different targets. Both storage and rendered HTML returned by the wiki API preserve this mismatch. [S1, S2]

| Exact URL in official material | Evidence and limit |
| --- | --- |
| `https://channel.moniepoint.com` | Visible base-URL text in S2. Not explicitly labelled production or sandbox. [S2] |
| `https://moniepoint-pos-backend-service.development.moniepoint.com` | Target of the link whose visible text is only `https://` in that same line. The hostname alone does not establish the sandbox client-auth base URL. [S2] |
| `http://channel.moniepoint.com` | Target of the adjacent `channel.moniepoint.com` link. Its HTTP scheme conflicts with the combined visible HTTPS text; do not send credentials over HTTP. [S2] |
| `https://posapi.development.moniepoint.com` | Explicit base URL for API-key introspection in S3. S3 documents `Authorization: Bearer <API_KEY>` and `authMethod: API_KEY`, not a client-secret exchange at `/v1/auth`. It does not establish a legacy sandbox host. [S3] |

The exact public documented **sandbox client-auth base URL remains unknown**. An explicitly confirmed **production client-auth base URL also remains unknown**; S2 supplies the unlabelled channel address above, not an environment mapping. Do not substitute a modern API-key host or derive hosts by renaming subdomains. [S1, S2, S3]

Following S2's host links with unauthenticated HEAD requests yielded HTTP 403 responses on 3 October 2026, not further documentation or an environment mapping. Host reachability does not confirm `/v1/auth` support. No `/v1/auth` or other API endpoint probes were made.

## ERPNext action

The request serializer and nested token-type handling can follow S2. Before enabling client-secret authentication, require non-secret official documentation that explicitly pairs HTTPS sandbox/production bases with `/v1/auth` and defines `expiresIn` units and reference time. Do not configure environment defaults or token expiry calculations from the unresolved examples. This is an implementation recommendation based on the gaps above, not an additional Moniepoint guarantee. [S1, S2, S3]

## Official sources

All pages were retrieved anonymously through the TeamApt wiki API on 3 October 2026. Dates below are the page-version timestamps returned by that API.

- S1. [API Client Credentials](https://teamapt.atlassian.net/wiki/spaces/EI/pages/1042120729/API+Client+Credentials), page 1042120729, version 8, updated 15 May 2025. [Storage API](https://teamapt.atlassian.net/wiki/api/v2/pages/1042120729?body-format=storage).
- S2. [Push Payment Request (API Reference)](https://teamapt.atlassian.net/wiki/spaces/EI/pages/1039826999/Push+Payment+Request+API+Reference), page 1039826999, version 20, updated 22 January 2025. [Storage API](https://teamapt.atlassian.net/wiki/api/v2/pages/1039826999?body-format=storage) and [rendered HTML API](https://teamapt.atlassian.net/wiki/api/v2/pages/1039826999?body-format=view). Relevant sections are "Moniepoint Environments", "Authentication" and "Generate Access token".
- S3. [POS as a Platform Documentation](https://teamapt.atlassian.net/wiki/spaces/EI/pages/1892974728/POS+as+a+Platform+Documentation), page 1892974728, version 1, updated 13 February 2025. [Storage API](https://teamapt.atlassian.net/wiki/api/v2/pages/1892974728?body-format=storage). Relevant sections are "Authentication Overview" and "Key Introspection API". No merchant console, key introspection or secret-management endpoint was called.
