CREATE TABLE IF NOT EXISTS games (
  event_id TEXT PRIMARY KEY,
  date TEXT,
  home TEXT,
  away TEXT,
  home_score INTEGER,
  away_score INTEGER
);
CREATE TABLE IF NOT EXISTS ratings (
  team TEXT PRIMARY KEY,
  games INTEGER,
  raw_o REAL,
  raw_d REAL,
  adj_o REAL,
  adj_d REAL,
  net REAL,
  adj_t REAL,
  raw_t REAL
);
