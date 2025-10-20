# Delegated Authentication Mode

## Overview

Delegated authentication mode allows the MCP server to operate behind an upstream proxy (like Pomerium) that handles Box OAuth authentication. This enables multi-tenant scenarios where each user authenticates with their own Box credentials.

## Architecture

```
[MCP Client] → [Pomerium Proxy] → [MCP Server] → [Box API]
                     ↓
             Handles Box OAuth
             for each user
```

**Token Flow:**
1. User authenticates with Pomerium
2. Pomerium performs Box OAuth flow for that user
3. Pomerium forwards requests to MCP server with `Authorization: Bearer <box_access_token>`
4. MCP server creates a Box client per-request using that token
5. Box API calls are made with the user's credentials

## Configuration

### 1. Start MCP Server in Delegated Mode

```bash
uv run src/mcp_server_box.py \
  --transport sse \
  --host 127.0.0.1 \
  --port 8001 \
  --box-auth delegated
```

**Key differences from OAuth/CCG mode:**
- No `BOX_CLIENT_ID`, `BOX_CLIENT_SECRET`, or `BOX_REDIRECT_URL` needed
- No `BOX_MCP_SERVER_AUTH_TOKEN` needed (Pomerium sends Box token)
- Server must use HTTP transport (sse or streamable-http), not stdio
- Box client is created per-request, not at startup

### 2. Configure Pomerium

```yaml
routes:
  - from: https://box-mcp.your-domain.com
    to: http://127.0.0.1:8001
    name: Box MCP Server
    mcp:
      server:
        upstream_oauth2:
          client_id: YOUR_BOX_CLIENT_ID
          client_secret: YOUR_BOX_CLIENT_SECRET
          scopes: 
            - root_readwrite  # Or appropriate scopes for your use case
          endpoint:
            auth_url: 'https://account.box.com/api/oauth2/authorize'
            token_url: 'https://api.box.com/oauth2/token'
    policy:
      allow:
        and:
          - domain:
              is: your-domain.com
```

### 3. Box App Configuration

In the Box Developer Console, configure your Box app:
- **Application Type:** Custom App
- **Authentication Method:** Standard OAuth 2.0
- **Redirect URI:** Set to your Pomerium callback URL
- **Application Scopes:** Grant appropriate permissions
- **CORS Domains:** Add your domain if needed

## Testing Without Pomerium

For local testing without Pomerium, you can manually pass a Box access token:

```bash
# Start the server
uv run src/mcp_server_box.py \
  --transport sse \
  --host 127.0.0.1 \
  --port 8001 \
  --box-auth delegated

# Make a request with your Box token
curl -X POST http://127.0.0.1:8001/tools/call \
  -H "Authorization: Bearer YOUR_BOX_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "box_who_am_i",
    "arguments": {}
  }'
```

To get a Box access token for testing:
1. Use the Box OAuth 2.0 flow manually
2. Or use a tool like Postman to complete OAuth
3. Or create a temporary token in Box Developer Console (for testing only)

## Benefits

1. **Multi-Tenant:** Each user operates with their own Box credentials
2. **Simplified Server:** No OAuth flow management in MCP server
3. **Better Security:** Tokens never stored server-side
4. **User Isolation:** Each user only accesses their Box content
5. **Centralized Auth:** Pomerium handles authentication and authorization policies

## Comparison with Other Modes

| Feature | OAuth Mode | CCG Mode | Delegated Mode |
|---------|-----------|----------|----------------|
| **Authentication Location** | MCP Server | MCP Server | Upstream Proxy |
| **Token Management** | Server-side | Server-side | Per-request |
| **Multi-Tenant** | No | No | Yes |
| **Box Identity** | Single user | Service account | Per user |
| **Requires Proxy** | No | No | Yes |
| **STDIO Support** | Yes | Yes | No |

## Troubleshooting

### "Box client is not initialized"
- Ensure you're passing the `Authorization: Bearer <token>` header
- Verify the server is started with `--box-auth delegated`
- Check that the token is a valid Box OAuth access token

### "Missing authorization header"
- The upstream proxy must forward the token in the `Authorization` header
- Verify Pomerium is configured with `upstream_oauth2`

### Token expired errors
- Pomerium should handle token refresh automatically
- If using manual testing, generate a fresh token

## Security Considerations

1. **Use HTTPS:** Always use TLS in production
2. **Token Validation:** Consider adding token validation/verification
3. **Rate Limiting:** Implement rate limiting at proxy level
4. **Monitoring:** Log authentication attempts and failures
5. **Token Expiry:** Pomerium handles refresh, but monitor for issues

