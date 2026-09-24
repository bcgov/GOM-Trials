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


## convert null to NAs
db_char <- function(x) {
  if (is.null(x) || length(x) == 0)
    NA_character_
  else
    as.character(x)
}

db_num <- function(x) {
  if (is.null(x) || length(x) == 0)
    NA_real_
  else
    as.numeric(x)
}

json_value <- function(x) {
  if (length(x) == 0 || is.na(x[[1]])) {
    unbox(NA)
  } else {
    unbox(x[[1]])
  }
}

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

#* Get list of usernames in database
#* @get /usernames
function(req, res) {
  con <- pg_connect()
  on.exit(dbDisconnect(con), add = TRUE)
  
  base_query <- "
    SELECT
      username, name, email
    FROM gom_users
  "
  data <- dbGetQuery(con, base_query)
  
  res$body <- jsonlite::toJSON(data, auto_unbox = TRUE, na = "null")
  res
}

#* Download users
#* @get /users
#* @serializer json
function(req, res) {
  con <- pg_connect()
  tryCatch({
    
    users <- DBI::dbGetQuery(
      con,
      "
      SELECT
          user_uuid,
          username,
          name,
          email
      FROM gom_users
      ORDER BY username
      "
    )
    
    list(
      success = TRUE,
      users = users
    )
    
  }, error = function(e) {
    
    res$status <- 500
    
    list(
      success = FALSE,
      error = conditionMessage(e)
    )
  })
}

#* Upsert users from client
#* @post /users
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
      INSERT INTO gom_users (
        username,
        user_uuid,
        name,
        email,
        created_at
      )
      VALUES (
        $1,$2,$3,$4, NOW()
      )
      ON CONFLICT (user_uuid)
      DO NOTHING",
                        params = list(
                          t$username,
                          t$user_uuid,
                          t$name,
                          t$email
                        ))
    
    inserted = inserted + 1
  }
  
  list(inserted = inserted)
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
      elev,
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
      site_prep,
      request_key,
      contact_name AS trial_owner,
      block_name,
      replicate_no
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
  
  body <- jsonlite::fromJSON(
    req$postBody,
    simplifyVector = TRUE
  )
  
  if(!"updated_at" %in% colnames(body)) body$updated_at <- NA
  if(!"updated_by" %in% colnames(body)) body$updated_by <- NA
  
  if (length(body) == 0) {
    return(list(
      message = "No trials received"
    ))
  }
  
  con <- pg_connect()
  on.exit(DBI::dbDisconnect(con), add = TRUE)
  
  inserted <- 0
  updated <- 0
  unchanged <- 0
  
  DBI::dbWithTransaction(con, {
    
    for (i in seq_len(nrow(body))) {
      
      t <- body[i, ]
      
      trial_uuid <- t$uuid
      
      # ====================================================
      # 1. Existing server version
      # ====================================================
      
      old_trial <- DBI::dbGetQuery(
        con,
        "
        SELECT *
        FROM gom_trials
        WHERE uuid = $1
        FOR UPDATE
        ",
        params = list(
          trial_uuid
        )
      )
      
      existed_before <- nrow(old_trial) == 1
      
      
      # ====================================================
      # 2. Upsert
      # ====================================================
      
      rows_changed <- DBI::dbExecute(
        con,
        "
        INSERT INTO gom_trials (
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
          site_series,
          smr,
          snr,
          soil_site_factors,
          site_prep,
          request_key,
          elev,
          contact_name,
          block_name,
          replicate_no,
          updated_at,
          updated_by
        )

        VALUES (
          $1, $2, $3,
          $4, $5, $6,
          NULLIF($7, '')::double precision,
          $8, $9, $10,
          $11, $12, $13,
          $14, $15, $16,
          $17, $18, $19, $20,
          $21, $22
        )

        ON CONFLICT (uuid)
        DO UPDATE SET
          lat               = EXCLUDED.lat,
          lon               = EXCLUDED.lon,
          species           = EXCLUDED.species,
          seedlot           = EXCLUDED.seedlot,
          seedlings         = EXCLUDED.seedlings,
          spacing           = EXCLUDED.spacing,
          growth_grid       = EXCLUDED.growth_grid,
          site_series       = EXCLUDED.site_series,
          smr               = EXCLUDED.smr,
          snr               = EXCLUDED.snr,
          soil_site_factors = EXCLUDED.soil_site_factors,
          site_prep         = EXCLUDED.site_prep,
          elev              = EXCLUDED.elev,
          contact_name      = EXCLUDED.contact_name,
          block_name        = EXCLUDED.block_name,
          replicate_no      = EXCLUDED.replicate_no,
          updated_at        = EXCLUDED.updated_at,
          updated_by        = EXCLUDED.updated_by

        WHERE
          gom_trials.updated_at IS NULL
          OR EXCLUDED.updated_at >= gom_trials.updated_at
        ",
        params = list(
          t$uuid,
          t$lat,
          t$lon,
          t$species,
          t$seedlot,
          t$seedlings,
          t$spacing,
          t$timestamp,
          t$user_id,
          t$growth_grid,
          t$site_series,
          t$smr,
          t$snr,
          t$site_fact,
          t$site_prep,
          t$request_key,
          t$elev,
          t$trial_owner,
          t$block_name,
          t$replicate_no,
          t$updated_at,
          t$updated_by
        )
      )
      
      
      # ====================================================
      # 3. Fetch resulting server version
      # ====================================================
      
      new_trial <- DBI::dbGetQuery(
        con,
        "
        SELECT *
        FROM gom_trials
        WHERE uuid = $1
        ",
        params = list(
          trial_uuid
        )
      )
      
      
      # ====================================================
      # 4. New trial: no UPDATE audit needed
      # ====================================================
      
      if (!existed_before) {
        
        inserted <- inserted + 1
        next
      }
      
      
      # ====================================================
      # 5. Determine whether anything actually changed
      # ====================================================
      
      old_compare <- old_trial
      new_compare <- new_trial
      
      # Don't let audit metadata itself be what makes
      # two otherwise identical records appear different.
      compare_columns <- intersect(
        names(old_compare),
        names(new_compare)
      )
      
      old_compare <- old_compare[, compare_columns, drop = FALSE]
      new_compare <- new_compare[, compare_columns, drop = FALSE]
      
      changed <- !isTRUE(
        all.equal(
          old_compare,
          new_compare,
          check.attributes = FALSE
        )
      )
      
      if (!changed) {
        
        unchanged <- unchanged + 1
        next
      }
      
      
      # ====================================================
      # 6. Audit the change
      # ====================================================
      
      old_json <- jsonlite::toJSON(
        as.list(old_trial[1, ]),
        auto_unbox = TRUE,
        na = "null",
        null = "null"
      )
      
      new_json <- jsonlite::toJSON(
        as.list(new_trial[1, ]),
        auto_unbox = TRUE,
        na = "null",
        null = "null"
      )
      
      DBI::dbExecute(
        con,
        "
        INSERT INTO trial_audit (
          audit_uuid,
          trial_uuid,
          changed_by,
          changed_at,
          action,
          old_data,
          new_data
        )

        VALUES (
          $1,
          $2,
          $3,
          NOW(),
          'UPDATE',
          $4::jsonb,
          $5::jsonb
        )
        ",
        params = list(
          uuid::UUIDgenerate(),
          trial_uuid,
          t$updated_by,
          as.character(old_json),
          as.character(new_json)
        )
      )
      
      updated <- updated + 1
    }
  })
  
  list(
    inserted = inserted,
    updated = updated,
    unchanged = unchanged
  )
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
  
  # Deduplicate within planting photos or this specific assessment.
  q2 <- dbGetQuery(con,
                   "SELECT photo_uuid FROM trial_photos
                    WHERE trial_uuid=$1 AND sha256=$2
                      AND assessment_uuid IS NOT DISTINCT FROM $3::text LIMIT 1",
                   params=list(body$trial_uuid, body$sha256,
                               body$assessment_uuid %||% NA_character_)
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
  assessment_uuid <- req$args$assessment_uuid %||% NA_character_
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
      file_relpath, assessment_uuid, uploaded_at
    ) VALUES ($1,$2,$3,$4,$5,$6, now())
    ON CONFLICT (photo_uuid)
    DO UPDATE SET
      trial_uuid   = EXCLUDED.trial_uuid,
      assessment_uuid = EXCLUDED.assessment_uuid,
      sha256       = EXCLUDED.sha256,
      bytes        = EXCLUDED.bytes,
      file_relpath = EXCLUDED.file_relpath,
      uploaded_at  = now()
  ",
            params=list(photo_uuid, trial_uuid, sha256, actual_bytes, relpath,
                        assessment_uuid)
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
    SELECT photo_uuid, trial_uuid, assessment_uuid, file_relpath, sha256, bytes
    FROM trial_photos
    WHERE trial_uuid = ANY(string_to_array($1, ',')::TEXT[])
  ", params = list(trial_uuids))
  
  static_base <- "http://178.128.233.227/static/"
  
  # If file_relpath is like "<trial_uuid>/<photo_uuid>.jpg"
  df$url <- if(nrow(df > 0)) paste0(static_base, df$file_relpath) else character(0)
  df
}

#* @get /trial_owners
function(req, res) {
  con <- pg_connect()
  on.exit(dbDisconnect(con), add = TRUE)
  
  base_query <- "
    SELECT
      company_name,
      contact_name,
      contact_email,
      objective
    FROM trial_owners
  "
  data <- dbGetQuery(con, base_query)
  res$body <- jsonlite::toJSON(data, auto_unbox = TRUE, na = "null")
  res
}

#* Upsert owners from client
#* @post /trial_owners
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
      INSERT INTO trial_owners (
        company_name,
        contact_name,
        contact_email,
        objective
      )
      VALUES (
        $1,$2,$3,$4
      )
      ON CONFLICT (contact_name)
      DO UPDATE SET
        company_name = EXCLUDED.company_name,
        contact_email = EXCLUDED.contact_email,
        objective = EXCLUDED.objective
      ",
                        params = list(
                          t$company_name,
                          t$contact_name,
                          t$contact_email,
                          t$objective
                        ))
    
    inserted = inserted + 1
  }
  
  list(inserted = inserted)
}

### assessments ################################

#* Upload assessments
#* @post /assessments
#* @serializer json
function(req, res) {
  
  body <- jsonlite::fromJSON(
    req$postBody,
    simplifyVector = FALSE
  )
  
  assessments <- body$assessments
  
  if (is.null(assessments)) {
    res$status <- 400
    return(list(
      success = FALSE,
      error = "Missing assessments"
    ))
  }
  con <- pg_connect()
  tryCatch({
    
    DBI::dbWithTransaction(con, {
      
      for (assessment in assessments) {
        if (!is.null(assessment$grid_direction) &&
            length(assessment$grid_direction) == 1) {
          
          DBI::dbExecute(
            con,
            "
            UPDATE gom_trials
            SET grid_direction = $1
            WHERE uuid = $2
              AND grid_direction IS NULL
            ",
            params = list(
              assessment$grid_direction,
              assessment$trial_uuid
            )
          )
        }
        # --------------------------------------------------
        # Assessment
        # --------------------------------------------------
        
        DBI::dbExecute(
          con,
          "
          INSERT INTO assessments (
              assessment_uuid,
              trial_uuid,
              user_uuid,
              assessment_date,
              trial_rating,
              notes
          )
          VALUES ($1, $2, $3, $4, $5, $6)

          ON CONFLICT (assessment_uuid)
          DO NOTHING
          ",
          params = list(
            assessment$assessment_uuid,
            assessment$trial_uuid,
            assessment$user_uuid,
            assessment$assessment_date,
            db_char(assessment$trial_rating),
            db_char(assessment$notes)
          )
        )
        
        # --------------------------------------------------
        # Trees
        # --------------------------------------------------
        
        for (tree in assessment$trees) {
          
          # Ensure permanent tree exists.
          #
          # This is safe because tree_uuid is deterministic.
          
          DBI::dbExecute(
            con,
            "
            INSERT INTO trial_trees (
                tree_uuid,
                trial_uuid,
                tree_number,
                row_num,
                col_num
            )
            VALUES ($1, $2, $3, $4, $5)

            ON CONFLICT (tree_uuid)
            DO NOTHING
            ",
            params = list(
              tree$tree_uuid,
              assessment$trial_uuid,
              tree$tree_number,
              tree$row_num,
              tree$col_num
            )
          )
          
          # ------------------------------------------------
          # Tree assessment
          # ------------------------------------------------
          
          DBI::dbExecute(
            con,
            "
            INSERT INTO tree_assessments (
                tree_assessment_uuid,
                assessment_uuid,
                tree_uuid,
                rating,
                height,
                diameter
            )
            VALUES ($1, $2, $3, $4, $5, $6)

            ON CONFLICT (tree_assessment_uuid)
            DO NOTHING
            ",
            params = list(
              tree$tree_assessment_uuid,
              assessment$assessment_uuid,
              tree$tree_uuid,
              db_char(tree$rating),
              db_num(tree$height),
              db_num(tree$diameter)
            )
          )
          
          # ------------------------------------------------
          # Damage
          # ------------------------------------------------
          
          if (length(tree$damage) > 0) {
            
            for (damage in tree$damage) {
              
              DBI::dbExecute(
                con,
                "
                INSERT INTO assessment_damage (
                    damage_uuid,
                    tree_assessment_uuid,
                    damage_code,
                    severity
                )
                VALUES ($1, $2, $3, $4)

                ON CONFLICT (damage_uuid)
                DO NOTHING
                ",
                params = list(
                  damage$damage_uuid,
                  tree$tree_assessment_uuid,
                  damage$damage_code,
                  damage$severity
                )
              )
            }
          }
        }
      }
    })
    
    list(
      success = TRUE,
      uploaded = length(assessments)
    )
    
  }, error = function(e) {
    
    res$status <- 500
    
    list(
      success = FALSE,
      error = conditionMessage(e)
    )
  })
}

#* Download assessments
#* @param since:string Optional timestamp
#* @get /assessments
#* @serializer json
function(since = NULL, res) {
  con <- pg_connect()
  on.exit(DBI::dbDisconnect(con), add = TRUE)
  if (is.null(since) || !nzchar(since)) {
    
    assessments <- DBI::dbGetQuery(
      con,
      "
      SELECT
          a.assessment_uuid,
          a.trial_uuid,
          a.user_uuid,
          a.assessment_date,
          a.trial_rating,
          a.notes,
          a.created_at,
          t.grid_direction
      FROM assessments a
      JOIN gom_trials t
        ON a.trial_uuid = t.uuid::uuid
      ORDER BY a.created_at
      "
    )
    
  } else {
    
    assessments <- DBI::dbGetQuery(
      con,
      "
      SELECT
          a.assessment_uuid,
          a.trial_uuid,
          a.user_uuid,
          a.assessment_date,
          a.trial_rating,
          a.notes,
          a.created_at,
          t.grid_direction
      FROM assessments a
      JOIN gom_trials t
        ON a.trial_uuid = t.uuid::uuid
      WHERE a.created_at >= $1::timestamptz
      ORDER BY a.created_at
      ",
      params = list(since)
    )
  }
  
  result <- vector(
    "list",
    nrow(assessments)
  )
  
  for (i in seq_len(nrow(assessments))) {
    
    a <- assessments[i, ]
    
    trees <- DBI::dbGetQuery(
      con,
      "
      SELECT
          ta.tree_assessment_uuid,
          ta.tree_uuid,
          tt.tree_number,
          tt.row_num,
          tt.col_num,
          ta.rating,
          ta.height,
          ta.diameter
      FROM tree_assessments ta
      JOIN trial_trees tt
        ON ta.tree_uuid = tt.tree_uuid
      WHERE ta.assessment_uuid = $1
      ORDER BY tt.tree_number
      ",
      params = list(a$assessment_uuid)
    )
    
    tree_list <- vector(
      "list",
      nrow(trees)
    )
    
    for (j in seq_len(nrow(trees))) {
      
      tree <- trees[j, ]
      
      damage <- DBI::dbGetQuery(
        con,
        "
        SELECT
            damage_uuid,
            damage_code,
            severity
        FROM assessment_damage
        WHERE tree_assessment_uuid = $1
        ",
        params = list(
          tree$tree_assessment_uuid
        )
      )
      
      damage_list <- vector(
        "list",
        nrow(damage)
      )
      
      if (nrow(damage) > 0) {
        
        for (k in seq_len(nrow(damage))) {
          
          d <- damage[k, ]
          
          damage_list[[k]] <- list(
            damage_uuid =
              json_value(d$damage_uuid),
            
            damage_code =
              json_value(d$damage_code),
            
            severity =
              json_value(d$severity)
          )
        }
      }
      
      tree_list[[j]] <- list(
        tree_assessment_uuid =
          json_value(tree$tree_assessment_uuid),
        
        tree_uuid =
          json_value(tree$tree_uuid),
        
        tree_number =
          json_value(tree$tree_number),
        
        row_num =
          json_value(tree$row_num),
        
        col_num =
          json_value(tree$col_num),
        
        rating =
          json_value(tree$rating),
        
        height =
          json_value(tree$height),
        
        diameter =
          json_value(tree$diameter),
        
        damage = damage_list
      )
    }
    
    result[[i]] <- list(
      assessment_uuid = json_value(a$assessment_uuid),
      trial_uuid = json_value(a$trial_uuid),
      user_uuid = json_value(a$user_uuid),
      assessment_date = json_value(a$assessment_date),
      trial_rating = json_value(a$trial_rating),
      notes = json_value(a$notes),
      created_at = json_value(format(a$created_at, "%Y-%m-%dT%H:%M:%OS6Z", tz = "UTC")),
      grid_direction = json_value(a$grid_direction),
      trees = tree_list
    )
  }
  
  list(
    assessments = result
  )
}
