from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional, Dict
from enum import Enum


class EventType(Enum):
    """Tipi di eventi nel sistema"""
    ORDER_UPDATED = "order_updated"
    ORDER_CREATED = "order_created"
    BID_REQUEST = "bid_request"
    BID_RESPONSE = "bid_response"
    ALLOCATION_AWARD = "allocation_award"
    PROGRESS_UPDATE = "progress_update"
    PRIORITY_CHANGE = "priority_change"
    SCHEDULE_UPDATED = "schedule_updated"


@dataclass
class Event:
    """Classe base per tutti gli eventi"""
    type: EventType
    timestamp: datetime = datetime.now()


class OrderEvent(Event):
    """Evento relativo a un ordine"""
    
    def __init__(self, order_code: str, type: EventType = None, timestamp: datetime = None):
        super().__init__(type=type, timestamp=timestamp or datetime.now())
        self.order_code = order_code


class OrderUpdated(OrderEvent):
    """Evento emesso quando un ordine viene aggiornato"""
    
    def __init__(self, order_code: str, ordered_qty: int, consumed_qty: int, due_date: datetime, 
                 priority_manual: Optional[int] = None, timestamp: datetime = None):
        super().__init__(order_code=order_code, type=EventType.ORDER_UPDATED, timestamp=timestamp)
        self.ordered_qty = ordered_qty
        self.consumed_qty = consumed_qty
        self.due_date = due_date
        self.priority_manual = priority_manual


class OrderCreated(OrderEvent):
    """Evento emesso quando un nuovo ordine viene creato"""
    
    def __init__(self, order_code: str, description: str, ordered_qty: int, consumed_qty: int, 
                 cycle_time: float, doc_number: str, doc_date: datetime, due_date: datetime,
                 priority_manual: Optional[int] = None, timestamp: datetime = None):
        super().__init__(order_code=order_code, type=EventType.ORDER_CREATED, timestamp=timestamp)
        self.description = description
        self.ordered_qty = ordered_qty
        self.consumed_qty = consumed_qty
        self.cycle_time = cycle_time
        self.doc_number = doc_number
        self.doc_date = doc_date
        self.due_date = due_date
        self.priority_manual = priority_manual


class BidRequest(OrderEvent):
    """Richiesta di offerta per un ordine"""
    
    def __init__(self, order_code: str, work_hours: float, due_date: datetime, timestamp: datetime = None):
        super().__init__(order_code=order_code, type=EventType.BID_REQUEST, timestamp=timestamp)
        self.work_hours = work_hours
        self.due_date = due_date


class BidResponse(OrderEvent):
    """Risposta a una richiesta di offerta"""
    
    def __init__(self, order_code: str, worker_id: int, capacity: float, proposed_dates: Dict[date, float], 
                 timestamp: datetime = None):
        super().__init__(order_code=order_code, type=EventType.BID_RESPONSE, timestamp=timestamp)
        self.worker_id = worker_id
        self.capacity = capacity
        self.proposed_dates = proposed_dates


class AllocationAward(OrderEvent):
    """Assegnazione di un ordine a un operaio"""
    
    def __init__(self, order_code: str, worker_id: int, allocations: Dict[date, float], timestamp: datetime = None):
        super().__init__(order_code=order_code, type=EventType.ALLOCATION_AWARD, timestamp=timestamp)
        self.worker_id = worker_id
        self.allocations = allocations


class ProgressUpdate(OrderEvent):
    """Aggiornamento del progresso di un ordine"""
    
    def __init__(self, order_code: str, worker_id: int, qty_done: int, allocation_date: date, timestamp: datetime = None):
        super().__init__(order_code=order_code, type=EventType.PROGRESS_UPDATE, timestamp=timestamp)
        self.worker_id = worker_id
        self.qty_done = qty_done
        self.allocation_date = allocation_date


class PriorityChange(OrderEvent):
    """Cambio di priorità di un ordine"""
    
    def __init__(self, order_code: str, new_priority: int, timestamp: datetime = None):
        super().__init__(order_code=order_code, type=EventType.PRIORITY_CHANGE, timestamp=timestamp)
        self.new_priority = new_priority


class ScheduleUpdated(Event):
    """Evento emesso quando il programma di lavoro viene aggiornato"""
    def __init__(self, timestamp: datetime = None):
        super().__init__(type=EventType.SCHEDULE_UPDATED, timestamp=timestamp)