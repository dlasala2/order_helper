from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple

from domain.models import Order, Worker, Allocation, PriorityLevel, WorkSchedule


class PriorityCalculator:
    """Calcola la priorità degli ordini"""
    
    def __init__(self, urgency_thresholds: List[int], size_threshold: float):
        """Inizializza il calcolatore di priorità
        
        Args:
            urgency_thresholds: Soglie in giorni per urgenza [alta, media, bassa]
            size_threshold: Soglia in ore per considerare un ordine grande
        """
        self.urgency_thresholds = urgency_thresholds
        self.size_threshold = size_threshold
    
    def compute_priority(self, order: Order, today: date) -> PriorityLevel:
        """Calcola la priorità di un ordine
        
        La priorità è calcolata in base a:
        - Urgenza: giorni mancanti alla consegna
        - Dimensione: ore totali residue
        - Priorità manuale: impostata dall'utente
        
        Args:
            order: L'ordine di cui calcolare la priorità
            today: La data odierna
            
        Returns:
            Il livello di priorità calcolato (0-5)
        """
        # Priorità manuale (se impostata)
        if order.priority_manual is not None:
            return PriorityLevel(min(order.priority_manual, 5))
        
        # Calcolo dell'urgenza (0-3)
        days_left = (order.due_date.date() - today).days
        urgency = 0
        
        if days_left <= self.urgency_thresholds[0]:  # Alta urgenza
            urgency = 3
        elif days_left <= self.urgency_thresholds[1]:  # Media urgenza
            urgency = 2
        elif days_left <= self.urgency_thresholds[2]:  # Bassa urgenza
            urgency = 1
        
        # Calcolo della dimensione (0-1)
        size_hours = order.pending_qty * order.cycle_time
        size = 1 if size_hours > self.size_threshold else 0
        
        # Calcolo della priorità totale (0-5)
        raw_priority = min(urgency + size + 1, 5)  # +1 per avere un minimo di priorità
        return PriorityLevel(raw_priority)


class Scheduler:
    """Scheduler per l'assegnazione degli ordini agli operai"""
    
    def __init__(self, workers: List[Worker], priority_calculator: PriorityCalculator):
        """Inizializza lo scheduler
        
        Args:
            workers: Lista degli operai disponibili
            priority_calculator: Calcolatore di priorità
        """
        self.workers = workers
        self.priority_calculator = priority_calculator
        self.schedule = WorkSchedule()
    
    def prioritize_orders(self, orders: List[Order], today: date) -> List[Order]:
        """Calcola la priorità degli ordini e li ordina
        
        Args:
            orders: Lista degli ordini da prioritizzare
            today: Data odierna
            
        Returns:
            Lista degli ordini ordinati per priorità (decrescente) e data di consegna (crescente)
        """
        # Calcola la priorità per ogni ordine
        for order in orders:
            order.calculated_priority = self.priority_calculator.compute_priority(order, today)
        
        # Ordina gli ordini per priorità (decrescente) e data di consegna (crescente)
        return sorted(
            orders,
            key=lambda o: (5 - o.calculated_priority.value, o.due_date)
        )
    
    def create_schedule(self, orders: List[Order], start_date: date, days_ahead: int = 30) -> WorkSchedule:
        """Crea un programma di lavoro per gli ordini
        
        Args:
            orders: Lista degli ordini da schedulare
            start_date: Data di inizio della schedulazione
            days_ahead: Numero di giorni da considerare per la schedulazione
            
        Returns:
            Il programma di lavoro creato
        """
        # Prioritizza gli ordini
        prioritized_orders = self.prioritize_orders(orders, start_date)
        
        # Resetta lo schedule
        self.schedule = WorkSchedule()
        
        # Resetta la disponibilità degli operai
        for worker in self.workers:
            worker.availability = {}
        
        # Genera le date di lavoro
        work_dates = [start_date + timedelta(days=i) for i in range(days_ahead)]
        
        # Assegna gli ordini agli operai
        for order in prioritized_orders:
            remaining_hours = order.remaining_work_hours
            
            if remaining_hours <= 0:
                continue
            
            # Assegna ore di lavoro giorno per giorno
            for day in work_dates:
                if remaining_hours <= 0:
                    break
                
                # Trova gli operai che conoscono il codice
                eligible_workers = [
                    w for w in self.workers
                    if not w.skills or order.code in w.skills
                ]

                # Ordina per disponibilità
                workers_sorted = sorted(
                    eligible_workers,
                    key=lambda w: w.get_available_hours(day),
                    reverse=True
                )

                if not workers_sorted:
                    continue
                
                for worker in workers_sorted:
                    allocated = worker.allocate_hours(day, remaining_hours)
                    
                    if allocated > 0:
                        # Crea un'allocazione
                        allocation = Allocation(
                            order_code=order.code,
                            worker_id=worker.id,
                            allocation_date=day,
                            hours=allocated
                        )
                        
                        # Aggiungi l'allocazione allo schedule
                        self.schedule.add_allocation(allocation)
                        
                        # Aggiorna le ore rimanenti
                        remaining_hours -= allocated
                        
                        if remaining_hours <= 0:
                            break
        
        return self.schedule
    
    def check_delays(self, orders: List[Order]) -> Dict[str, timedelta]:
        """Verifica se ci sono ritardi previsti nella consegna degli ordini
        
        Args:
            orders: Lista degli ordini da verificare
            
        Returns:
            Dizionario che mappa i codici degli ordini ai ritardi previsti
        """
        delays = {}
        
        for order in orders:
            # Ottieni le allocazioni per questo ordine
            allocations = self.schedule.get_order_schedule(order.code)
            
            if not allocations:
                continue
            
            # Calcola la data di completamento prevista
            completion_date = max(a.allocation_date for a in allocations)
            
            # Verifica se c'è un ritardo
            if completion_date > order.due_date.date():
                delay = completion_date - order.due_date.date()
                delays[order.code] = delay
        
        return delays
    
    def get_worker_load(self) -> Dict[int, Dict[date, float]]:
        """Calcola il carico di lavoro per ogni operaio
        
        Returns:
            Dizionario che mappa gli ID degli operai a un dizionario che mappa le date alle ore di lavoro
        """
        worker_load = {worker.id: {} for worker in self.workers}
        
        for allocation in self.schedule.allocations:
            worker_id = allocation.worker_id
            day = allocation.allocation_date
            hours = allocation.hours
            
            if day not in worker_load[worker_id]:
                worker_load[worker_id][day] = 0
            
            worker_load[worker_id][day] += hours
        
        return worker_load
    
    def get_order_progress(self, orders: List[Order]) -> Dict[str, float]:
        """Calcola l'avanzamento percentuale di ciascun ordine
        
        Args:
            orders: Lista degli ordini
            
        Returns:
            Dizionario che mappa i codici degli ordini alle percentuali di avanzamento
        """
        progress = {}
        
        for order in orders:
            # Calcola le ore totali necessarie
            total_hours = order.ordered_qty * order.cycle_time
            
            if total_hours <= 0:
                progress[order.code] = 100.0
                continue
            
            # Calcola le ore già lavorate (consumate)
            consumed_hours = order.consumed_qty * order.cycle_time
            
            # Calcola la percentuale di avanzamento
            percentage = (consumed_hours / total_hours) * 100
            progress[order.code] = min(percentage, 100.0)
        
        return progress