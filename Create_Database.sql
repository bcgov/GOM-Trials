-- !preview conn=DBI::dbConnect(RSQLite::SQLite())

BEGIN;

CREATE TABLE IF NOT EXISTS trial_photos (
  photo_uuid     text PRIMARY KEY,
  trial_uuid     text NOT NULL REFERENCES gom_trials(uuid) ON DELETE CASCADE,
  sha256         text NOT NULL,
  bytes          bigint NOT NULL,
  file_relpath   text NOT NULL,   -- e.g. photos/<trial_uuid>/<photo_uuid>.jpg
  created_at_client timestamptz,
  uploaded_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trial_photos_trial
  ON trial_photos(trial_uuid);

-- Also migrates existing installations. Run before deploying the updated API.
ALTER TABLE trial_photos ADD COLUMN IF NOT EXISTS assessment_uuid text;

CREATE INDEX IF NOT EXISTS idx_trial_photos_assessment
  ON trial_photos(assessment_uuid);

-- Identical content may belong to planting and/or several assessments.
DROP INDEX IF EXISTS uq_trial_photos_trial_sha;
CREATE UNIQUE INDEX IF NOT EXISTS uq_trial_photos_planting_sha
  ON trial_photos(trial_uuid, sha256) WHERE assessment_uuid IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_trial_photos_assessment_sha
  ON trial_photos(trial_uuid, assessment_uuid, sha256)
  WHERE assessment_uuid IS NOT NULL;

COMMIT;

