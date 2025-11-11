# Prowler API - Render Deployment Guide

This guide walks you through deploying the Prowler Django REST API to Render. The API enables multi-tenant cloud security scanning where each organization can have its own AWS credentials and trigger scans via REST endpoints.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Deployment Steps](#deployment-steps)
4. [Environment Variables](#environment-variables)
5. [Post-Deployment Setup](#post-deployment-setup)
6. [API Usage Guide](#api-usage-guide)
7. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The deployment consists of **5 services**:

1. **prowler-api** (Web Service) - Django REST API server
2. **prowler-worker** (Background Worker) - Celery worker that processes scan jobs
3. **prowler-beat** (Background Worker) - Celery beat scheduler for recurring scans
4. **prowler-db** (PostgreSQL) - Managed database for storing tenants, providers, scans, and findings
5. **prowler-redis** (Redis) - Message broker and cache for Celery tasks

### How it Works

```
Your App → POST /api/v1/scans → prowler-api → Celery Queue (Redis)
                                       ↓
                              prowler-worker picks up job
                                       ↓
                          Executes Prowler CLI with org credentials
                                       ↓
                          Stores findings in PostgreSQL
                                       ↓
Your App → GET /api/v1/findings ← Returns scan results
```

---

## Prerequisites

Before deploying:

1. **GitHub Account** - Your Prowler repo must be on GitHub
2. **Render Account** - Sign up at [render.com](https://render.com)
3. **Git Push** - Ensure `render.yaml` and updated `api/Dockerfile` are committed

---

## Deployment Steps

### Option A: Deploy via Render Blueprint (Recommended)

1. **Push Code to GitHub**
   ```bash
   git add render.yaml api/Dockerfile
   git commit -m "feat: add Render deployment configuration"
   git push origin main
   ```

2. **Connect to Render**
   - Go to [render.com/dashboard](https://dashboard.render.com/)
   - Click **New** → **Blueprint**
   - Connect your GitHub account and select the `prowler` repository
   - Render will automatically detect `render.yaml`

3. **Review & Deploy**
   - Review the 5 services that will be created
   - Click **Apply**
   - Wait 10-15 minutes for initial build and deployment

4. **Get Your API URL**
   - Once deployed, find your API URL: `https://prowler-api-XXXX.onrender.com`

### Option B: Manual Deployment

If you prefer manual setup:

1. **Create PostgreSQL Database**
   - New → PostgreSQL
   - Name: `prowler-db`
   - Database: `prowler`
   - User: `prowler`
   - Plan: Starter or higher

2. **Create Redis Instance**
   - New → Redis
   - Name: `prowler-redis`
   - Plan: Starter or higher
   - Maxmemory Policy: `allkeys-lru`

3. **Create API Web Service**
   - New → Web Service
   - Connect repository: `prowler`
   - Name: `prowler-api`
   - Runtime: Docker
   - Dockerfile Path: `./api/Dockerfile`
   - Docker Context: `./api`
   - Add environment variables (see below)

4. **Create Worker Service**
   - New → Background Worker
   - Name: `prowler-worker`
   - Runtime: Docker
   - Docker Command: `/home/prowler/docker-entrypoint.sh worker`
   - Add same environment variables as API

5. **Create Beat Service**
   - New → Background Worker
   - Name: `prowler-beat`
   - Runtime: Docker
   - Docker Command: `/home/prowler/docker-entrypoint.sh beat`
   - Add same environment variables as API

---

## Environment Variables

All services need these environment variables. Most are auto-configured via `render.yaml`, but here's the complete reference:

### Required Environment Variables

#### Django Configuration

| Variable | Value | Notes |
|----------|-------|-------|
| `DJANGO_SETTINGS_MODULE` | `config.django.production` | Django settings module |
| `DJANGO_PORT` | `8080` | API server port |
| `DJANGO_DEBUG` | `false` | Set to false in production |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated list of allowed hosts |
| `SECRET_KEY` | *Generate* | See generation command below |
| `DJANGO_SECRETS_ENCRYPTION_KEY` | *Generate* | Fernet key for encrypting credentials |

#### Database Configuration

| Variable | Source | Notes |
|----------|--------|-------|
| `POSTGRES_ADMIN_USER` | From Render DB | Admin user for migrations |
| `POSTGRES_ADMIN_PASSWORD` | From Render DB | Admin password |
| `POSTGRES_DB` | From Render DB | Database name (`prowler`) |
| `POSTGRES_HOST` | From Render DB | Database hostname |
| `POSTGRES_PORT` | From Render DB | Database port (5432) |
| `POSTGRES_USER` | From Render DB | Same as admin for now |
| `POSTGRES_PASSWORD` | From Render DB | Same as admin for now |

#### Redis Configuration

| Variable | Source | Notes |
|----------|--------|-------|
| `VALKEY_HOST` | From Render Redis | Redis hostname |
| `VALKEY_PORT` | From Render Redis | Redis port (6379) |
| `VALKEY_DB` | `0` | Redis database number |

#### Build-Time AWS Credentials (Required)

These prevent import errors during Docker build. **NOT used at runtime.**

| Variable | Value |
|----------|-------|
| `AWS_ACCESS_KEY_ID` | `dummy_build_key` |
| `AWS_SECRET_ACCESS_KEY` | `dummy_build_secret` |
| `AWS_DEFAULT_REGION` | `us-east-1` |

### Generating Secret Keys

#### Django SECRET_KEY

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

#### Fernet Encryption Key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Or:

```bash
python3 -c "import secrets; import base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

**Important:** 
- Copy these values and add them to **ALL services** (API, worker, beat)
- The encryption key must be the same across all services
- Never commit these to version control

---

## Post-Deployment Setup

### 1. Run Database Migrations

After deployment, access the Render Shell for `prowler-api`:

```bash
# In Render Dashboard: prowler-api → Shell
poetry run python manage.py migrate --database admin
```

### 2. Create Superuser

```bash
poetry run python manage.py createsuperuser --database admin
```

Follow prompts to create admin credentials.

### 3. Verify Services

- **API Health Check**: `https://prowler-api-XXXX.onrender.com/api/v1/docs`
- **Check Logs**: Render Dashboard → Each service → Logs

All three services (API, worker, beat) should be running without errors.

---

## API Usage Guide

Your external app will interact with the Prowler API via REST endpoints.

### Base URL

```
https://prowler-api-XXXX.onrender.com
```

### API Documentation

Interactive API docs available at:
```
https://prowler-api-XXXX.onrender.com/api/v1/docs
```

### Authentication Flow

#### 1. Register/Login

**Register User:**
```bash
POST /api/v1/auth/register
Content-Type: application/vnd.api+json

{
  "email": "admin@example.com",
  "password": "SecurePassword123!",
  "password_confirm": "SecurePassword123!"
}
```

**Login:**
```bash
POST /api/v1/auth/login
Content-Type: application/vnd.api+json

{
  "email": "admin@example.com",
  "password": "SecurePassword123!"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

Save the `access` token for subsequent requests.

### Multi-Tenant Workflow

#### 2. Create Tenant (Organization)

```bash
POST /api/v1/tenants
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
Content-Type: application/vnd.api+json

{
  "data": {
    "type": "tenants",
    "attributes": {
      "name": "Acme Corporation"
    }
  }
}
```

**Response:**
```json
{
  "data": {
    "type": "tenants",
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "attributes": {
      "name": "Acme Corporation",
      "inserted_at": "2025-11-11T10:00:00Z"
    }
  }
}
```

Save the tenant `id` - this is your organization identifier.

#### 3. Add AWS Provider with Credentials

```bash
POST /api/v1/providers
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
X-Tenant-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
Content-Type: application/vnd.api+json

{
  "data": {
    "type": "providers",
    "attributes": {
      "provider": "aws",
      "alias": "Production AWS Account",
      "secret": {
        "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
      }
    }
  }
}
```

**Response:**
```json
{
  "data": {
    "type": "providers",
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "attributes": {
      "provider": "aws",
      "alias": "Production AWS Account",
      "connected": null,
      "connection_last_checked_at": null
    }
  }
}
```

**Important:** Credentials are encrypted in the database using Fernet encryption. They're never exposed in API responses.

#### 4. Trigger a Scan

```bash
POST /api/v1/scans
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
X-Tenant-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
Content-Type: application/vnd.api+json

{
  "data": {
    "type": "scans",
    "attributes": {
      "provider": "b2c3d4e5-f6a7-8901-bcde-f12345678901"
    }
  }
}
```

**Response (202 Accepted):**
```json
{
  "data": {
    "type": "tasks",
    "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "attributes": {
      "state": "PENDING",
      "task_name": "scan-perform"
    }
  }
}
```

The scan is now queued and will be processed by the Celery worker.

#### 5. Check Scan Status

```bash
GET /api/v1/tasks/c3d4e5f6-a7b8-9012-cdef-123456789012
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
X-Tenant-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response:**
```json
{
  "data": {
    "type": "tasks",
    "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "attributes": {
      "state": "EXECUTING",
      "progress": 45,
      "result": null
    }
  }
}
```

Possible states: `PENDING`, `EXECUTING`, `SUCCESS`, `FAILURE`

#### 6. List Scans

```bash
GET /api/v1/scans?filter[provider]=b2c3d4e5-f6a7-8901-bcde-f12345678901
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
X-Tenant-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

#### 7. Get Scan Findings

```bash
GET /api/v1/findings?filter[scan]=<scan-id>
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
X-Tenant-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response:**
```json
{
  "data": [
    {
      "type": "findings",
      "id": "finding-uuid",
      "attributes": {
        "uid": "prowler-aws-ec2_instance_public_ip-123456789012-us-east-1-i-1234567890abcdef0",
        "status": "FAIL",
        "status_extended": "EC2 Instance i-1234567890abcdef0 has a public IP address.",
        "severity": "medium",
        "check_id": "ec2_instance_public_ip",
        "service_name": "ec2",
        "region": "us-east-1"
      }
    }
  ],
  "meta": {
    "pagination": {
      "page": 1,
      "pages": 10,
      "count": 250
    }
  }
}
```

### Complete cURL Example

Here's a complete workflow using cURL:

```bash
# 1. Login
TOKEN=$(curl -X POST https://prowler-api-XXXX.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/vnd.api+json" \
  -d '{"email":"admin@example.com","password":"SecurePassword123!"}' \
  | jq -r '.access')

# 2. Create Tenant
TENANT_ID=$(curl -X POST https://prowler-api-XXXX.onrender.com/api/v1/tenants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/vnd.api+json" \
  -d '{"data":{"type":"tenants","attributes":{"name":"Acme Corp"}}}' \
  | jq -r '.data.id')

# 3. Add AWS Provider
PROVIDER_ID=$(curl -X POST https://prowler-api-XXXX.onrender.com/api/v1/providers \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "Content-Type: application/vnd.api+json" \
  -d '{
    "data": {
      "type": "providers",
      "attributes": {
        "provider": "aws",
        "secret": {
          "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
          "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        }
      }
    }
  }' | jq -r '.data.id')

# 4. Trigger Scan
TASK_ID=$(curl -X POST https://prowler-api-XXXX.onrender.com/api/v1/scans \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "Content-Type: application/vnd.api+json" \
  -d "{\"data\":{\"type\":\"scans\",\"attributes\":{\"provider\":\"$PROVIDER_ID\"}}}" \
  | jq -r '.data.id')

# 5. Check Status (poll until complete)
curl https://prowler-api-XXXX.onrender.com/api/v1/tasks/$TASK_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID"

# 6. Get Findings
curl "https://prowler-api-XXXX.onrender.com/api/v1/findings?filter[status]=FAIL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: $TENANT_ID"
```

---

## Troubleshooting

### Build Fails with "Unable to locate credentials"

**Cause:** Prowler tries to load AWS credentials during `poetry install`.

**Solution:** Ensure dummy AWS environment variables are set in Dockerfile and Render environment:
```
AWS_ACCESS_KEY_ID=dummy_build_key
AWS_SECRET_ACCESS_KEY=dummy_build_secret
AWS_DEFAULT_REGION=us-east-1
```

### Worker Not Processing Scans

**Check:**
1. Verify `prowler-worker` service is running in Render dashboard
2. Check worker logs for errors
3. Verify Redis connection in worker logs
4. Ensure all environment variables match between API and worker

### Database Migration Errors

If migrations fail, manually run:
```bash
# In Render Shell
poetry run python manage.py migrate --database admin --fake-initial
```

### Scan Fails with "Provider not connected"

**Check:**
1. Verify AWS credentials are valid
2. Check IAM permissions for the credentials
3. Review provider connection status via API:
   ```bash
   GET /api/v1/providers/{provider-id}
   ```

### SSL/HTTPS Issues

Render provides automatic HTTPS. Ensure:
- `SECURE_PROXY_SSL_HEADER` is set in Django settings (already configured)
- `USE_X_FORWARDED_HOST = True` (already configured)

### Performance Optimization

For better performance:
- Upgrade Render plans (Starter → Standard)
- Add read replicas for PostgreSQL
- Increase Redis memory
- Scale workers horizontally (add more worker instances)

---

## Security Best Practices

1. **Never commit secrets** - Use Render's environment variables
2. **Rotate encryption keys** periodically
3. **Use strong passwords** for superuser accounts
4. **Enable rate limiting** in production (configure in Django)
5. **Review IAM permissions** - Use least-privilege AWS credentials
6. **Monitor logs** regularly for suspicious activity
7. **Enable Render's IP allowlist** for Redis if possible

---

## Scaling Considerations

As your usage grows:

1. **Vertical Scaling**
   - Upgrade Render plans for more CPU/RAM
   - Use Standard or Pro plans for better performance

2. **Horizontal Scaling**
   - Add more worker instances (clone `prowler-worker` service)
   - Each worker processes scans independently

3. **Database Optimization**
   - Add read replicas (configure `POSTGRES_REPLICA_*` env vars)
   - Upgrade to PostgreSQL plans with more connections

4. **Caching**
   - Results are cached automatically via Django cache framework
   - Increase Redis memory for better cache hit rates

---

## Support

- **Prowler Documentation**: https://docs.prowler.com
- **API Documentation**: Your deployed API at `/api/v1/docs`
- **Render Support**: https://render.com/docs
- **GitHub Issues**: https://github.com/prowler-cloud/prowler/issues

---

## Next Steps

After successful deployment:

1. ✅ Test the API with the cURL examples above
2. ✅ Integrate with your external application
3. ✅ Set up monitoring and alerting
4. ✅ Configure scheduled scans if needed
5. ✅ Review and optimize IAM permissions

Happy scanning! 🚀

