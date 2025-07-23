from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Set
from enum import Enum


class PriorityLevel(Enum):
    """Livelli di priorità per gli ordini"""
    LOW = 0
    MEDIUM_LOW = 1
    MEDIUM = 2
    MEDIUM_HIGH = 3
    HIGH = 4
    CRITICAL = 5


@dataclass
class Order:
    """Rappresenta un ordine di produzione"""
    code: str
    description: str
    ordered_qty: int
    consumed_qty: int
    cycle_time: float  # ore/pezzo
    doc_number: str
    doc_date: datetime
    due_date: datetime
    priority_manual: Optional[int] = None
    calculated_priority: PriorityLevel = PriorityLevel.MEDIUM
    
    @property
    def pending_qty(self) -> int:
        """Quantità residua da produrre"""
        return self.ordered_qty - self.consumed_qty
    
    @property
    def remaining_work_hours(self) -> float:
        """Ore di lavoro rimanenti per completare l'ordine"""
        return self.pending_qty * self.cycle_time


@dataclass
class Worker:
    """Rappresenta un operaio"""
    id: int
    name: str
    hours_per_day: float = 8.0
    skills: Set[str] = field(default_factory=set)
    # Dizionario che mappa date a ore disponibili
    availability: Dict[date, float] = field(default_factory=dict)
    
    def get_available_hours(self, day: date) -> float:
        """Restituisce le ore disponibili per una data specifica"""
        return self.availability.get(day, self.hours_per_day)
    
    def allocate_hours(self, day: date, hours: float) -> float:
        """Alloca ore di lavoro per una data specifica e restituisce le ore effettivamente allocate"""
        available = self.get_available_hours(day)
        allocated = min(available, hours)
        self.availability[day] = available - allocated
        return allocated


@dataclass
class Allocation:
    """Rappresenta un'allocazione di lavoro per un ordine a un operaio"""
    order_code: str
    worker_id: int
    allocation_date: date
    hours: float
    completed: bool = False
    
    @property
    def key(self) -> str:
        """Chiave univoca per l'allocazione"""
        return f"{self.order_code}_{self.worker_id}_{self.allocation_date.isoformat()}"


@dataclass
class WorkSchedule:
    """Rappresenta il programma di lavoro complessivo"""
    allocations: List[Allocation] = field(default_factory=list)
    
    def add_allocation(self, allocation: Allocation) -> None:
        """Aggiunge un'allocazione al programma"""
        self.allocations.append(allocation)
    
    def get_worker_schedule(self, worker_id: int) -> List[Allocation]:
        """Restituisce le allocazioni per un operaio specifico"""
        return [a for a in self.allocations if a.worker_id == worker_id]
    
    def get_order_schedule(self, order_code: str) -> List[Allocation]:
        """Restituisce le allocazioni per un ordine specifico"""
        return [a for a in self.allocations if a.order_code == order_code]
    
    def get_day_schedule(self, day: date) -> List[Allocation]:
        """Restituisce le allocazioni per un giorno specifico"""
        return [a for a in self.allocations if a.allocation_date == day]


def load_workers_from_yaml(path: str) -> List[Worker]:
    """Carica gli operai da un file YAML"""
    import yaml
    import os

    if not os.path.exists(path):
        return []

    with open(path, "r") as f:
        data = yaml.safe_load(f) or []

    workers: List[Worker] = []
    for item in data:
        worker = Worker(
            id=item.get("id"),
            name=item.get("name"),
            hours_per_day=item.get("hours_per_day", 8.0),
            skills=set(item.get("skills", [])),
        )
        workers.append(worker)

    return workers


def save_workers_to_yaml(workers: List[Worker], path: str) -> None:
    """Salva gli operai in un file YAML"""
    import yaml

    data = [
        {
            "id": w.id,
            "name": w.name,
            "hours_per_day": w.hours_per_day,
            "skills": sorted(list(w.skills)),
        }
        for w in workers
    ]

    with open(path, "w") as f:
        yaml.safe_dump(data, f, allow_unicode=True)