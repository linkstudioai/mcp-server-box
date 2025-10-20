# Box MCP Server

## Quick Start

### Clone the repository:

```sh
git clone https://github.com/box-community/mcp-server-box.git
cd mcp-server-box
```

### Optional but recommended `uv` installation for virtual environment and dependency management:

#### Homebrew (macOS)
```sh
brew install uv
```

#### WinGet (Windows)
```sh
winget install --id=astral-sh.uv  -e
```

#### On macOS and Linux
```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### On Windows
```sh
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Set up the virtual environment and install dependencies:

```sh
uv sync
```

### Set environment variables:
Set the following environment variables for Box authentication in a `.env` file or your system environment:

#### Using OAuth2.0 with a Box App
```
BOX_CLIENT_ID = YOUR_CLIENT_ID
BOX_CLIENT_SECRET = YOUR_CLIENT_SECRET
BOX_REDIRECT_URL = http://localhost:8000/callback

BOX_MCP_SERVER_AUTH_TOKEN = YOUR_BOX_MCP_SERVER_AUTH_TOKEN
```

#### Using CCG with a Box App
```
BOX_CLIENT_ID = YOUR_CLIENT_ID
BOX_CLIENT_SECRET = YOUR_CLIENT_SECRET
BOX_SUBJECT_TYPE = user_or_enterprise
BOX_SUBJECT_ID = YOUR_USER_OR_ENTERPRISE_ID

BOX_MCP_SERVER_AUTH_TOKEN = YOUR_BOX_MCP_SERVER_AUTH_TOKEN
```

#### Using Delegated Authentication (with Pomerium or similar proxy)
When running behind an upstream proxy (like Pomerium) that handles Box OAuth:
```
# No Box credentials needed - the proxy handles OAuth
# The proxy sends the Box access token as the Authorization Bearer token
```

> Note: The `BOX_MCP_SERVER_AUTH_TOKEN` is the token used to authenticate requests to the Box MCP server. You can generate this token. In delegated mode, this token is not used - the proxy sends the Box OAuth token directly.

### Run the MCP server in STDIO mode:
```sh
uv run src/mcp_server_box.py
```

## Box Community MCP Server Tools

Below is a summary of the available tools:

| Tools available          | Description                                      |
|--------------------------|--------------------------------------------------|
| [box_tools_ai](docs/box_tools_ai.md) | AI-powered file and hub queries                  |
| [box_tools_collaboration](docs/box_tools_collaboration.md)  | Manage file/folder collaborations                |
| [box_tools_docgen](docs/box_tools_docgen.md)         | Document generation and template management      |
| [box_tools_files](docs/box_tools_files.md)          | File operations (read, upload, download)         |
| [box_tools_folders](docs/box_tools_folders.md)        | Folder operations (list, create, delete, update) |
| [box_tools_generic](docs/box_tools_generic.md)        | Generic Box API utilities                        |
| [box_tools_groups](docs/box_tools_groups.md)         | Group management and queries                     |
| [box_tools_metadata](docs/box_tools_metadata.md)       | Metadata template and instance management        |
| [box_tools_search](docs/box_tools_search.md)         | Search files and folders                         |
| [box_tools_shared_links](docs/box_tools_shared_links.md)   | Shared link management for files/folders/web-links|
| [box_tools_users](docs/box_tools_users.md)          | User management and queries                      |
| [box_tools_web_link](docs/box_tools_web_link.md)       | Web link creation and management                 |

## Box Community MCP Server Operations Details

### Command line interface parameters
To run the MCP server with specific configurations, you can use the following command line parameters:
```sh
uv run src/mcp_server_box.py --help
```
```
usage: mcp_server_box.py [-h] [--transport {stdio,sse,streamable-http}] [--host HOST]
                         [--port PORT] [--box-auth {oauth,ccg,delegated}] [--no-mcp-server-auth]

Box Community MCP Server

options:
  -h, --help            show this help message and exit
  --transport {stdio,sse,streamable-http}
                        Transport type (default: stdio)
  --host HOST           Host for SSE/HTTP transport (default: 0.0.0.0)
  --port PORT           Port for SSE/HTTP transport (default: 8000)
  --box-auth {oauth,ccg,delegated}
                        Authentication type for Box API (default: oauth)
                        - oauth: Server handles OAuth flow on port 8000
                        - ccg: Server uses Client Credentials Grant
                        - delegated: Upstream proxy (e.g., Pomerium) handles OAuth
  --no-mcp-server-auth  Disable authentication (for development only)
  ```

### Claude Desktop Configuration
Edit your `claude_desktop_config.json`:

```code ~/Library/Application\ Support/Claude/claude_desktop_config.json```

Add the configuration:
```json
{
    "mcpServers": {
        "mcp-server-box": {
            "command": "uv",
            "args": [
                "--directory",
                "/path/to/mcp-server-box",
                "run",
                "src/mcp_server_box.py"
            ]
        }
    }
}
```

Restart Claude if it is running.

### Cursor Configuration

Cursor supports MCP servers through its configuration file. Here's how to set it up:

The Cursor MCP configuration file is located at:
- **macOS/Linux**: `~/.cursor/config.json` or `~/.config/cursor/config.json`
- **Windows**: `%APPDATA%\Cursor\config.json`

#### Add the MCP Server Configuration: STDIO Transport

Edit your Cursor configuration file and add the following under the `mcpServers` section:
```json
{
    "mcpServers": {
        "mcp-server-box": {
            "command": "uv",
            "args": [
                "--directory",
                "/path/to/mcp-server-box",
                "run",
                "src/mcp_server_box.py"
            ],
            "env": {
                "BOX_CLIENT_ID": "YOUR_CLIENT_ID",
                "BOX_CLIENT_SECRET": "YOUR_CLIENT_SECRET",
                "BOX_REDIRECT_URL": "http://localhost:8000/callback"
            }
        }
    }
}
```

### Pomerium Configuration (Delegated Auth Mode)

For production deployments with multiple users, you can use Pomerium to handle Box OAuth authentication:

#### Start the MCP Server in Delegated Mode

```sh
uv run src/mcp_server_box.py \
  --transport sse \
  --host 127.0.0.1 \
  --port 8001 \
  --box-auth delegated
```

#### Configure Pomerium Route

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
            - root_readwrite  # Adjust based on your needs
          endpoint:
            auth_url: 'https://account.box.com/api/oauth2/authorize'
            token_url: 'https://api.box.com/oauth2/token'
    policy:
      allow:
        and:
          - domain:
              is: your-domain.com
```

**How it works:**
1. Pomerium handles the Box OAuth flow for each user
2. Pomerium sends the user's Box access token as `Authorization: Bearer <token>` to the MCP server
3. The MCP server creates a Box client per-request using that token
4. Each user operates on Box with their own credentials and permissions