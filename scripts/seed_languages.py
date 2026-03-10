"""
Seed Neo4j with Programming Language Family Tree data.

Usage:
    python scripts/seed_languages.py

Reads data/languages.json and creates Language nodes + INFLUENCED relationships in Neo4j.
"""

import json
import os
import sys

from neo4j import GraphDatabase

# ─── Configuration ──────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "codeatlas_secret")

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "languages.json")


def seed_languages():
    """Load language data into Neo4j."""
    # Load data
    with open(DATA_FILE) as f:
        data = json.load(f)

    languages = data["languages"]
    print(f"📦 Loading {len(languages)} languages into Neo4j...")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # Create constraint for unique language names
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Language) REQUIRE l.name IS UNIQUE"
        )

        # Create language nodes
        for lang in languages:
            session.run(
                """
                MERGE (l:Language {name: $name})
                SET l.year_created = $year_created,
                    l.paradigm = $paradigm,
                    l.creator = $creator
                """,
                name=lang["name"],
                year_created=lang["year_created"],
                paradigm=lang["paradigm"],
                creator=lang["creator"],
            )
            print(f"  ✅ {lang['name']} ({lang['year_created']})")

        # Create INFLUENCED relationships
        relationship_count = 0
        for lang in languages:
            for influenced in lang.get("influenced", []):
                result = session.run(
                    """
                    MATCH (a:Language {name: $from_lang})
                    MATCH (b:Language {name: $to_lang})
                    MERGE (a)-[:INFLUENCED]->(b)
                    RETURN count(*) AS created
                    """,
                    from_lang=lang["name"],
                    to_lang=influenced,
                )
                record = result.single()
                if record and record["created"] > 0:
                    relationship_count += 1

        print(f"\n🔗 Created {relationship_count} INFLUENCED relationships")

    driver.close()
    print("✨ Done seeding Neo4j!")


if __name__ == "__main__":
    try:
        seed_languages()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
