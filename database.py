import aiosqlite
import time

DB_PATH = "memecoin_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alerted_tokens (
                pair_address    TEXT PRIMARY KEY,
                token_name      TEXT,
                symbol          TEXT,
                alert_price     REAL,
                alert_time      INTEGER,
                market_cap      REAL,
                liquidity       REAL,
                score           TEXT,
                tracking        INTEGER DEFAULT 1,
                last_multiplier REAL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_time        INTEGER,
                pairs_scanned    INTEGER,
                passed_market    INTEGER,
                passed_security  INTEGER,
                signals_sent     INTEGER
            )
        """)
        await db.commit()

async def is_already_alerted(pair_address: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM alerted_tokens WHERE pair_address = ?",
            (pair_address,)
        )
        return await cursor.fetchone() is not None

async def save_alerted_token(pair_address, token_name, symbol,
                              alert_price, market_cap, liquidity, score):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO alerted_tokens
            (pair_address, token_name, symbol, alert_price,
             alert_time, market_cap, liquidity, score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (pair_address, token_name, symbol, alert_price,
              int(time.time()), market_cap, liquidity, score))
        await db.commit()

async def get_tracked_tokens():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT pair_address, token_name, symbol,
                   alert_price, alert_time, last_multiplier
            FROM alerted_tokens
            WHERE tracking = 1
        """)
        return await cursor.fetchall()

async def update_tracking(pair_address, tracking=None, last_multiplier=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if tracking is not None:
            await db.execute(
                "UPDATE alerted_tokens SET tracking = ? WHERE pair_address = ?",
                (tracking, pair_address)
            )
        if last_multiplier is not None:
            await db.execute(
                "UPDATE alerted_tokens SET last_multiplier = ? WHERE pair_address = ?",
                (last_multiplier, pair_address)
            )
        await db.commit()

async def save_scan_stats(pairs_scanned, passed_market,
                           passed_security, signals_sent):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO scan_history
            (scan_time, pairs_scanned, passed_market,
             passed_security, signals_sent)
            VALUES (?, ?, ?, ?, ?)
        """, (int(time.time()), pairs_scanned, passed_market,
              passed_security, signals_sent))
        await db.commit()
