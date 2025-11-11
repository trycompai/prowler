# Prowler API Render Deployment - Summary

## What Was Done

Three key files were created/modified to enable Render deployment:

### 1. ✅ Fixed `api/Dockerfile`
**Location:** `/api/Dockerfile`

**Change:** Added dummy AWS credentials before `poetry install` to prevent import-time errors:
```dockerfile
ENV AWS_ACCESS_KEY_ID=dummy_build_key \
    AWS_SECRET_ACCESS_KEY=dummy_build_secret \
    AWS_DEFAULT_REGION=us-east-1
```

**Why:** Prowler's AWS provider imports boto3 modules that look for credentials. These dummy values prevent build failures.

### 2. ✅ Created `render.yaml`
**Location:** `/render.yaml` (repo root)

**What:** Blueprint defining 5 services:
- `prowler-api` - Web service (Django REST API)
- `prowler-worker` - Background worker (Celery)
- `prowler-beat` - Scheduler (Celery Beat)
- `prowler-db` - PostgreSQL database
- `prowler-redis` - Redis cache/queue

**Why:** Automates deployment - just push to GitHub and connect to Render.

### 3. ✅ Created `RENDER_DEPLOYMENT.md`
**Location:** `/RENDER_DEPLOYMENT.md` (repo root)

**What:** Complete deployment guide including:
- Step-by-step deployment instructions
- All environment variables with generation commands
- Complete API usage guide with cURL examples
- Multi-tenant workflow explanation
- Troubleshooting section

---

## Quick Start - Deploy to Render

### 1. Commit Changes
```bash
git add api/Dockerfile render.yaml RENDER_DEPLOYMENT.md
git commit -m "feat: add Render deployment configuration"
git push origin main
```

### 2. Deploy on Render
1. Go to https://dashboard.render.com
2. Click **New** → **Blueprint**
3. Connect your GitHub repo
4. Select the `prowler` repository
5. Click **Apply**

### 3. Wait for Build (~10-15 min)
Render will:
- Build the Docker image
- Create PostgreSQL database
- Create Redis instance
- Deploy 3 services (API, worker, beat)

### 4. Initialize Database
Once deployed, open Shell for `prowler-api`:
```bash
poetry run python manage.py migrate --database admin
poetry run python manage.py createsuperuser --database admin
```

### 5. Test API
Visit: `https://prowler-api-XXXX.onrender.com/api/v1/docs`

---

## How Your App Will Use It

### Flow
```
Your App → Prowler API → Celery Queue → Worker → Prowler CLI → AWS
                  ↓
            PostgreSQL (Results)
                  ↓
Your App ← GET /api/v1/findings
```

### Example Integration

```javascript
// 1. Create organization
const createOrg = async (orgName) => {
  const response = await fetch('https://prowler-api-XXXX.onrender.com/api/v1/tenants', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/vnd.api+json'
    },
    body: JSON.stringify({
      data: {
        type: 'tenants',
        attributes: { name: orgName }
      }
    })
  });
  return await response.json();
};

// 2. Add AWS credentials for org
const addAWSProvider = async (tenantId, awsAccessKey, awsSecretKey) => {
  const response = await fetch('https://prowler-api-XXXX.onrender.com/api/v1/providers', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Tenant-ID': tenantId,
      'Content-Type': 'application/vnd.api+json'
    },
    body: JSON.stringify({
      data: {
        type: 'providers',
        attributes: {
          provider: 'aws',
          secret: {
            aws_access_key_id: awsAccessKey,
            aws_secret_access_key: awsSecretKey
          }
        }
      }
    })
  });
  return await response.json();
};

// 3. Trigger scan
const triggerScan = async (tenantId, providerId) => {
  const response = await fetch('https://prowler-api-XXXX.onrender.com/api/v1/scans', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Tenant-ID': tenantId,
      'Content-Type': 'application/vnd.api+json'
    },
    body: JSON.stringify({
      data: {
        type: 'scans',
        attributes: {
          provider: providerId
        }
      }
    })
  });
  return await response.json();
};

// 4. Poll for results
const checkScanStatus = async (tenantId, taskId) => {
  const response = await fetch(
    `https://prowler-api-XXXX.onrender.com/api/v1/tasks/${taskId}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Tenant-ID': tenantId
      }
    }
  );
  return await response.json();
};

// 5. Get findings
const getFindings = async (tenantId, scanId) => {
  const response = await fetch(
    `https://prowler-api-XXXX.onrender.com/api/v1/findings?filter[scan]=${scanId}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Tenant-ID': tenantId
      }
    }
  );
  return await response.json();
};
```

---

## Key Features

✅ **Multi-tenant** - Each organization has isolated data and credentials
✅ **Async Scans** - Scans run in background via Celery
✅ **Encrypted Credentials** - AWS keys encrypted at rest using Fernet
✅ **Auto-scaling** - Add more workers as needed
✅ **REST API** - Standard JSON:API format
✅ **Production Ready** - Includes migrations, health checks, monitoring

---

## Important Notes

1. **Credentials Storage**: AWS credentials are encrypted in PostgreSQL, never in code or environment variables
2. **Tenant Isolation**: Each API call requires `X-Tenant-ID` header for data isolation
3. **JWT Auth**: All requests need Bearer token (except login/register)
4. **Async Processing**: Scans can take 5-30 minutes depending on AWS account size
5. **Worker Required**: The `prowler-worker` service MUST be running for scans to process

---

## Next Steps

1. Deploy using the instructions above
2. Test with cURL examples in `RENDER_DEPLOYMENT.md`
3. Integrate with your external app using the example code above
4. Monitor logs in Render dashboard
5. Scale workers as needed for performance

For detailed information, see **RENDER_DEPLOYMENT.md**.

