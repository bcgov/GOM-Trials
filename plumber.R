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
        $4,$5,$6,$7,
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
        trials.timestamp IS NULL
        OR EXCLUDED.timestamp >= trials.timestamp
    ",
                        params = list(
                          t$uuid,
                          t$lat, t$lon,
                          t$species, t$seedlot, t$seedlings, t$spacing,
                          t$timestamp, t$user_id, t$growth_grid,
                          t$site_series, t$smr, t$snr, t$site_fact, t$site_prep
                        ))
    
  insterted = insterted + 1
  }
  
  list(inserted = inserted)
}
