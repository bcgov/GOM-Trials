library(plumber)
library(DBI)
library(RPostgres)
library(jsonlite)
library(uuid)

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

#* Get trials updated after a timestamp
#* @param since optional ISO timestamp (UTC)
#* @get /trials
function(req, res, since = NULL) {
  con <- pg_connect()
  on.exit(dbDisconnect(con), add = TRUE)
  
  base_query <- "
    WITH latest_assessment AS (
      SELECT DISTINCT ON (trial_uuid)
        trial_uuid,
        growth_grid/
      FROM assessments
      ORDER BY trial_uuid, assessed_at DESC, created_at DESC
    )
    SELECT
      t.*,
    la.growth_grid
    FROM trials t
    LEFT JOIN latest_assessment la
      ON la.trial_uuid = t.uuid
  "
  
  if (!is.null(since) && nchar(since) > 0) {
    query <- paste0(base_query, " WHERE t.timestamp > $1")
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
  updated  <- 0
  
  for (i in seq_len(nrow(body))) {
    t <- body[i, ]
    # check if exists
    q_check <- dbGetQuery(con, "SELECT lat FROM trials WHERE uuid=$1", list(t$uuid))
    
    if (nrow(q_check) == 0) {
      # insert
      dbExecute(con, "
        INSERT INTO trials (uuid, lat, lon, species, seedlot, seedlings, timestamp, growth_grid)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
      ",
                params = list(t$uuid, t$lat, t$lon, t$species, t$seedlot,
                              t$seedlings, t$timestamp, t$growth_grid))
      inserted <- inserted + 1
    } else {
      message("Entry already exists - skipping")
      # update (last-writer-wins)
      # dbExecute(con, "
      #   UPDATE trials
      #   SET species=$2, seedlings=$3, seedlot=$4, spacing=$5,
      #       lat=$6, lon=$7, updated_at=$8, deleted=$9, user_id=$10
      #   WHERE uuid=$1
      # ",
      #           params = list(t$uuid, t$species, t$seedlings, t$seedlot, t$spacing,
      #                         t$lat, t$lon, t$updated_at, t$deleted, t$user_id))
      # updated <- updated + 1
    }
  }
  
  list(inserted = inserted, updated = updated)
}