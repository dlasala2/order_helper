import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Iterable, List

from domain.models import Order, Worker


class Database:
    """Semplice database SQLite per ordini e operai."""

    def __init__(self, path: str = "./data/schedule.db"):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self._create_tables()

    def _create_tables(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                doc_number TEXT PRIMARY KEY,
                code TEXT,
                description TEXT,
                ordered_qty INTEGER,
                consumed_qty INTEGER,
                cycle_time REAL,
                doc_date TEXT,
                due_date TEXT,
                priority_manual INTEGER
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY,
                name TEXT,
                hours_per_day REAL
            )
            """
        )
        self.conn.commit()

    def save_orders(self, orders: Iterable[Order]) -> None:
        cur = self.conn.cursor()
        for o in orders:
            cur.execute(
                """
                INSERT INTO orders (doc_number, code, description, ordered_qty, consumed_qty,
                                    cycle_time, doc_date, due_date, priority_manual)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_number) DO UPDATE SET
                    code=excluded.code,
                    description=excluded.description,
                    ordered_qty=excluded.ordered_qty,
                    consumed_qty=excluded.consumed_qty,
                    cycle_time=excluded.cycle_time,
                    doc_date=excluded.doc_date,
                    due_date=excluded.due_date,
                    priority_manual=excluded.priority_manual
                """,
                (
                    o.doc_number,
                    o.code,
                    o.description,
                    o.ordered_qty,
                    o.consumed_qty,
                    o.cycle_time,
                    o.doc_date.isoformat(),
                    o.due_date.isoformat(),
                    o.priority_manual,
                ),
            )
        self.conn.commit()

    def save_workers(self, workers: Iterable[Worker]) -> None:
        cur = self.conn.cursor()
        for w in workers:
            cur.execute(
                """
                INSERT INTO workers (id, name, hours_per_day)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    hours_per_day=excluded.hours_per_day
                """,
                (w.id, w.name, w.hours_per_day),
            )
        self.conn.commit()

    def load_orders(self) -> List[Order]:
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT doc_number, code, description, ordered_qty, consumed_qty, cycle_time, doc_date, due_date, priority_manual FROM orders"
        ).fetchall()
        orders = []
        for r in rows:
            orders.append(
                Order(
                    code=r[1],
                    description=r[2],
                    ordered_qty=r[3],
                    consumed_qty=r[4],
                    cycle_time=r[5],
                    doc_number=r[0],
                    doc_date=datetime.fromisoformat(r[6]),
                    due_date=datetime.fromisoformat(r[7]),
                    priority_manual=r[8],
                )
            )
        return orders

    def load_workers(self) -> List[Worker]:
        cur = self.conn.cursor()
        rows = cur.execute("SELECT id, name, hours_per_day FROM workers").fetchall()
        return [Worker(id=r[0], name=r[1], hours_per_day=r[2]) for r in rows]
