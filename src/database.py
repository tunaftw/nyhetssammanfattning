"""SQLite-databas för historisk lagring av nyheter."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

# Databasfil i projektets rot
DB_PATH = Path(__file__).parent.parent / "data" / "news_history.db"


def get_connection() -> sqlite3.Connection:
    """Skapar anslutning till databasen."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Returnera dicts istället för tuples
    return conn


def init_database():
    """Skapar databastabeller om de inte finns."""
    conn = get_connection()
    cursor = conn.cursor()

    # Tabell för rapporter (dagliga/vecko)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date DATE NOT NULL,
            report_type TEXT NOT NULL DEFAULT 'daily',
            total_articles INTEGER DEFAULT 0,
            categories_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(report_date, report_type)
        )
    """)

    # Tabell för nyhetsartiklar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER,
            title TEXT NOT NULL,
            summary TEXT,
            url TEXT,
            source TEXT,
            published_date DATE,
            category TEXT,
            category_name TEXT,
            relevance_score INTEGER,
            api_source TEXT DEFAULT 'gemini',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES reports(id),
            UNIQUE(url, report_id)
        )
    """)

    # Index för snabbare sökningar
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_articles_date
        ON articles(published_date)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_articles_category
        ON articles(category)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reports_date
        ON reports(report_date)
    """)

    conn.commit()
    conn.close()


def save_report(news_data: dict, report_type: str = "daily") -> int:
    """
    Sparar en rapport och dess artiklar till databasen.

    Args:
        news_data: Dict med news_by_category från fetch_all_news()
        report_type: 'daily' eller 'weekly'

    Returns:
        report_id för den sparade rapporten
    """
    init_database()
    conn = get_connection()
    cursor = conn.cursor()

    report_date = news_data.get("fetch_date", datetime.now().strftime("%Y-%m-%d"))

    # Räkna totalt antal artiklar
    total_articles = sum(
        len(cat.get("news_items", []))
        for cat in news_data.get("news_by_category", {}).values()
    )
    categories_count = len(news_data.get("news_by_category", {}))

    # Infoga eller uppdatera rapport
    cursor.execute("""
        INSERT INTO reports (report_date, report_type, total_articles, categories_count)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(report_date, report_type) DO UPDATE SET
            total_articles = excluded.total_articles,
            categories_count = excluded.categories_count,
            created_at = CURRENT_TIMESTAMP
    """, (report_date, report_type, total_articles, categories_count))

    # Hämta report_id
    cursor.execute("""
        SELECT id FROM reports
        WHERE report_date = ? AND report_type = ?
    """, (report_date, report_type))
    report_id = cursor.fetchone()["id"]

    # Spara artiklar
    for cat_key, cat_data in news_data.get("news_by_category", {}).items():
        for article in cat_data.get("news_items", []):
            try:
                cursor.execute("""
                    INSERT INTO articles (
                        report_id, title, summary, url, source,
                        published_date, category, category_name,
                        relevance_score, api_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url, report_id) DO NOTHING
                """, (
                    report_id,
                    article.get("title", ""),
                    article.get("summary", ""),
                    article.get("url", ""),
                    article.get("source", ""),
                    article.get("published_date", ""),
                    cat_key,
                    cat_data.get("name", ""),
                    article.get("relevance_score", 0),
                    article.get("api_source", "gemini"),
                ))
            except sqlite3.Error:
                continue  # Hoppa över dubbletter

    conn.commit()
    conn.close()

    return report_id


def get_reports(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    report_type: Optional[str] = None,
    limit: int = 30
) -> list[dict]:
    """
    Hämtar rapporter med optional filtrering.

    Args:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        report_type: 'daily' eller 'weekly'
        limit: Max antal rapporter

    Returns:
        Lista med rapport-dicts
    """
    init_database()
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM reports WHERE 1=1"
    params = []

    if start_date:
        query += " AND report_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND report_date <= ?"
        params.append(end_date)

    if report_type:
        query += " AND report_type = ?"
        params.append(report_type)

    query += " ORDER BY report_date DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    reports = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return reports


def get_articles(
    report_id: Optional[int] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> list[dict]:
    """
    Hämtar artiklar med optional filtrering.

    Args:
        report_id: Specifik rapport
        category: Filtrera på kategori
        search: Sök i titel/sammanfattning
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        limit: Max antal artiklar

    Returns:
        Lista med artikel-dicts
    """
    init_database()
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT a.*, r.report_date, r.report_type
        FROM articles a
        JOIN reports r ON a.report_id = r.id
        WHERE 1=1
    """
    params = []

    if report_id:
        query += " AND a.report_id = ?"
        params.append(report_id)

    if category:
        query += " AND a.category = ?"
        params.append(category)

    if search:
        query += " AND (a.title LIKE ? OR a.summary LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    if start_date:
        query += " AND r.report_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND r.report_date <= ?"
        params.append(end_date)

    query += " ORDER BY r.report_date DESC, a.relevance_score DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    articles = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return articles


def get_monthly_summary(year: int, month: int) -> dict:
    """
    Hämtar sammanfattning för en specifik månad.

    Returns:
        Dict med statistik och top-artiklar
    """
    init_database()
    conn = get_connection()
    cursor = conn.cursor()

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    # Hämta statistik
    cursor.execute("""
        SELECT
            COUNT(DISTINCT r.id) as total_reports,
            COUNT(a.id) as total_articles,
            AVG(a.relevance_score) as avg_relevance
        FROM reports r
        LEFT JOIN articles a ON a.report_id = r.id
        WHERE r.report_date >= ? AND r.report_date < ?
    """, (start_date, end_date))
    stats = dict(cursor.fetchone())

    # Hämta artiklar per kategori
    cursor.execute("""
        SELECT
            a.category_name,
            COUNT(*) as count
        FROM articles a
        JOIN reports r ON a.report_id = r.id
        WHERE r.report_date >= ? AND r.report_date < ?
        GROUP BY a.category_name
        ORDER BY count DESC
    """, (start_date, end_date))
    by_category = [dict(row) for row in cursor.fetchall()]

    # Top 10 artiklar
    cursor.execute("""
        SELECT a.title, a.source, a.url, a.relevance_score, r.report_date
        FROM articles a
        JOIN reports r ON a.report_id = r.id
        WHERE r.report_date >= ? AND r.report_date < ?
        ORDER BY a.relevance_score DESC
        LIMIT 10
    """, (start_date, end_date))
    top_articles = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "year": year,
        "month": month,
        "stats": stats,
        "by_category": by_category,
        "top_articles": top_articles,
    }


def check_duplicate_url(url: str, days_back: int = 7) -> bool:
    """
    Kollar om en URL redan rapporterats de senaste dagarna.

    Args:
        url: URL att kolla
        days_back: Antal dagar att söka bakåt

    Returns:
        True om URL finns, False annars
    """
    init_database()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) as count
        FROM articles a
        JOIN reports r ON a.report_id = r.id
        WHERE a.url = ?
        AND r.report_date >= date('now', ?)
    """, (url, f"-{days_back} days"))

    result = cursor.fetchone()
    conn.close()

    return result["count"] > 0


def get_database_stats() -> dict:
    """Returnerar övergripande statistik om databasen."""
    init_database()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM reports")
    total_reports = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM articles")
    total_articles = cursor.fetchone()["count"]

    cursor.execute("SELECT MIN(report_date) as first, MAX(report_date) as last FROM reports")
    date_range = dict(cursor.fetchone())

    cursor.execute("""
        SELECT category_name, COUNT(*) as count
        FROM articles
        GROUP BY category_name
        ORDER BY count DESC
    """)
    by_category = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "total_reports": total_reports,
        "total_articles": total_articles,
        "date_range": date_range,
        "by_category": by_category,
    }


if __name__ == "__main__":
    # Test
    init_database()
    print(f"Databas initierad: {DB_PATH}")

    stats = get_database_stats()
    print(f"\nStatistik:")
    print(f"  Rapporter: {stats['total_reports']}")
    print(f"  Artiklar: {stats['total_articles']}")
