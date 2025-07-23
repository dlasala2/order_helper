import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
import yaml

from domain.events import OrderCreated, OrderUpdated
from domain.models import Order


class ExcelMonitor:
    """Monitora un file Excel e genera eventi quando ci sono cambiamenti"""
    
    def __init__(self, config_path: str = "config.yaml", event_queue: Optional[asyncio.Queue] = None):
        """Inizializza il monitor Excel
        
        Args:
            config_path: Percorso del file di configurazione
            event_queue: Coda di eventi asyncio per la comunicazione con altri componenti
        """
        self.config_path = config_path
        self.event_queue = event_queue or asyncio.Queue()
        self.config = self._load_config()
        self.excel_path = self.config["excel"]["path"]
        self.sheet_name = self.config["excel"]["sheet_name"]
        self.poll_interval = self.config["excel"]["poll_interval_minutes"] * 60  # Converti in secondi
        self.default_cycle_time = self.config["resources"]["default_cycle_time"]
        self.last_modified_time = 0
        self.known_orders: Dict[str, Order] = {}
        
    def _load_config(self) -> dict:
        """Carica la configurazione dal file YAML"""
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)
    
    def _get_file_modified_time(self) -> float:
        """Ottiene il timestamp di ultima modifica del file Excel"""
        if not os.path.exists(self.excel_path):
            return 0
        return os.path.getmtime(self.excel_path)
    
    def _parse_excel(self) -> List[Order]:
        """Legge il file Excel e converte le righe in oggetti Order"""
        try:
            df = pd.read_excel(self.excel_path, sheet_name=self.sheet_name)
            orders = []
            
            # Mappatura delle colonne Excel ai campi dell'oggetto Order
            for _, row in df.iterrows():
                # Gestisci i valori mancanti
                cycle_time = row.get("Ore_Pezzo", self.default_cycle_time)
                if pd.isna(cycle_time):
                    cycle_time = self.default_cycle_time
                
                priority_manual = row.get("PriorityManual", None)
                if pd.isna(priority_manual):
                    priority_manual = None
                else:
                    priority_manual = int(priority_manual)
                
                # Crea l'oggetto Order
                order = Order(
                    code=row["Codice"],
                    description=row["Descrizione"],
                    ordered_qty=int(row["Ordinato"]),
                    consumed_qty=int(row["Da cons."]),
                    cycle_time=float(cycle_time),
                    doc_number=str(row["Nr. doc."]),
                    doc_date=pd.to_datetime(row["Data Doc."], dayfirst=True).to_pydatetime(),
                    due_date=pd.to_datetime(row["Consegna"], dayfirst=True).to_pydatetime(),
                    priority_manual=priority_manual
                )
                orders.append(order)
            
            return orders
        except Exception as e:
            print(f"Errore durante la lettura del file Excel: {e}")
            return []
    
    def _detect_changes(self, current_orders: List[Order]) -> None:
        """Rileva cambiamenti negli ordini e genera eventi appropriati"""
        current_order_dict = {order.code: order for order in current_orders}
        current_codes = set(current_order_dict.keys())
        known_codes = set(self.known_orders.keys())
        
        # Nuovi ordini
        new_codes = current_codes - known_codes
        for code in new_codes:
            order = current_order_dict[code]
            event = OrderCreated(
                order_code=order.code,
                description=order.description,
                ordered_qty=order.ordered_qty,
                consumed_qty=order.consumed_qty,
                cycle_time=order.cycle_time,
                doc_number=order.doc_number,
                doc_date=order.doc_date,
                due_date=order.due_date,
                priority_manual=order.priority_manual
            )
            asyncio.create_task(self.event_queue.put(event))
        
        # Ordini aggiornati
        updated_codes = current_codes.intersection(known_codes)
        for code in updated_codes:
            current = current_order_dict[code]
            known = self.known_orders[code]
            
            # Verifica se ci sono cambiamenti
            if (current.ordered_qty != known.ordered_qty or
                current.consumed_qty != known.consumed_qty or
                current.due_date != known.due_date or
                current.priority_manual != known.priority_manual):
                
                event = OrderUpdated(
                    order_code=current.code,
                    ordered_qty=current.ordered_qty,
                    consumed_qty=current.consumed_qty,
                    due_date=current.due_date,
                    priority_manual=current.priority_manual
                )
                asyncio.create_task(self.event_queue.put(event))
        
        # Aggiorna gli ordini conosciuti
        self.known_orders = current_order_dict
    
    async def start_monitoring(self) -> None:
        """Avvia il monitoraggio del file Excel"""
        print(f"Avvio monitoraggio del file Excel: {self.excel_path}")
        
        while True:
            current_modified_time = self._get_file_modified_time()
            
            # Verifica se il file è stato modificato
            if current_modified_time > self.last_modified_time:
                print(f"Rilevata modifica del file Excel: {datetime.now()}")
                orders = self._parse_excel()
                self._detect_changes(orders)
                self.last_modified_time = current_modified_time
            
            # Attendi prima del prossimo controllo
            await asyncio.sleep(self.poll_interval)
    
    def ensure_data_directory(self) -> None:
        """Assicura che la directory dei dati esista"""
        data_dir = Path(self.excel_path).parent
        os.makedirs(data_dir, exist_ok=True)