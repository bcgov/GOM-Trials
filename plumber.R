library(plumber)
library(DBI)
library(RPostgres)
library(jsonlite)
library(uuid)
#library(magick)
library(fs)

#* @apiTitle Gomapp Trial Sync API (R / plumber)

# Connect lazily so each request gets a fresh connection
pg_connect <- function() {
  dbConnect(
    RPostgres::Postgres(),
    dbname   = Sys.getenv("PG_DB"),
    host     = Sys.getenv("PG_HOST"),
    port     = Sys.getenv("PG_PORT"),
    user     = Sys.getenv("PG_USER"),
    password = Sys.getenv("PG_PASS")
  )
}

PHOTO_DIR <- "/var/lib/gomapp/photos"

get_field <- function(x, key) {
  if (is.null(x)) return(NULL)
  # works for both list and named atomic vector
  out <- tryCatch(x[[key]], error = function(e) NULL)
  out
}

`%||%` <- function(x, y) if (!is.null(x) && length(x) && !is.na(x)) x else y



#* Debug: show what 'image' looks like
#* @param image:file
#* @post /debug_upload
#* @serializer json
function(image, res) {
  list(
    image_is_null = is.null(image),
    image_class = paste(class(image), collapse = ", "),
    image_length = length(image),
    image_names = if (is.null(image)) NULL else names(image),
    image_preview = if (is.null(image)) NULL else {
      # avoid dumping huge content
      x <- image
      if (is.raw(x)) paste0("raw[", length(x), "]") else
        paste0(substr(capture.output(str(x)), 1, 200), collapse = "\n")
    }
  )
}



#* Upload a JPG image (multipart/form-data)
#* @param image:file The uploaded image file
#* @post /upload_old
#* @serializer json
function(image, res) {
  
  if (is.null(image) || length(image) < 1) {
    res$status <- 400
    return(list(error = "Missing file field 'image'"))
  }
  
  # In your case: image is a named list; name = filename, value = raw bytes
  filename_in <- names(image)[1] %||% "upload.jpg"
  content <- image[[1]]
  
  if (!is.raw(content) || length(content) == 0) {
    res$status <- 400
    return(list(error = "Uploaded file content is empty or not raw"))
  }
  
  # Sanitize filename (strip any path, remove weird chars)
  safe_base <- path_file(filename_in)
  safe_base <- gsub("[^A-Za-z0-9._-]", "_", safe_base)
  if (!nzchar(safe_base) || is.na(safe_base)) safe_base <- "upload.jpg"
  
  out_name <- paste0(format(Sys.time(), "%Y%m%d_%H%M%S"), "_", safe_base)
  out_path <- path(PHOTO_DIR, out_name)
  
  # Write raw bytes
  writeBin(content, out_path)
  
  list(ok = TRUE, filename = out_name, saved_to = out_path)
}

#* @param since optional ISO timestamp (UTC)
#* @get /trials
function(req, res, since = NULL) {
  con <- pg_connect()
  on.exit(dbDisconnect(con), add = TRUE)
  
  base_query <- "
    SELECT
      uuid,
      lat,
      lon,
      species,
      seedlot,
      seedlings,
      spacing,
      timestamp,
      user_id,
      growth_grid,

      -- new site fields
      site_series,
      smr,
      snr,
      soil_site_factors,
      site_prep
    FROM gom_trials
  "
  
  if (!is.null(since) && nchar(since) > 0) {
    query <- paste0(base_query, " WHERE timestamp > $1")
    data  <- dbGetQuery(con, query, list(since))
  } else {
    data <- dbGetQuery(con, base_query)
  }
  
  res$body <- jsonlite::toJSON(data, auto_unbox = TRUE, na = "null")
  res
}


#* Upsert trials from client
#* @post /trials
function(req, res) {
  
  body <- jsonlite::fromJSON(req$postBody, simplifyVector = TRUE)
  if (length(body) == 0) return(list(message = "No trials received"))
  
  con <- pg_connect()
  on.exit(dbDisconnect(con), add = TRUE)
  
  inserted <- 0
  # Loop over rows
  for (i in seq_len(nrow(body))) {
    t <- body[i, ]
    
    result <- dbExecute(con, "
      INSERT INTO gom_trials (
        uuid,
        lat, lon,
        species, seedlot, seedlings, spacing,
        timestamp, user_id, growth_grid,
        site_series, smr, snr, soil_site_factors, site_prep
      )
      VALUES (
        $1,$2,$3,
        $4,$5,$6,NULLIF($7, '')::double precision,
        $8,$9,$10,
        $11,$12,$13,$14,$15
      )
      ON CONFLICT (uuid)
      DO UPDATE SET
        lat          = EXCLUDED.lat,
        lon          = EXCLUDED.lon,
        species      = EXCLUDED.species,
        seedlot      = EXCLUDED.seedlot,
        seedlings    = EXCLUDED.seedlings,
        spacing      = EXCLUDED.spacing,
        growth_grid  = EXCLUDED.growth_grid,
        site_series  = EXCLUDED.site_series,
        smr          = EXCLUDED.smr,
        snr          = EXCLUDED.snr,
        soil_site_factors = EXCLUDED.soil_site_factors,
        site_prep    = EXCLUDED.site_prep,
        timestamp    = EXCLUDED.timestamp
      WHERE
        gom_trials.timestamp IS NULL
        OR EXCLUDED.timestamp >= gom_trials.timestamp
    ",
                        params = list(
                          t$uuid,
                          t$lat, t$lon,
                          t$species, t$seedlot, t$seedlings, t$spacing,
                          t$timestamp, t$user_id, t$growth_grid,
                          t$site_series, t$smr, t$snr, t$site_fact, t$site_prep
                        ))
    
    inserted = inserted + 1
  }
  
  list(inserted = inserted)
}

####Photo upload api
#* @post /photos/init
#* @serializer json
function(req, res) {
  body <- jsonlite::fromJSON(req$postBody, simplifyVector = TRUE)
  
  required <- c("photo_uuid", "trial_uuid", "sha256", "bytes")
  if (!all(required %in% names(body))) {
    res$status <- 400
    return(list(error = "photo_uuid, trial_uuid, sha256, bytes required"))
  }
  
  con <- pg_connect()
  on.exit(dbDisconnect(con), add = TRUE)
  
  # Already have this photo_uuid?
  q1 <- dbGetQuery(con,
                   "SELECT 1 FROM trial_photos WHERE photo_uuid=$1 LIMIT 1",
                   params=list(body$photo_uuid)
  )
  if (nrow(q1) > 0) {
    return(list(upload_required = FALSE, reason = "photo_uuid_exists"))
  }
  
  # Already have identical content for this trial?
  q2 <- dbGetQuery(con,
                   "SELECT photo_uuid FROM trial_photos WHERE trial_uuid=$1 AND sha256=$2 LIMIT 1",
                   params=list(body$trial_uuid, body$sha256)
  )
  if (nrow(q2) > 0) {
    return(list(upload_required = FALSE, reason = "duplicate_sha"))
  }
  
  relpath <- file.path("photos", body$trial_uuid, paste0(body$photo_uuid, ".jpg"))
  
  list(
    upload_required = TRUE,
    upload_url = paste0("/photos/upload/", body$photo_uuid),
    file_relpath = relpath
  )
}

#* Upload photo
#* @param image:file The image file to upload
#* @post /photos/upload/<photo_uuid>
#* @serializer json
function(req, res, photo_uuid, image) {
  
  if (is.null(image) || length(image) < 1) {
    res$status <- 400
    return(list(error = "Missing file field 'image'"))
  }
  
  # In your case: image is a named list; name = filename, value = raw bytes
  filename_in <- names(image)[1] %||% "upload.jpg"
  content <- image[[1]]
  
  trial_uuid <- req$args$trial_uuid
  sha256     <- req$args$sha256
  bytes      <- as.numeric(req$args$bytes)
  created_at <- req$args$created_at_client
  
  if (is.null(trial_uuid) || is.null(sha256) || is.null(bytes)) {
    res$status <- 400
    return(list(error="trial_uuid, sha256, bytes must be provided"))
  }
  
  # 4. Move the file from the temp directory to your storage
  base <- Sys.getenv("GOMAPP_PHOTO_DIR", "/var/lib/gomapp/photos")
  tdir <- file.path(base, trial_uuid)
  dir.create(tdir, recursive=TRUE, showWarnings=FALSE)
  
  outpath <- file.path(tdir, paste0(photo_uuid, ".jpg"))
  writeBin(content, outpath)
  actual_bytes <- file.info(outpath)$size
  
  relpath <- file.path("photos", trial_uuid, paste0(photo_uuid, ".jpg"))
  
  con <- pg_connect()
  on.exit(dbDisconnect(con), add = TRUE)
  
  dbExecute(con, "
    INSERT INTO trial_photos (
      photo_uuid, trial_uuid, sha256, bytes,
      file_relpath, uploaded_at
    ) VALUES ($1,$2,$3,$4,$5, now())
    ON CONFLICT (photo_uuid)
    DO UPDATE SET
      trial_uuid   = EXCLUDED.trial_uuid,
      sha256       = EXCLUDED.sha256,
      bytes        = EXCLUDED.bytes,
      file_relpath = EXCLUDED.file_relpath,
      uploaded_at  = now()
  ",
            params=list(photo_uuid, trial_uuid, sha256, actual_bytes, relpath)
  )
  
  list(ok=TRUE, file_relpath=relpath, bytes=actual_bytes)
}

#* @get /photos/list
#* @serializer json
function(req, res) {
  trial_uuids <- req$args$trial_uuids
  
  if (is.null(trial_uuids) || nchar(trial_uuids) == 0) {
    res$status <- 400
    return(list(error = "trial_uuids is required (comma-separated UUIDs)"))
  }
  
  # Clean whitespace (important if you send "uuid1, uuid2")
  trial_uuids <- gsub("\\s+", "", trial_uuids)
  
  con <- pg_connect()
  on.exit(dbDisconnect(con), add = TRUE)
  
  df <- dbGetQuery(con, "
    SELECT photo_uuid, trial_uuid, file_relpath, sha256, bytes
    FROM trial_photos
    WHERE trial_uuid = ANY(string_to_array($1, ',')::TEXT[])
  ", params = list(trial_uuids))
  
  static_base <- "http://178.128.233.227/static/"
  
  # If file_relpath is like "<trial_uuid>/<photo_uuid>.jpg"
  df$url <- if(nrow(df > 0)) paste0(static_base, df$file_relpath) else character(0)
  df
}
