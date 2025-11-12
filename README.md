# MCP State Server

An MCP (Model Context Protocol) server for conversation and preference persistence using Databricks Lakehouse Postgres. This server provides tools for managing conversations, messages, and user preferences that can be used by AI assistants and other MCP clients.

## Table of Contents

- [MCP State Server](#mcp-state-server)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Step 1: Create a Databricks Service Principal](#step-1-create-a-databricks-service-principal)
    - [Option A: Using Databricks UI](#option-a-using-databricks-ui)
    - [Option B: Using Databricks CLI](#option-b-using-databricks-cli)
  - [Step 2: Create a Lakehouse Postgres Instance](#step-2-create-a-lakehouse-postgres-instance)
    - [Option A: Using Databricks UI](#option-a-using-databricks-ui-1)
    - [Option B: Using Databricks CLI](#option-b-using-databricks-cli-1)
  - [Step 3: Store Secrets in Databricks Secret Scope](#step-3-store-secrets-in-databricks-secret-scope)
    - [Create a Secret Scope](#create-a-secret-scope)
    - [Store Secrets](#store-secrets)
  - [Step 4: Install Dependencies](#step-4-install-dependencies)
    - [Using uv (Recommended)](#using-uv-recommended)
    - [Using pip](#using-pip)
  - [Step 5: Configure Environment Variables](#step-5-configure-environment-variables)
    - [Create .env File](#create-env-file)
    - [Edit .env File](#edit-env-file)
  - [Step 6: Run Locally](#step-6-run-locally)
    - [Start the Server](#start-the-server)
    - [Verify Server is Running](#verify-server-is-running)
  - [Step 7: Deploy as Databricks App](#step-7-deploy-as-databricks-app)
    - [Update databricks.yml (if needed)](#update-databricksyml-if-needed)
    - [Deploy Using Databricks Asset Bundles](#deploy-using-databricks-asset-bundles)
    - [Verify Deployment](#verify-deployment)
  - [Step 8: Test the Server](#step-8-test-the-server)
    - [Test Health Endpoint](#test-health-endpoint)
    - [Test MCP Tools (Using MCP Client)](#test-mcp-tools-using-mcp-client)
    - [Test Using Python](#test-using-python)
  - [Troubleshooting](#troubleshooting)
    - [Server Won't Start Locally](#server-wont-start-locally)
    - [Database Connection Fails](#database-connection-fails)
    - [App Deployment Fails](#app-deployment-fails)
    - ["Role does not exist" Error](#role-does-not-exist-error)
    - [Secret Scope Not Found](#secret-scope-not-found)
  - [Additional Resources](#additional-resources)
  - [Support](#support)

## Prerequisites

Before you begin, ensure you have:

- A Databricks workspace (Azure, AWS, or GCP)
- Databricks CLI installed and configured (`databricks --version`)
- Python 3.12 or higher (`python3 --version`)
- `uv` package manager installed (`uv --version`) - [Installation guide](https://github.com/astral-sh/uv)
- Access to create service principals, databases, and secrets in your Databricks workspace

## Step 1: Create a Databricks Service Principal

A service principal is a non-human identity that can be used to authenticate applications. This is required for the MCP server to authenticate with Databricks.

### Option A: Using Databricks UI

1. Log into your Databricks workspace
2. Go to **Settings** → **Identity and Access** → **Service Principals**
3. Click **Add Service Principal**
4. Enter a name (e.g., `mcp-state-server-sp`)
5. Click **Add**
6. **Important**: Copy the **Application ID** (Client ID) - you'll need this later
7. Click **Generate Token** or **Add Secret** to create a client secret
8. **Important**: Copy the **Client Secret** immediately - you won't be able to see it again

### Option B: Using Databricks CLI

```bash
# Create the service principal
databricks service-principals create \
  --display-name "mcp-state-server-sp" \
  --output JSON > sp_info.json

# Extract the application ID (Client ID)
CLIENT_ID=$(cat sp_info.json | jq -r '.applicationId')
echo "Client ID: $CLIENT_ID"

# Generate a client secret (valid for 100 days by default)
databricks service-principals create-secret \
  --service-principal-id "$CLIENT_ID" \
  --output JSON > sp_secret.json

# Extract the secret value
CLIENT_SECRET=$(cat sp_secret.json | jq -r '.secret')
echo "Client Secret: $CLIENT_SECRET"

# Save these values - you'll need them in Step 3
```

**Replace these values:**
- `mcp-state-server-sp` - Use your preferred service principal name
- `100` - Adjust token expiration days as needed

## Step 2: Create a Lakehouse Postgres Instance

Lakehouse Postgres is Databricks' managed PostgreSQL service. You'll create an instance to store conversation and preference data.

### Option A: Using Databricks UI

1. Log into your Databricks workspace
2. Go to **SQL** → **Lakehouse Postgres**
3. Click **Create Instance**
4. Fill in the details:
   - **Instance Name**: `mcp-state-server-pg` (or your preferred name)
   - **Capacity**: Choose based on your needs (e.g., `Small` for development)
   - **Region**: Select your preferred region
5. Click **Create**
6. Wait for the instance to be created (status will show as "Available")
7. **Important**: Note the instance name - you'll need it in Step 5

### Option B: Using Databricks CLI

```bash
# Create a Lakehouse Postgres instance
databricks database-instances create \
  --instance-name "mcp-state-server-pg" \
  --capacity "SMALL" \
  --region "us-east-1" \
  --output JSON > instance_info.json

# Check instance status
INSTANCE_NAME="mcp-state-server-pg"
databricks database-instances get \
  --instance-name "$INSTANCE_NAME" \
  --output JSON | jq '.state'

# Wait until state is "AVAILABLE" (may take a few minutes)
```

**Replace these values:**
- `mcp-state-server-pg` - Use your preferred instance name
- `SMALL` - Options: `SMALL`, `MEDIUM`, `LARGE`, `XLARGE`
- `us-east-1` - Use your Databricks region (e.g., `westus2` for Azure, `us-west-2` for AWS)

## Step 3: Store Secrets in Databricks Secret Scope

Secrets are securely stored credentials that the Databricks App can access. You'll create a secret scope and store your service principal credentials.

### Create a Secret Scope

```bash
# Create a secret scope (if it doesn't exist)
databricks secrets create-scope \
  --scope "retail_consumer_goods" \
  --initial-manage-principal "users"

# Or use an existing scope - replace "retail_consumer_goods" with your scope name
```

**Replace this value:**
- `retail_consumer_goods` - Use your preferred secret scope name (must match `databricks.yml`)

### Store Secrets

```bash
# Set your Databricks workspace host
# For Azure: https://adb-<workspace-id>.<deployment>.azuredatabricks.net
# For AWS: https://<workspace-id>.cloud.databricks.com
# For GCP: https://<workspace-id>.gcp.databricks.com
LAKEBASE_HOST="https://adb-1234567890123456.7.azuredatabricks.net"

# Use the Client ID and Secret from Step 1
LAKEBASE_CLIENT_ID="your-client-id-from-step-1"
LAKEBASE_CLIENT_SECRET="your-client-secret-from-step-1"

# Store the secrets
databricks secrets put \
  --scope "retail_consumer_goods" \
  --key "RETAIL_AI_DATABRICKS_HOST" \
  --string-value "$LAKEBASE_HOST"

databricks secrets put \
  --scope "retail_consumer_goods" \
  --key "RETAIL_AI_DATABRICKS_CLIENT_ID" \
  --string-value "$LAKEBASE_CLIENT_ID"

databricks secrets put \
  --scope "retail_consumer_goods" \
  --key "RETAIL_AI_DATABRICKS_CLIENT_SECRET" \
  --string-value "$LAKEBASE_CLIENT_SECRET"

# Verify secrets are stored
databricks secrets list --scope "retail_consumer_goods"
```

**Replace these values:**
- `retail_consumer_goods` - Must match the scope name in `databricks.yml`
- `LAKEBASE_HOST` - Your Databricks workspace URL (e.g., `https://adb-1234567890123456.7.azuredatabricks.net`)
- `LAKEBASE_CLIENT_ID` - The Application ID from Step 1 (UUID format, e.g., `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- `LAKEBASE_CLIENT_SECRET` - The Client Secret from Step 1 (keep this secure - never commit to version control!)

**Note**: If you use a different secret scope name, update `databricks.yml` to match:
```yaml
# In databricks.yml, update these lines:
scope: retail_consumer_goods  # Change to your scope name
```

## Step 4: Install Dependencies

Install Python dependencies using `uv` (recommended) or `pip`.

### Using uv (Recommended)

```bash
# Navigate to the project directory
cd /path/to/mcp_state_server

# Install dependencies
uv sync

# Verify installation
uv run python -c "import mcp_state_server; print('✓ Installation successful')"
```

### Using pip

```bash
# Navigate to the project directory
cd /path/to/mcp_state_server

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import mcp_state_server; print('✓ Installation successful')"
```

## Step 5: Configure Environment Variables

Create a `.env` file in the project root with your configuration.

### Create .env File

```bash
# Copy the example (if it exists) or create a new file
cp .env.example .env  # If example exists
# OR
touch .env  # Create new file
```

### Edit .env File

Open `.env` in a text editor and add the following:

```bash
# Databricks Workspace Configuration (for service principal authentication)
LAKEBASE_HOST=https://adb-1234567890123456.7.azuredatabricks.net
LAKEBASE_CLIENT_ID=your-client-id-from-step-1
LAKEBASE_CLIENT_SECRET=your-client-secret-from-step-1

# Lakehouse Postgres Instance
LAKEBASE_INSTANCE_NAME=your-instance-name-from-step-2
DATABRICKS_POSTGRES_INSTANCE_NAME=your-instance-name-from-step-2

# Alternative: Direct PostgreSQL Connection (for local testing)
# PGHOST=localhost
# PGPORT=5432
# PGDATABASE=databricks_postgres
# PGUSER=postgres
# PGPASSWORD=your-password

# Logging
LOG_LEVEL=DEBUG
```

**Replace these values:**
- `LAKEBASE_HOST` - Your Databricks workspace URL from Step 3 (e.g., `https://adb-1234567890123456.7.azuredatabricks.net`)
- `LAKEBASE_CLIENT_ID` - The Application ID (Client ID) from Step 1 (UUID format, e.g., `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- `LAKEBASE_CLIENT_SECRET` - The Client Secret from Step 1 (keep this secure - never commit to version control!)
- `LAKEBASE_INSTANCE_NAME` - The instance name from Step 2 (e.g., `mcp-state-server-pg`)
- `DATABRICKS_POSTGRES_INSTANCE_NAME` - Same as LAKEBASE_INSTANCE_NAME

**For local testing** (optional):
- If you have a local PostgreSQL instance, uncomment and configure the `PGHOST`, `PGPORT`, etc. lines
- Set `use_databricks_auth=False` in your test configuration

## Step 6: Run Locally

Test the server locally before deploying.

### Start the Server

```bash
# Using uv
uv run python main.py

# OR using the entry point
uv run mcp-state-server

# OR with custom port
uv run mcp-state-server --port 8080

# OR using python directly
python main.py --port 8000
```

### Verify Server is Running

Open a new terminal and test the server:

```bash
# Check health endpoint
curl http://localhost:8000/

# Expected response:
# {"message":"MCP State Server is running","status":"healthy","description":"MCP server for conversation and preference persistence"}
```

The server should start on `http://localhost:8000` by default.

## Step 7: Deploy as Databricks App

Deploy the MCP server as a Databricks App so it can be accessed by users in your workspace.

### Update databricks.yml (if needed)

If you used a different secret scope name in Step 3, update `databricks.yml`:

```yaml
# In databricks.yml, update the scope name:
scope: your-secret-scope-name  # Change from "retail_consumer_goods" if different
```

### Deploy Using Databricks Asset Bundles

```bash
# Validate the bundle configuration
databricks bundle validate

# Deploy the app
databricks bundle deploy \
  --var lakebase_instance_name="mcp-state-server-pg"

# Check deployment status
databricks apps list
```

**Replace this value:**
- `mcp-state-server-pg` - Your instance name from Step 2

### Verify Deployment

```bash
# List deployed apps
databricks apps list

# Get app details
databricks apps get --app-name "mcp-state-server"

# Get app URL
databricks apps get --app-name "mcp-state-server" --output JSON | jq -r '.url'
```

The app URL will be in the format: `https://mcp-state-server-<workspace-id>.<deployment>.databricksapps.com`

## Step 8: Test the Server

Test the deployed MCP server to ensure it's working correctly.

### Test Health Endpoint

```bash
# Replace <app-url> with your actual app URL from Step 7
APP_URL="https://mcp-state-server-1234567890123456.11.azure.databricksapps.com"

# Test health endpoint
curl "$APP_URL/"

# Expected response:
# {"message":"MCP State Server is running","status":"healthy",...}
```

### Test MCP Tools (Using MCP Client)

If you have an MCP client configured:

```bash
# Connect to the MCP server
# The server URL is: <app-url>/messages-sse

# Example using MCP CLI (if installed)
mcp connect sse "$APP_URL/messages-sse" \
  --auth "Bearer $DATABRICKS_TOKEN"

# List available tools
mcp list-tools
```

### Test Using Python

```python
import httpx
from mcp.client.sse import sse_client
from mcp import ClientSession

# Replace with your app URL
app_url = "https://mcp-state-server-1234567890123456.11.azure.databricksapps.com"
sse_url = f"{app_url}/messages-sse"

# Get Databricks token
import os
token = os.getenv("DATABRICKS_TOKEN")  # Set this in your environment

# Create auth header
auth = httpx.BasicAuth(token, "")

# Connect and test
async with sse_client(sse_url, auth=auth) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        
        # List tools
        tools = await session.list_tools()
        print(f"Available tools: {[t.name for t in tools.tools]}")
        
        # Test health tool
        result = await session.call_tool("health", arguments={})
        print(f"Health check: {result.content[0].text}")
```

## Troubleshooting

### Server Won't Start Locally

**Problem**: `ModuleNotFoundError` or import errors

**Solution**:
```bash
# Ensure dependencies are installed
uv sync

# Or with pip
pip install -r requirements.txt
```

### Database Connection Fails

**Problem**: `psycopg2.OperationalError` or authentication errors

**Solutions**:
1. Verify your `.env` file has correct values:
   ```bash
   # Check environment variables are set
   cat .env | grep -E "(LAKEBASE|DATABRICKS|PG)"
   ```

2. Verify service principal has access:
   ```bash
   # Test service principal authentication
   databricks service-principals get --service-principal-id "$CLIENT_ID"
   ```

3. Verify Lakehouse Postgres instance is available:
   ```bash
   databricks database-instances get \
     --instance-name "mcp-state-server-pg" \
     --output JSON | jq '.state'
   # Should be "AVAILABLE"
   ```

### App Deployment Fails

**Problem**: `Error: failed to update app` or resource errors

**Solutions**:
1. Verify secrets exist:
   ```bash
   databricks secrets list --scope "retail_consumer_goods"
   ```

2. Verify instance name matches:
   ```bash
   # Check instance exists
   databricks database-instances get \
     --instance-name "mcp-state-server-pg"
   ```

3. Check bundle validation:
   ```bash
   databricks bundle validate
   ```

### "Role does not exist" Error

**Problem**: `FATAL: role "..." does not exist`

**Solution**: The service principal's Application ID is being used as the PostgreSQL role, which may not exist. Ensure:
- The service principal has proper permissions
- The instance allows service principal connections
- Consider using a different authentication method for local testing

### Secret Scope Not Found

**Problem**: `Error: Secret scope 'retail_consumer_goods' not found`

**Solution**:
1. Create the secret scope (see Step 3)
2. Or update `databricks.yml` to use an existing scope name

## Additional Resources

- [Databricks Lakehouse Postgres Documentation](https://docs.databricks.com/en/sql/lakehouse-postgres/index.html)
- [Databricks Service Principals Guide](https://docs.databricks.com/en/dev-tools/auth/service-principals.html)
- [Databricks Apps Documentation](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review Databricks documentation links above
3. Check server logs: `LOG_LEVEL=DEBUG` in `.env` for detailed logging
