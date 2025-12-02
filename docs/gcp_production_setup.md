# GCP Production Infrastructure Setup

This checklist stitches together the resources needed to run Gaia on Google Cloud
Run with Cloud SQL and Cloud Storage. Follow the sections in order; each one
builds on the previous step.

---

## 0. Prerequisites

- Google Cloud project with billing enabled.
- `gcloud` CLI >= 458 and `gsutil` installed.
- Terraform/OpenTofu is optional; commands below use `gcloud`/`gsutil`.
- An OpenTofu starter configuration is available at `infra/opentofu/gcp` if you prefer IaC.
- Local tooling: Docker, Node 18+, Python 3.11+, Mozilla SOPS (`brew install sops`),
  OpenSSL, jq.

Quick install (macOS or Debian/Ubuntu):

```bash
bash scripts/setup/install_prereqs.sh
```

> **Identity model**
> - Runtime: `gaia-backend-sa` (Cloud Run).
> - CI/CD: `gaia-deployer-sa` (GitHub Actions or OIDC).
> - Manual ops: human users with `roles/editor` or scoped roles.

---

## 1. Key Management (SOPS + KMS or age)

Option A — Cloud KMS (recommended for team/enterprise; ~$3/month/key)

1. Enable required APIs:
   ```bash
   gcloud services enable cloudkms.googleapis.com iam.googleapis.com
   ```
2. Create a key ring and key (example names):
   ```bash
   gcloud kms keyrings create gaia-secrets \
     --location=global

   gcloud kms keys create gaia-secrets-key \
     --location=global \
     --keyring=gaia-secrets \
     --purpose=encryption
   ```
3. Grant users and the deployer service account encrypt/decrypt rights:
   ```bash
   gcloud kms keys add-iam-policy-binding gaia-secrets-key \
     --location=global \
     --keyring=gaia-secrets \
     --member="user:<you@example.com>" \
     --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"

   gcloud kms keys add-iam-policy-binding gaia-secrets-key \
     --location=global \
     --keyring=gaia-secrets \
     --member="serviceAccount:gaia-deployer-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
     --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"
   ```
4. Configure `.sops.yaml` in the repo root (or update the existing one) to point at
   the KMS key. Example:
   ```yaml
   creation_rules:
     - encrypted_regex: '^(PROJECT_ID|REGION|.*_KEY|.*_SECRET|DB_.*)$'
       gcp_kms:
         - projects/${PROJECT_ID}/locations/global/keyRings/gaia-secrets/cryptoKeys/gaia-secrets-key
   ```
5. Encrypt `secrets/.secrets.env`:
   ```bash
   sops --encrypt --in-place secrets/.secrets.env
   ```
   To edit later: `sops secrets/.secrets.env`.

Option B — SOPS with age (no GCP KMS cost)

1. Install age: macOS `brew install age`, Ubuntu `sudo apt-get install age`.
2. Generate a keypair on each editor machine:
   ```bash
   age-keygen -o ~/.config/sops/age/keys.txt
   ```
3. Add the public key(s) to `.sops.yaml`:
   ```yaml
   creation_rules:
     - encrypted_regex: '^(PROJECT_ID|REGION|.*_KEY|.*_SECRET|DB_.*)$'
       age: ["age1...publickey1", "age1...publickey2"]
   ```
4. Encrypt and edit with SOPS as usual. Rotate recipients if someone leaves.

---

## 2. Service Accounts & IAM

### Runtime (Cloud Run)
```bash
gcloud iam service-accounts create gaia-backend-sa \
  --display-name="Gaia Cloud Run runtime"
```
Assign roles:
```bash
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:gaia-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:gaia-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.reader"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:gaia-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:gaia-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```
Add `roles/secretmanager.secretAccessor` once secrets are migrated.

> Secrets best practices
> - Prefer Cloud Run secret env vars or volumes so secrets are injected at container startup (no per-request API calls).
> - If you need programmatic fetches, enable the backend's startup cache. See `docs/SECRETS.md`.

### CI/CD (GitHub Actions)
```bash
gcloud iam service-accounts create gaia-deployer-sa \
  --display-name="Gaia CI/CD deployer"
```
Grant deployment roles:
```bash
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountTokenCreator; do
  gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:gaia-deployer-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="${role}"
done
```
Export a key (short-lived) or configure workload identity federation for GitHub
Actions (preferred).

---

## 3. Artifact Registry

1. Enable the API: `gcloud services enable artifactregistry.googleapis.com`.
2. Create a Docker repository:
   ```bash
   gcloud artifacts repositories create gaia-backend \
     --repository-format=docker \
     --location=${REGION} \
     --description="Gaia backend images"
   ```
3. Authenticate locally: `gcloud auth configure-docker ${REGION}-docker.pkg.dev`.
4. Update `secrets/.secrets.env` with `ARTIFACT_REGISTRY_REPO=${REGION}-docker.pkg.dev/${PROJECT_ID}/gaia-backend`.

---

## 4. Cloud Storage (Campaign Data & Media)

### 4.1 Bucket Layout

| Purpose            | Suggested Bucket                                |
|--------------------|-------------------------------------------------|
| Campaign storage   | `gs://gaia-campaigns-${ENV}`                    |
| Generated media    | `gs://gaia-media-${ENV}`                        |
| Database backups   | `gs://gaia-db-backups-${ENV}`                  |
| Frontend artifacts | `gs://gaia-frontend-${ENV}` (if using CDN)      |

Keep `ENV` as `stg`, `prod`, etc.

### 4.2 Create Buckets

```bash
for env in stg prod; do
  gsutil mb -l ${REGION} -p ${PROJECT_ID} gs://gaia-campaigns-${env}/
  gsutil mb -l ${REGION} -p ${PROJECT_ID} gs://gaia-media-${env}/
done
```

Recommended settings:
```bash
# Uniform bucket-level access
gsutil uniformbucketlevelaccess set on gs://gaia-campaigns-prod

# Object versioning (optional but useful for accidental deletes)
gsutil versioning set on gs://gaia-campaigns-prod

# Default storage class (optional): nearline for older backups
gsutil defstorageclass set STANDARD gs://gaia-campaigns-prod
```

Assign IAM to the runtime service account:
```bash
for bucket in gaia-campaigns-stg gaia-campaigns-prod gaia-media-stg gaia-media-prod; do
  gsutil iam ch serviceAccount:gaia-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com:roles/storage.objectAdmin gs://${bucket}
done
```

Document the bucket names in `secrets/.secrets.env`:
```bash
CAMPAIGN_STORAGE_BUCKET=gaia-campaigns-prod
MEDIA_BUCKET=gaia-media-prod
CAMPAIGN_STORAGE_PATH=/mnt/campaigns  # Cloud Run volume mount point
```

### 4.3 Cloud Run Volume Mount

Use Cloud Run’s Cloud Storage FUSE integration (beta):
```bash
gcloud run deploy gaia-backend \
  --image=${IMAGE} \
  --add-cloud-storage-volume=name=campaigns,bucket=gaia-campaigns-prod \
  --set-cloud-storage-mount=volume=campaigns,mount-path=/mnt/campaigns \
  ...
```

Alternatively, rely on `gsutil`/`gcloud storage` API calls in code (stateless) if
mounts are unnecessary.

### 4.4 Pre-Generated Content Storage

The system pre-generates campaigns and characters during Cloud Run container startup. This content must persist in GCS:

**Storage Paths:**
```
gs://gaia-campaigns-stg/campaigns/stg/pregenerated/campaigns.json
gs://gaia-campaigns-stg/campaigns/stg/pregenerated/characters.json
gs://gaia-campaigns-prod/campaigns/prod/pregenerated/campaigns.json
gs://gaia-campaigns-prod/campaigns/prod/pregenerated/characters.json
```

**Environment Variables:**
- `CAMPAIGN_STORAGE_BACKEND=auto` - Auto-enables GCS when running on Cloud Run
- `CAMPAIGN_STORAGE_BUCKET=gaia-campaigns-prod` - GCS bucket name
- `CAMPAIGN_STORAGE_PATH=/tmp/campaigns` - Local ephemeral cache
- `PARASAIL_API_KEY` - Required for pre-generation (store in Secret Manager)
- `ENV=prod` or `ENVIRONMENT=production` - **Required for correct image storage paths**
- `IMAGE_STORAGE_BUCKET=gaia-media-prod` - GCS bucket for images

**Image Storage Configuration:**
Images (portraits, scenes) require proper environment detection to store correctly:
- **Production/Staging**: Must set `ENV=prod`, `ENVIRONMENT_NAME=prod`, or `ENVIRONMENT=production`
- **Without these**: Images will incorrectly use hostname prefix (`localhost/campaign_XX/...`)
- **Result**: 404 errors after container restarts

The system checks three environment variables in order:
1. `ENV` (preferred) - Set in `config/cloudrun.prod.env` and `config/cloudrun.stg.env`
2. `ENVIRONMENT_NAME` - Alternative production indicator
3. `ENVIRONMENT` - Legacy variable for backward compatibility

See `backend/CLAUDE.md` Image Artifact Storage section for detailed documentation.

**Pre-Generation Behavior:**
- Non-blocking by default - deployment succeeds even if generation fails
- Checks GCS first before attempting generation
- Uses Parasail-only model fallback chain (kimi → deepseek → qwen)
- Can force regeneration with `--force-pregen` deployment flag

See `backend/CLAUDE.md` for detailed pre-generation documentation.

### 4.5 Frontend Hosting (Optional)

1. Build locally: `npm run build`.
2. Sync to the frontend bucket:
   ```bash
   gsutil -m rsync -r frontend/dist gs://gaia-frontend-prod
   ```
3. Enable static website hosting or place Cloud CDN + HTTPS Load Balancer in front
   of the bucket (see Google Cloud documentation for full setup).

---

## 5. Cloud SQL (Production PostgreSQL)

See `docs/POSTGRESQL_SETUP.md#production-deployment-cloud-sql` for the full
playbook. Checklist:
- Instance: `gcloud sql instances create gaia-prod-db ...`
- Create `gaia_app` user and `gaia` database.
- Store credentials in SOPS / Secret Manager.
- Attach Cloud Run with `--add-cloudsql-instances`.
- Run Alembic migrations via Cloud Run job or Cloud Build step.
- Enable automated backups and export schedule.

---

## 6. Cloud Run Services

### 6.1 Enable APIs
```bash
gcloud services enable run.googleapis.com compute.googleapis.com vpcaccess.googleapis.com
```

### 6.2 Staging Deploy (Spot)
```bash
IMAGE=${REGION}-docker.pkg.dev/${PROJECT_ID}/gaia-backend:${TAG}

gcloud run deploy gaia-backend-stg \
  --image=${IMAGE} \
  --region=${REGION} \
  --service-account=gaia-backend-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --concurrency=1 \
  --min-instances=0 \
  --max-instances=2 \
  --cpu=1 \
  --memory=2Gi \
  --execution-environment=gen2 \
  --ingress=all \
  --set-env-vars-file=runtime-env-vars-stg.txt \
  --add-cloudsql-instances=${DB_INSTANCE_CONNECTION_NAME} \
  --labels=env=stg,tier=backend
```
Add `--launch-stage=ALPHA --template-revision=spot` once spot revisions reach GA
in your region (currently `--execution-environment=gen2` with `min-instances=0`
achieves similar cost behaviour).

### 6.3 Production Deploy
- Increase `--max-instances`.
- Attach Cloud Storage mounts (`--add-cloud-storage-volume`).
- Use production env-vars file.
- Map a custom domain: `gcloud run domain-mappings create --service gaia-backend-prod --domain api.example.com`.

---

## 7. GitHub Actions / CI Pipeline

1. Configure workload identity federation (recommended) or store a service account
   key (`GCP_SA_KEY_B64`) in GitHub secrets.
2. Update `.github/workflows/deploy-cloud-run.yml` or the matrix variant `.github/workflows/deploy-cloudrun-matrix.yml` to:
   - Authenticate to GCP (OIDC or key).
   - Decrypt `secrets/.secrets.env` using SOPS (age).
   - Sync secrets to Secret Manager with `scripts/cloud_run/sync_secrets_to_sm.py` (use `--prune-keep 5` to cap versions; default skips unchanged values).
   - Use non-sensitive env files committed under `config/` (e.g., `config/cloudrun.stg.env`) with `--set-env-vars-file` and attach secrets with `--set-secrets`.
   - Run backend tests (`python run_tests.py --markers "not slow"`).
   - Build Docker image with `backend/Dockerfile.cloudrun` and push to Artifact Registry.
   - Deploy to staging (auto) and production (manual approval step).
   - For multi-service deploys, use the matrix workflow which builds and deploys `backend`, `frontend`, `stt`, and `tts` in parallel. It reads per-service env files from `config/cloudrun.<service>.<env>.env` and uses `config/gcp.env` for shared values (buckets, paths, service names).

> Note: Grant `roles/secretmanager.secretAccessor` to the Cloud Run runtime service account. If using OpenTofu, set `grant_secret_manager_accessor=true`.
3. Store API keys and sensitive config only in the encrypted secrets file. Keep non-sensitive
   deployments settings in `config/gcp.env` and per-env Cloud Run files in `config/cloudrun.<env>.env`.

---

## 8. Monitoring, Logging, and Alerts

1. Enable Cloud Monitoring & Logging dashboards:
   ```bash
   gcloud services enable monitoring.googleapis.com logging.googleapis.com
   ```
2. Create dashboards for:
   - Cloud Run request latency & error rate.
   - Cloud SQL CPU/storage/connections.
   - Cloud Storage operation counts (optional).
3. Set alerting policies (SLO-style) for 5xx rate, DB CPU > 80%, low free storage.
4. Wire Sentry/New Relic/etc. via environment variables if already licensed.
5. Configure budgets:
   ```bash
   gcloud alpha billing budgets create --display-name="Gaia Prod Budget" ...
   ```

---

## 9. Data Migration & Validation

1. Export existing campaign data from the current environment.
2. Upload to `gaia-campaigns-prod` using `gsutil -m cp`.
3. Seed Cloud SQL using Alembic migrations + data import (psql or `gcloud sql import csv`).
4. Run the manual smoke test checklist:
   - Auth0 login flow.
   - Campaign creation, join, and playback.
   - Multi-session concurrency.
   - Audio playback from Cloud Storage.
   - Monitoring alerts behave as expected.

---

## 10. Go-Live Playbook

1. Confirm staging and production revisions match the expected container digest.
2. Freeze manual deploys; merge the release branch.
3. Trigger GitHub Actions workflow, approve production step.
4. Validate `/api/health`, manual sessions, and DB logs.
5. Announce cutover complete; update on-call runbook.
6. Schedule the next key rotation & backup verification.

---

With these resources provisioned, Gaia runs stateless on Cloud Run, persists data
in Cloud SQL, stores artifacts in Cloud Storage, and can be managed through a
repeatable CI/CD pipeline. Keep this document in sync with infrastructure changes
to maintain operational clarity.
