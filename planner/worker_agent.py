import asyncio
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set

from domain.events import BidRequest, BidResponse, AllocationAward, ProgressUpdate, Event, EventType
from domain.models import Worker, Allocation


class WorkerAgent:
    """Agente che rappresenta un operaio nel sistema"""
    
    def __init__(self, worker: Worker, event_queue: asyncio.Queue, days_ahead: int = 30):
        """Inizializza l'agente operaio
        
        Args:
            worker: L'operaio rappresentato dall'agente
            event_queue: Coda di eventi per la comunicazione
            days_ahead: Numero di giorni da considerare per la pianificazione
        """
        self.worker = worker
        self.event_queue = event_queue
        self.days_ahead = days_ahead
        self.allocations: List[Allocation] = []
        self.active_bids: Set[str] = set()  # Codici degli ordini per cui è stata fatta un'offerta
    
    async def start(self) -> None:
        """Avvia l'agente operaio"""
        print(f"Avvio WorkerAgent per operaio {self.worker.id} - {self.worker.name}")
        
        while True:
            # Attendi un evento dalla coda
            event = await self.event_queue.get()
            
            # Gestisci l'evento in base al tipo
            if event.type == EventType.BID_REQUEST:
                await self.handle_bid_request(event)
            elif event.type == EventType.ALLOCATION_AWARD:
                await self.handle_allocation_award(event)
            
            # Segnala che l'evento è stato processato
            self.event_queue.task_done()
    
    async def handle_bid_request(self, event: BidRequest) -> None:
        """Gestisce una richiesta di offerta
        
        Args:
            event: L'evento di richiesta di offerta
        """
        order_code = event.order_code
        work_hours = event.work_hours
        due_date = event.due_date

        # Verifica se l'operaio conosce il codice
        if self.worker.skills and order_code not in self.worker.skills:
            return
        
        # Aggiungi l'ordine alle offerte attive
        self.active_bids.add(order_code)
        
        # Calcola la capacità disponibile fino alla data di consegna
        today = date.today()
        end_date = min(due_date.date(), today + timedelta(days=self.days_ahead))
        
        # Genera le date di lavoro
        work_dates = [today + timedelta(days=i) for i in range((end_date - today).days + 1)]
        
        # Calcola la disponibilità per ogni giorno
        proposed_dates: Dict[date, float] = {}
        remaining_hours = work_hours
        
        for day in work_dates:
            available_hours = self.worker.get_available_hours(day)
            
            if available_hours > 0:
                allocated = min(available_hours, remaining_hours)
                proposed_dates[day] = allocated
                remaining_hours -= allocated
                
                if remaining_hours <= 0:
                    break
        
        # Calcola la capacità totale disponibile
        total_capacity = sum(proposed_dates.values())
        
        # Crea e invia la risposta all'offerta
        response = BidResponse(
            order_code=order_code,
            worker_id=self.worker.id,
            capacity=total_capacity,
            proposed_dates=proposed_dates
        )
        
        await self.event_queue.put(response)
    
    async def handle_allocation_award(self, event: AllocationAward) -> None:
        """Gestisce un'assegnazione di lavoro
        
        Args:
            event: L'evento di assegnazione
        """
        order_code = event.order_code
        worker_id = event.worker_id
        allocations = event.allocations
        
        # Verifica che l'assegnazione sia per questo operaio
        if worker_id != self.worker.id:
            return
        
        # Rimuovi l'ordine dalle offerte attive
        self.active_bids.discard(order_code)
        
        # Aggiorna la disponibilità dell'operaio
        for day, hours in allocations.items():
            available = self.worker.get_available_hours(day)
            self.worker.availability[day] = available - hours
            
            # Crea un'allocazione
            allocation = Allocation(
                order_code=order_code,
                worker_id=self.worker.id,
                allocation_date=day,
                hours=hours
            )
            
            self.allocations.append(allocation)
        
        print(f"Operaio {self.worker.id} ha ricevuto un'assegnazione per l'ordine {order_code}")
    
    async def report_progress(self, order_code: str, qty_done: int, allocation_date: date) -> None:
        """Riporta il progresso di un ordine
        
        Args:
            order_code: Codice dell'ordine
            qty_done: Quantità prodotta
            allocation_date: Data dell'allocazione
        """
        # Crea e invia un evento di aggiornamento del progresso
        update = ProgressUpdate(
            order_code=order_code,
            worker_id=self.worker.id,
            qty_done=qty_done,
            allocation_date=allocation_date
        )
        
        await self.event_queue.put(update)
        
        # Aggiorna lo stato dell'allocazione
        for allocation in self.allocations:
            if (allocation.order_code == order_code and 
                allocation.allocation_date == allocation_date):
                allocation.completed = True
                break