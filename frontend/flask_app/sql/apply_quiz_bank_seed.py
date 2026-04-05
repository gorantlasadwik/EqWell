from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "eqwell_scores.db"
SEED_SQL_PATH = Path(__file__).resolve().with_name("quiz_bank_seed.sql")


def ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Quizzes (
            quiz_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            type TEXT NOT NULL,
            created_by INTEGER
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            is_mandatory INTEGER NOT NULL DEFAULT 1,
            weight INTEGER NOT NULL DEFAULT 1,
            polarity INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (quiz_id) REFERENCES Quizzes(quiz_id)
        )
        """
    )

    columns = {
        str(row[1]).strip().lower()
        for row in conn.execute("PRAGMA table_info(Questions)").fetchall()
    }
    if "polarity" not in columns:
        conn.execute("ALTER TABLE Questions ADD COLUMN polarity INT DEFAULT 1")


def apply_seed(conn: sqlite3.Connection, sql_text: str) -> None:
    # Keep reruns deterministic for these 4 curated quizzes.
    conn.execute("DELETE FROM Questions WHERE quiz_id IN (1, 2, 3, 4)")
    conn.execute("DELETE FROM Quizzes WHERE quiz_id IN (1, 2, 3, 4)")

    # Table migration is handled in Python above, so skip raw ALTER line here.
    normalized_sql = sql_text.replace("ALTER TABLE Questions ADD COLUMN polarity INT DEFAULT 1;", "")
    conn.executescript(normalized_sql)


def main() -> None:
    sql_text = SEED_SQL_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(DB_PATH) as conn:
        ensure_tables(conn)
        apply_seed(conn, sql_text)
        conn.commit()

    print("Applied quiz bank seed to", DB_PATH)


if __name__ == "__main__":
    main()
