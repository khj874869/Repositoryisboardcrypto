from __future__ import annotations

import argparse
from collections.abc import Sequence

from sqlalchemy import Integer, create_engine, delete, select, text
from sqlalchemy.engine import Connection

from . import db


def _build_engine(database_url: str):
    engine_kwargs = {'future': True, 'pool_pre_ping': True}
    if database_url.startswith('sqlite'):
        engine_kwargs['connect_args'] = {'check_same_thread': False}
    return create_engine(database_url, **engine_kwargs)


def _copy_table_rows(source_conn: Connection, target_conn: Connection, table, batch_size: int = 500) -> int:
    rows = [dict(row) for row in source_conn.execute(select(table)).mappings()]
    if not rows:
        return 0

    for index in range(0, len(rows), batch_size):
        batch = rows[index : index + batch_size]
        target_conn.execute(table.insert(), batch)
    return len(rows)


def _reset_postgresql_sequences(target_conn: Connection) -> None:
    if target_conn.dialect.name != 'postgresql':
        return

    for table in db.metadata.sorted_tables:
        pk_columns = list(table.primary_key.columns)
        if len(pk_columns) != 1:
            continue
        pk_column = pk_columns[0]
        if not isinstance(pk_column.type, Integer):
            continue

        table_name = table.name.replace('"', '""')
        column_name = pk_column.name.replace('"', '""')
        target_conn.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('"{table_name}"', '{column_name}'),
                    COALESCE((SELECT MAX("{column_name}") FROM "{table_name}"), 1),
                    (SELECT MAX("{column_name}") IS NOT NULL FROM "{table_name}")
                )
                """
            )
        )


def migrate_database(source_url: str, target_url: str, *, reset_target: bool = False) -> dict[str, object]:
    source_engine = _build_engine(source_url)
    target_engine = _build_engine(target_url)
    copied_tables: dict[str, int] = {}

    try:
        with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
            db.metadata.create_all(target_conn)

            if reset_target:
                for table in reversed(db.metadata.sorted_tables):
                    target_conn.execute(delete(table))

            for table in db.metadata.sorted_tables:
                copied_tables[table.name] = _copy_table_rows(source_conn, target_conn, table)

            _reset_postgresql_sequences(target_conn)
    finally:
        source_engine.dispose()
        target_engine.dispose()

    return {
        'source_url': source_url,
        'target_url': target_url,
        'tables': copied_tables,
        'rows_copied': sum(copied_tables.values()),
        'reset_target': reset_target,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Copy Signal Flow data between database URLs.')
    parser.add_argument('--source-url', required=True, help='Source database URL')
    parser.add_argument('--target-url', required=True, help='Target database URL')
    parser.add_argument(
        '--reset-target',
        action='store_true',
        help='Delete existing target rows before copying source data',
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = migrate_database(args.source_url, args.target_url, reset_target=args.reset_target)

    print(f"source={result['source_url']}")
    print(f"target={result['target_url']}")
    print(f"rows_copied={result['rows_copied']}")
    for table_name, row_count in result['tables'].items():
        print(f'{table_name}={row_count}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
