import Database from "better-sqlite3";
import bcrypt from "bcrypt";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = path.join(__dirname, "..", "auth-lab.db");

const db = new Database(DB_PATH);

// Enable WAL mode for better concurrent read performance
db.pragma("journal_mode = WAL");

// ── Schema ──

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    key_hash TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    permissions TEXT NOT NULL DEFAULT 'read',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS magic_tokens (
    id TEXT PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);

// ── Seed data ──
// Pre-insert alice and bob so every auth method has users ready.
// bcrypt hash of "password" with 10 rounds.

async function seed(): Promise<void> {
  const insert = db.prepare(`
    INSERT OR IGNORE INTO users (id, email, password_hash)
    VALUES (?, ?, ?)
  `);

  const hash = await bcrypt.hash("password", 10);

  insert.run("alice-001", "alice@example.com", hash);
  insert.run("bob-002", "bob@example.com", hash);

  console.log("Seeded users: alice@example.com, bob@example.com (password: 'password')");
}

// Run seed if this file is executed directly
if (process.argv[1] && process.argv[1].includes("db")) {
  seed().catch(console.error);
}

export { db, seed };
export default db;
