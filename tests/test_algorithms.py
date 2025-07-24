from datetime import datetime, timedelta, date

from planner.algorithms import PriorityCalculator, Scheduler
from domain.models import Order, Worker, PriorityLevel


def test_priority_calculator():
    calc = PriorityCalculator([2, 5, 10], size_threshold=8)
    order = Order(
        code="A",
        description="test",
        ordered_qty=10,
        consumed_qty=0,
        cycle_time=1.0,
        doc_number="1",
        doc_date=datetime.now(),
        due_date=datetime.now() + timedelta(days=1),
    )
    level = calc.compute_priority(order, date.today())
    assert level == PriorityLevel.CRITICAL


def test_scheduler_creates_allocations():
    workers = [Worker(id=1, name="W1", hours_per_day=8)]
    calc = PriorityCalculator([2, 5, 10], size_threshold=8)
    scheduler = Scheduler(workers, calc)
    order = Order(
        code="A",
        description="test",
        ordered_qty=5,
        consumed_qty=0,
        cycle_time=1.0,
        doc_number="1",
        doc_date=datetime.now(),
        due_date=datetime.now() + timedelta(days=2),
    )
    schedule = scheduler.create_schedule([order], date.today(), days_ahead=3)
    assert len(schedule.allocations) > 0
