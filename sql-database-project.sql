CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullname TEXT,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_name TEXT NOT NULL,
    location TEXT NOT NULL,
    description TEXT,
    datetime TEXT NOT NULL,
    participants INTEGER DEFAULT 0,
    max_participants INTEGER DEFAULT 50,
    image TEXT,
    created_by TEXT,
    collected_trash INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Pending',
    holder_name TEXT
);

CREATE TABLE IF NOT EXISTS event_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    UNIQUE(event_id, username)
);

CREATE TABLE IF NOT EXISTS community_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    description TEXT NOT NULL,
    image TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);