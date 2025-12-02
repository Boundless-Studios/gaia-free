-- Rename legacy column 'title' to 'name' in campaign_sessions (idempotent for Postgres)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='campaign_sessions' AND column_name='title'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='campaign_sessions' AND column_name='name'
  ) THEN
    ALTER TABLE campaign_sessions RENAME COLUMN title TO name;
  END IF;
END $$;

