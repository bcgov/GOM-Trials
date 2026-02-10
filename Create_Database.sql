-- !preview conn=DBI::dbConnect(RSQLite::SQLite())

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

CREATE UNIQUE INDEX IF NOT EXISTS uq_trial_photos_trial_sha
  ON trial_photos(trial_uuid, sha256);

