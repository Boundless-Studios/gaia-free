# Upload Pre-Generated Content Script

## Overview

The `upload_pregenerated_content.py` script allows you to upload pre-generated characters or campaigns files to the production or staging Google Cloud Storage buckets.

## Features

- **Replace Mode**: Completely replace existing content in GCS
- **Append Mode**: Merge new content with existing content (deduplicates by name/title)
- **Validation**: Validates JSON structure before upload
- **Multi-Environment**: Upload to prod, staging, or both
- **Dry Run**: Preview changes without uploading

## Prerequisites

1. **Google Cloud Authentication**: Configure one of the following:
   - Application Default Credentials (ADC): `gcloud auth application-default login`
   - Service account key: Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

2. **Required Environment Variables**:
   ```bash
   # Bucket names (default values shown)
   CAMPAIGN_STORAGE_BUCKET_PROD=gaia-campaigns-prod
   CAMPAIGN_STORAGE_BUCKET_STG=gaia-campaigns-stg
   ```

3. **Docker**: Script should be run inside the backend container to access dependencies

## Usage

### Basic Syntax

```bash
docker exec gaia-backend-dev python3 scripts/upload_pregenerated_content.py \
  --file <path-to-json> \
  --type <characters|campaigns> \
  --env <prod|stg|both> \
  --mode <replace|append> \
  [--dry-run]
```

### Examples

#### 1. Replace All Characters in Production

```bash
docker exec gaia-backend-dev python3 scripts/upload_pregenerated_content.py \
  --file ./campaign_storage/pregenerated/characters.json \
  --type characters \
  --env prod \
  --mode replace
```

#### 2. Add New Campaigns to Staging (Append Mode)

```bash
docker exec gaia-backend-dev python3 scripts/upload_pregenerated_content.py \
  --file ./new_campaigns.json \
  --type campaigns \
  --env stg \
  --mode append
```

#### 3. Upload to Both Environments

```bash
docker exec gaia-backend-dev python3 scripts/upload_pregenerated_content.py \
  --file ./characters.json \
  --type characters \
  --env both \
  --mode replace
```

#### 4. Dry Run (Preview Without Uploading)

```bash
docker exec gaia-backend-dev python3 scripts/upload_pregenerated_content.py \
  --file ./characters.json \
  --type characters \
  --env prod \
  --mode append \
  --dry-run
```

## Arguments

| Argument | Required | Values | Description |
|----------|----------|--------|-------------|
| `--file` | Yes | Path | Path to the JSON file to upload |
| `--type` | Yes | `characters`, `campaigns` | Content type |
| `--env` | Yes | `prod`, `stg`, `both` | Target environment |
| `--mode` | No | `replace`, `append` | Upload mode (default: `replace`) |
| `--dry-run` | No | Flag | Preview without uploading |
| `--no-validate` | No | Flag | Skip validation (not recommended) |

## Upload Modes

### Replace Mode

Completely overwrites the existing content in GCS with the new file.

- **Use case**: When you've regenerated all content and want a fresh start
- **Example**: After running `pregenerate_content.py` with `--force`

### Append Mode

Merges new content with existing content in GCS.

- **Duplicate handling**: Items with duplicate names (characters) or titles (campaigns) are skipped
- **Preserves existing content**: Only adds new items
- **Use case**: Adding a single new character or campaign without regenerating everything

**Example workflow:**
```bash
# Create a file with just the new character
cat > new_character.json <<EOF
{
  "characters": [
    {
      "name": "New Hero",
      "character_class": "Paladin",
      "backstory": "A brave hero on a quest...",
      "type": "warrior",
      "gender": "non-binary",
      "facial_expression": "determined",
      "build": "athletic"
    }
  ],
  "total": 1
}
EOF

# Upload in append mode
docker exec gaia-backend-dev python3 scripts/upload_pregenerated_content.py \
  --file ./new_character.json \
  --type characters \
  --env prod \
  --mode append
```

## JSON File Format

### Characters File (`characters.json`)

```json
{
  "characters": [
    {
      "name": "Character Name",
      "character_class": "Fighter",
      "type": "warrior",
      "backstory": "Detailed backstory (min 50 chars)...",
      "gender": "non-binary",
      "facial_expression": "determined",
      "build": "average"
    }
  ],
  "total": 1
}
```

**Required fields:**
- `name` (string): Character name
- `character_class` (string): D&D class
- `backstory` (string): Backstory with at least 50 characters

**Optional fields:**
- `type`, `gender`, `facial_expression`, `build`, etc.

### Campaigns File (`campaigns.json`)

```json
{
  "campaigns": [
    {
      "title": "Campaign Title",
      "description": "Detailed description (min 50 chars)...",
      "style": "epic fantasy",
      "key_npcs": ["NPC 1", "NPC 2", "NPC 3"]
    }
  ],
  "total": 1
}
```

**Required fields:**
- `title` (string): Campaign title
- `description` (string): Description with at least 50 characters

**Optional fields:**
- `style`, `key_npcs`, etc.

## GCS Storage Paths

The script uploads to the following paths:

**Production:**
```
gs://gaia-campaigns-prod/campaigns/prod/pregenerated/characters.json
gs://gaia-campaigns-prod/campaigns/prod/pregenerated/campaigns.json
```

**Staging:**
```
gs://gaia-campaigns-stg/campaigns/stg/pregenerated/characters.json
gs://gaia-campaigns-stg/campaigns/stg/pregenerated/campaigns.json
```

## Validation

The script validates JSON structure before upload:

1. **File exists and is valid JSON**
2. **Root object structure**:
   - Must have `characters` or `campaigns` array
   - Should have `total` field (auto-added if missing)
3. **Array items**:
   - Characters: Must have `name`, `character_class`, `backstory`
   - Campaigns: Must have `title`, `description`
4. **Minimum content**:
   - Arrays must not be empty
   - Backstory/description must be at least 50 characters

## Troubleshooting

### "Module not found" errors

**Solution**: Run the script inside Docker container:
```bash
docker exec gaia-backend-dev python3 scripts/upload_pregenerated_content.py ...
```

### "Failed to initialize GCS connection"

**Solutions**:
1. Check authentication:
   ```bash
   gcloud auth application-default login
   ```
2. Verify service account has permissions:
   - `roles/storage.objectAdmin` on both buckets

### "Validation failed"

**Solution**: Check JSON structure matches the format above. Use `--dry-run` to test validation without uploading.

### Duplicate items in append mode

**Behavior**: Items with duplicate names/titles are automatically skipped with a warning. This is intentional to preserve existing content.

## Related Scripts

- `backend/scripts/pregenerate_content.py` - Generates new content
- `backend/scripts/claude_helpers/migrate_pregenerated_content.py` - Legacy migration utility

## Security Notes

- The script never modifies local files
- Append mode preserves existing content in GCS
- Use `--dry-run` to preview changes before committing
- Authentication uses Google Cloud Application Default Credentials (secure)

## Examples Repository

Test files are available in `generated/`:
- `generated/test_upload_character.json` - Example character file
- `generated/test_upload_campaign.json` - Example campaign file

These can be used for testing with `--dry-run`:

```bash
docker exec gaia-backend-dev python3 scripts/upload_pregenerated_content.py \
  --file ./generated/test_upload_character.json \
  --type characters \
  --env stg \
  --mode append \
  --dry-run
```
