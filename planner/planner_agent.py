import asyncio
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set

from domain.events import (
    Event, EventType, OrderCreated, OrderUpdated, BidRequest, BidResponse, 
    AllocationAward, ProgressUpdate, PriorityChange, ScheduleUpdated
)
from domain.models import Order, Worker, Allocation, WorkSchedule
from planner.algorithms import PriorityCalculator, Scheduler


class PlannerAgent:
    """Agente pianificatore che coordina l'assegnazione degli ordini agli operai"""
    
    def __init__(self, workers: List[Worker], config: dict, event_queue: asyncio.Queue):
        """Inizializza l'agente pianificatore
        
        Args:
            workers: Lista degli operai disponibili
            config: Configurazione del sistema
            event_queue: Coda di eventi per la comunicazione
        """
        self.workers = workers
        self.config = config
        self.event_queue = event_queue
        # Dizionari indicizzati per numero documento (doc_number)
        self.orders: Dict[str, Order] = {}
        self.active_bids: Dict[str, List[BidResponse]] = {}
        self.schedule = WorkSchedule()
        
        # Inizializza il calcolatore di priorità
        urgency_thresholds = config["priority"]["urgency_thresholds"]
        size_threshold = config["priority"]["size_threshold"]
        self.priority_calculator = PriorityCalculator(urgency_thresholds, size_threshold)
        
        # Inizializza lo scheduler
        self.scheduler = Scheduler(workers, self.priority_calculator)
    
    async def start(self) -> None:
        """Avvia l'agente pianificatore"""
        print("Avvio PlannerAgent")
        
        while True:
            # Attendi un evento dalla coda
            event = await self.event_queue.get()
            
            # Gestisci l'evento in base al tipo
            if event.type == EventType.ORDER_CREATED:
                await self.handle_order_created(event)
            elif event.type == EventType.ORDER_UPDATED:
                await self.handle_order_updated(event)
            elif event.type == EventType.BID_RESPONSE:
                await self.handle_bid_response(event)
            elif event.type == EventType.PROGRESS_UPDATE:
                await self.handle_progress_update(event)
            elif event.type == EventType.PRIORITY_CHANGE:
                await self.handle_priority_change(event)
            
            # Segnala che l'evento è stato processato
            self.event_queue.task_done()
    
    async def handle_order_created(self, event: OrderCreated) -> None:
        """Gestisce la creazione di un nuovo ordine
        
        Args:
            event: L'evento di creazione dell'ordine
        """
        # Crea un nuovo ordine
        order = Order(
            code=event.order_code,
            description=event.description,
            ordered_qty=event.ordered_qty,
            consumed_qty=event.consumed_qty,
            cycle_time=event.cycle_time,
            doc_number=event.doc_number,
            doc_date=event.doc_date,
            due_date=event.due_date,
            priority_manual=event.priority_manual
        )
        
        # Aggiungi l'ordine alla lista degli ordini indicizzato per nr. documento
        self.orders[order.doc_number] = order
        
        print(f"Nuovo ordine creato: {order.code} - {order.description}")
        
        # Avvia il processo di assegnazione
        await self.start_allocation_process(order)
    
    async def handle_order_updated(self, event: OrderUpdated) -> None:
        """Gestisce l'aggiornamento di un ordine esistente
        
        Args:
            event: L'evento di aggiornamento dell'ordine
        """
        order_code = event.doc_number
        
        # Verifica che l'ordine esista
        if order_code not in self.orders:
            print(f"Ordine non trovato: {order_code}")
            return
        
        # Aggiorna l'ordine
        order = self.orders[order_code]
        order.ordered_qty = event.ordered_qty
        order.consumed_qty = event.consumed_qty
        order.due_date = event.due_date
        
        if event.priority_manual is not None:
            order.priority_manual = event.priority_manual
        
        print(f"Ordine aggiornato: {order.code}")
        
        # Ricalcola la priorità
        order.calculated_priority = self.priority_calculator.compute_priority(
            order, date.today()
        )
        
        # Ricalcola lo schedule
        await self.recalculate_schedule()
    
    async def handle_bid_response(self, event: BidResponse) -> None:
        """Gestisce una risposta a una richiesta di offerta
        
        Args:
            event: L'evento di risposta all'offerta
        """
        order_code = event.doc_number
        
        # Verifica che l'ordine esista e che ci sia una richiesta di offerta attiva
        if order_code not in self.orders or order_code not in self.active_bids:
            return
        
        # Aggiungi la risposta alla lista delle offerte attive
        self.active_bids[order_code].append(event)
        
        # Verifica se tutti gli operai hanno risposto
        if len(self.active_bids[order_code]) == len(self.workers):
            await self.process_bids(order_code)
    
    async def handle_progress_update(self, event: ProgressUpdate) -> None:
        """Gestisce un aggiornamento del progresso di un ordine
        
        Args:
            event: L'evento di aggiornamento del progresso
        """
        order_code = event.doc_number
        
        # Verifica che l'ordine esista
        if order_code not in self.orders:
            return
        
        # Aggiorna la quantità consumata
        order = self.orders[order_code]
        order.consumed_qty += event.qty_done
        
        print(f"Progresso aggiornato per l'ordine {order_code}: {order.consumed_qty}/{order.ordered_qty}")
        
        # Verifica se l'ordine è completato
        if order.consumed_qty >= order.ordered_qty:
            print(f"Ordine completato: {order_code}")
        else:
            # Ricalcola lo schedule
            await self.recalculate_schedule()
    
    async def handle_priority_change(self, event: PriorityChange) -> None:
        """Gestisce un cambio di priorità di un ordine
        
        Args:
            event: L'evento di cambio priorità
        """
        order_code = event.doc_number
        
        # Verifica che l'ordine esista
        if order_code not in self.orders:
            return
        
        # Aggiorna la priorità manuale
        order = self.orders[order_code]
        order.priority_manual = event.new_priority
        
        print(f"Priorità aggiornata per l'ordine {order_code}: {order.priority_manual}")
        
        # Ricalcola la priorità
        order.calculated_priority = self.priority_calculator.compute_priority(
            order, date.today()
        )
        
        # Ricalcola lo schedule
        await self.recalculate_schedule()
    
    async def start_allocation_process(self, order: Order) -> None:
        """Avvia il processo di assegnazione per un ordine
        
        Args:
            order: L'ordine da assegnare
        """
        # Calcola le ore di lavoro necessarie
        work_hours = order.remaining_work_hours
        
        if work_hours <= 0:
            return
        
        # Inizializza la lista delle offerte attive
        self.active_bids[order.doc_number] = []
        
        # Crea e invia una richiesta di offerta
        request = BidRequest(
            order_code=order.code,
            doc_number=order.doc_number,
            work_hours=work_hours,
            due_date=order.due_date
        )
        
        await self.event_queue.put(request)
    
    async def process_bids(self, doc_number: str) -> None:
        """Processa le offerte ricevute per un ordine

        Args:
            doc_number: Numero documento dell'ordine
        """
        # Verifica che l'ordine esista e che ci siano offerte attive
        if doc_number not in self.orders or doc_number not in self.active_bids:
            return

        order = self.orders[doc_number]
        bids = self.active_bids[doc_number]
        
        # Ordina le offerte per capacità (decrescente)
        bids.sort(key=lambda b: b.capacity, reverse=True)
        
        # Assegna il lavoro agli operai
        remaining_hours = order.remaining_work_hours
        allocations: Dict[int, Dict[date, float]] = {}  # worker_id -> {date -> hours}
        
        for bid in bids:
            if remaining_hours <= 0:
                break
            
            worker_id = bid.worker_id
            proposed_dates = bid.proposed_dates
            
            # Inizializza le allocazioni per questo operaio
            if worker_id not in allocations:
                allocations[worker_id] = {}
            
            # Assegna ore di lavoro per ogni giorno proposto
            for day, hours in proposed_dates.items():
                if remaining_hours <= 0:
                    break
                
                allocated = min(hours, remaining_hours)
                allocations[worker_id][day] = allocated
                remaining_hours -= allocated
        
        # Invia le assegnazioni agli operai
        for worker_id, worker_allocations in allocations.items():
            if not worker_allocations:
                continue
            
            award = AllocationAward(
                order_code=order.code,
                doc_number=doc_number,
                worker_id=worker_id,
                allocations=worker_allocations
            )
            
            await self.event_queue.put(award)
        
        # Rimuovi l'ordine dalle offerte attive
        del self.active_bids[doc_number]
        
        # Notifica che lo schedule è stato aggiornato
        await self.event_queue.put(ScheduleUpdated())
    
    async def recalculate_schedule(self) -> None:
        """Ricalcola lo schedule completo"""
        # Ottieni gli ordini attivi (con quantità residua > 0)
        active_orders = [o for o in self.orders.values() if o.pending_qty > 0]
        
        # Crea un nuovo schedule
        self.schedule = self.scheduler.create_schedule(
            active_orders, date.today()
        )
        
        # Verifica se ci sono ritardi previsti
        delays = self.scheduler.check_delays(active_orders)
        
        for doc_number, delay in delays.items():
            print(f"Ritardo previsto per l'ordine {doc_number}: {delay.days} giorni")
        
        # Notifica che lo schedule è stato aggiornato
        await self.event_queue.put(ScheduleUpdated())