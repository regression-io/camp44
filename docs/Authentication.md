# Camp44 Authentication Documentation

Camp44 supports multiple authentication methods to secure your multi-tenant application:

1. **JWT-Based Authentication** - Traditional username/password authentication
2. **OAuth/OIDC Authentication** - Integration with external identity providers
3. **WebAuthn/Passkey Authentication** - Passwordless authentication using security keys and biometrics

## JWT-Based Authentication

The traditional authentication flow uses JWT tokens and remains available at the `/api/v1/auth/login` endpoint:

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=password"
```

This returns a JWT token that should be included in the `Authorization` header as a Bearer token for subsequent requests.

## OAuth/OIDC Authentication

OAuth/OIDC integration allows users to authenticate with external identity providers like Google, Microsoft, Auth0, etc. To enable OIDC:

1. Configure your OIDC settings in `.env`:

```dotenv
OAUTH_ENABLED=true
OIDC_ISSUER_URL=https://accounts.google.com
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_AUTHORIZATION_ENDPOINT=https://accounts.google.com/o/oauth2/auth
OIDC_TOKEN_ENDPOINT=https://oauth2.googleapis.com/token
OIDC_JWKS_URI=https://www.googleapis.com/oauth2/v3/certs
OIDC_USERINFO_ENDPOINT=https://openidconnect.googleapis.com/v1/userinfo
OIDC_TENANT_CLAIM=tenant_id
OIDC_CALLBACK_URL=http://localhost:8000/api/v1/auth/oidc/callback
```

2. Configure your identity provider to use your callback URL.

3. Implement the OIDC auth flow:
   - Redirect user to `/api/v1/auth/oidc/login` to initiate the flow
   - User authenticates with the provider
   - Provider redirects to your callback URL with an authorization code
   - The callback endpoint exchanges this code for tokens and creates/authenticates the user
   - User receives a JWT token for subsequent requests

### Tenant ID Extraction

Camp44 automatically extracts the tenant ID from the OIDC token claims and sets it in the database session for row-level security. The claim name is configurable via `OIDC_TENANT_CLAIM`.

## WebAuthn/Passkey Authentication

WebAuthn/Passkey enables passwordless authentication using platform authenticators (TouchID, FaceID, Windows Hello) or security keys (YubiKey, etc.).

### Configuration

Configure your WebAuthn settings in `.env`:

```dotenv
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=Camp44
WEBAUTHN_ORIGIN=http://localhost:8000
WEBAUTHN_TIMEOUT=60000
```

### Registration Flow

1. User must first authenticate using JWT or OIDC
2. Call `/api/v1/auth/passkey/register/options` to get registration options
3. Use these options with the WebAuthn browser API to create a credential
4. Submit the credential to `/api/v1/auth/passkey/register/verify`

Example client-side JavaScript for registration:

```javascript
// 1. Get registration options
const optionsResponse = await fetch('/api/v1/auth/passkey/register/options', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_JWT_TOKEN'
  },
  body: JSON.stringify({ user_id: 'user-uuid' })
});
const optionsData = await optionsResponse.json();

// 2. Create credential with WebAuthn API
const credential = await navigator.credentials.create({
  publicKey: {
    ...optionsData.options,
    challenge: base64URLToBuffer(optionsData.options.challenge),
    user: {
      ...optionsData.options.user,
      id: base64URLToBuffer(optionsData.options.user.id),
    },
    excludeCredentials: optionsData.options.excludeCredentials.map(cred => ({
      ...cred,
      id: base64URLToBuffer(cred.id),
    })),
  }
});

// 3. Verify credential with server
const verifyResponse = await fetch('/api/v1/auth/passkey/register/verify', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_JWT_TOKEN'
  },
  body: JSON.stringify({
    user_id: 'user-uuid',
    credential: {
      id: credential.id,
      rawId: bufferToBase64URL(credential.rawId),
      response: {
        attestationObject: bufferToBase64URL(credential.response.attestationObject),
        clientDataJSON: bufferToBase64URL(credential.response.clientDataJSON),
      },
      type: credential.type,
    }
  })
});
```

### Authentication Flow

1. Call `/api/v1/auth/passkey/authenticate/options` to get authentication options
2. Use these options with the WebAuthn browser API to get an assertion
3. Submit the assertion to `/api/v1/auth/passkey/authenticate/verify`
4. Receive a JWT token for subsequent requests

Example client-side JavaScript for authentication:

```javascript
// 1. Get authentication options
const optionsResponse = await fetch('/api/v1/auth/passkey/authenticate/options', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'user@example.com' })
});
const optionsData = await optionsResponse.json();

// 2. Get assertion with WebAuthn API
const assertion = await navigator.credentials.get({
  publicKey: {
    ...optionsData.options,
    challenge: base64URLToBuffer(optionsData.options.challenge),
    allowCredentials: optionsData.options.allowCredentials?.map(cred => ({
      ...cred,
      id: base64URLToBuffer(cred.id),
    })),
  }
});

// 3. Verify assertion with server
const verifyResponse = await fetch('/api/v1/auth/passkey/authenticate/verify', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    credential: {
      id: assertion.id,
      rawId: bufferToBase64URL(assertion.rawId),
      response: {
        authenticatorData: bufferToBase64URL(assertion.response.authenticatorData),
        clientDataJSON: bufferToBase64URL(assertion.response.clientDataJSON),
        signature: bufferToBase64URL(assertion.response.signature),
        userHandle: assertion.response.userHandle ? bufferToBase64URL(assertion.response.userHandle) : null,
      },
      type: assertion.type,
    },
    email: 'user@example.com'
  })
});

// 4. Get JWT token from response
const { access_token } = await verifyResponse.json();
```

## Security Considerations

1. **Token Security**: Store JWT tokens securely, preferably in HttpOnly cookies.
2. **TLS**: Always use HTTPS in production environments.
3. **CORS**: Restrict CORS settings to known domains in production.
4. **Token Expiry**: Set appropriate token expiration times.
5. **Passkey Storage**: WebAuthn credentials are stored securely by the platform authenticator.
