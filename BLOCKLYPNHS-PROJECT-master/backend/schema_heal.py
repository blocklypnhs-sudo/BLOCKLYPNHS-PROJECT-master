# backend/schema_heal.py
"""Repair older databases whose catalog tables are missing columns the app expects."""

OLD_NUMBER_NAMES = ('activity_number', 'assessment_no', 'activity_no', 'item_number', 'number', 'lesson_number')

# column -> (definition used when adding it, value used to fill existing rows)
EXPECTED_COLUMNS = {
    'assessment_number': ('TINYINT NOT NULL DEFAULT 0', None),   # backfilled specially
    'title': ("VARCHAR(200) NOT NULL DEFAULT ''", None),
    'description': ('TEXT NULL', ''),
    'duration_minutes': ('SMALLINT UNSIGNED NOT NULL DEFAULT 0', None),
    'points': ('SMALLINT UNSIGNED NOT NULL DEFAULT 10', None),
    'difficulty': ("VARCHAR(10) NOT NULL DEFAULT 'Easy'", None),
    'expected_output': ('TEXT NULL', ''),
    'hint': ('TEXT NULL', ''),
    'required_blocks': ('TEXT NULL', ''),
    'starter_blocks_xml': ('TEXT NULL', ''),
}


def heal_catalog_table(cursor, table):
    """Add any missing catalog columns to `table`. Returns the list of columns added."""
    cursor.execute(f"SHOW COLUMNS FROM {table}")
    existing = {row['Field'] for row in cursor.fetchall()}
    added = []
    for column, (definition, fill) in EXPECTED_COLUMNS.items():
        if column in existing:
            continue
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        added.append(column)
        if column == 'assessment_number':
            old = next((n for n in OLD_NUMBER_NAMES if n in existing), None)
            if old:
                cursor.execute(f"UPDATE {table} SET assessment_number = {old}")
            elif 'language' in existing:
                cursor.execute(f"SELECT id, language FROM {table} ORDER BY language, id")
                counters = {}
                for row in cursor.fetchall():
                    counters[row['language']] = counters.get(row['language'], 0) + 1
                    cursor.execute(
                        f"UPDATE {table} SET assessment_number = %s WHERE id = %s",
                        (counters[row['language']], row['id']),
                    )
        elif fill is not None:
            cursor.execute(f"UPDATE {table} SET {column} = %s WHERE {column} IS NULL", (fill,))
    if added:
        print(f"ℹ️ Added missing columns to {table}: {', '.join(added)}")
    return added
