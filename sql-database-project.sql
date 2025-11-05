CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullname TEXT,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    password TEXT NOT NULL
);
