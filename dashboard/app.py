import asyncio
import os
import sys
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set
from pathlib import Path

# Aggiungi la directory principale al PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st
import yaml
import plotly.express as px
import plotly.graph_objects as go

from domain.events import (
    Event,
    EventType,
    ScheduleUpdated,
    ProgressUpdate,
    PriorityChange,
)
from domain.models import Order, Worker, Allocation, PriorityLevel, WorkSchedule
from planner.algorithms import Scheduler


class Dashboard:
    """Dashboard per visualizzare lo stato del sistema"""
    
    def __init__(self, config_path: str = "config.yaml", event_queue: Optional[asyncio.Queue] = None):
        """Inizializza la dashboard
        
        Args:
            config_path: Percorso del file di configurazione
            event_queue: Coda di eventi per la comunicazione
        """
        self.config_path = config_path
        self.event_queue = event_queue or asyncio.Queue()
        self.config = self._load_config()
        self.refresh_interval = self.config["dashboard"]["refresh_interval_seconds"]
        self.orders: Dict[str, Order] = {}
        self.workers_file = self.config["resources"].get("workers_file")
        if self.workers_file and os.path.exists(self.workers_file):
            from domain.models import load_workers_from_yaml
            self.workers = load_workers_from_yaml(self.workers_file)
        else:
            self.workers: List[Worker] = []
        self.schedule = WorkSchedule()
        self.delays: Dict[str, timedelta] = {}
        self.progress: Dict[str, float] = {}
        self.worker_load: Dict[int, Dict[date, float]] = {}
        self.last_update = datetime.now()
    
    def _load_config(self) -> dict:
        """Carica la configurazione dal file YAML"""
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)
    
    async def start_event_listener(self) -> None:
        """Avvia l'ascolto degli eventi"""
        print("Avvio listener eventi per la dashboard")
        
        while True:
            # Attendi un evento dalla coda
            event = await self.event_queue.get()
            
            # Gestisci l'evento in base al tipo
            if event.type == EventType.SCHEDULE_UPDATED:
                self.last_update = datetime.now()
            
            # Segnala che l'evento è stato processato
            self.event_queue.task_done()
    
    def update_data(self, orders: Dict[str, Order], workers: List[Worker], 
                    schedule: WorkSchedule, delays: Dict[str, timedelta], 
                    progress: Dict[str, float], worker_load: Dict[int, Dict[date, float]]) -> None:
        """Aggiorna i dati della dashboard
        
        Args:
            orders: Dizionario degli ordini
            workers: Lista degli operai
            schedule: Programma di lavoro
            delays: Dizionario dei ritardi previsti
            progress: Dizionario dell'avanzamento degli ordini
            worker_load: Dizionario del carico di lavoro degli operai
        """
        self.orders = orders
        self.workers = workers
        self.schedule = schedule
        self.delays = delays
        self.progress = progress
        self.worker_load = worker_load
        self.last_update = datetime.now()
    
    def run(self) -> None:
        """Avvia l'applicazione Streamlit"""
        st.set_page_config(
            page_title="Scadenziario Ordini",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.title("📊 Scadenziario Ordini di Produzione")
        
        # Sidebar
        st.sidebar.header("Filtri e Controlli")
        
        # Aggiungi un pulsante per la riallocazione manuale degli operai
        st.sidebar.subheader("Gestione Allocazioni")
        if st.sidebar.button("Ottimizza Allocazioni Operai"):
            st.sidebar.success("Ottimizzazione allocazioni avviata. Controlla la tab 'Alert e Notifiche' per i suggerimenti.")
        
        # Aggiorna i dati
        if st.sidebar.button("Aggiorna dati"):
            st.rerun()
        
        st.sidebar.info(f"Ultimo aggiornamento: {self.last_update.strftime('%d/%m/%Y %H:%M:%S')}")
        
        # Tabs
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📋 Ordini",
            "👷 Carico Operai",
            "⚠️ Alert",
            "📈 Avanzamento",
            "📆 Gantt",
            "👥 Gestione Operai",
        ])
        
        # Tab 1: Ordini
        with tab1:
            self._render_orders_tab()
        
        # Tab 2: Carico Operai
        with tab2:
            self._render_worker_load_tab()
        
        # Tab 3: Alert
        with tab3:
            self._render_alerts_tab()
        
        # Tab 4: Avanzamento
        with tab4:
            self._render_progress_tab()

        # Tab 5: Gantt
        with tab5:
            self._render_gantt_tab()

        # Tab 6: Gestione Operai
        with tab6:
            self._render_workers_tab()
    
    def _render_orders_tab(self) -> None:
        """Renderizza la tab degli ordini"""
        st.header("📋 Ordini di Produzione")
        
        if not self.orders:
            st.info("Nessun ordine disponibile")
            return
        
        # Crea un DataFrame con gli ordini
        orders_data = []
        
        for order in self.orders.values():
            # Determina l'operaio con più ore assegnate all'ordine
            allocations = self.schedule.get_order_schedule(order.doc_number)
            worker_name = "-"
            if allocations:
                hours_by_worker: Dict[int, float] = {}
                for alloc in allocations:
                    hours_by_worker[alloc.worker_id] = hours_by_worker.get(alloc.worker_id, 0) + alloc.hours
                best_id = max(hours_by_worker, key=hours_by_worker.get)
                for w in self.workers:
                    if w.id == best_id:
                        worker_name = w.name
                        break

            orders_data.append({
                "Codice": order.code,
                "Descrizione": order.description,
                "Ordinato": order.ordered_qty,
                "Consumato": order.consumed_qty,
                "Residuo": order.pending_qty,
                "Ore/Pezzo": order.cycle_time,
                "Ore Residue": order.remaining_work_hours,
                "Nr. Doc.": order.doc_number,
                "Data Doc.": order.doc_date.strftime("%d/%m/%Y"),
                "Consegna": order.due_date.strftime("%d/%m/%Y"),
                "Priorità": order.calculated_priority.value,
                "Priorità Man.": str(order.priority_manual) if order.priority_manual is not None else "-",
                "Operaio": worker_name,
            })
        
        df_orders = pd.DataFrame(orders_data)
        
        # Filtri
        col1, col2 = st.columns(2)
        
        with col1:
            priority_filter = st.multiselect(
                "Filtra per priorità",
                options=list(range(6)),
                default=list(range(6)),
                key="orders_priority_filter"
            )
        
        with col2:
            search = st.text_input("Cerca per codice o descrizione")
        
        # Applica i filtri
        filtered_df = df_orders[
            (df_orders["Priorità"].isin(priority_filter)) &
            (df_orders["Codice"].str.contains(search, case=False) |
             df_orders["Descrizione"].str.contains(search, case=False))
        ]
        
        # Ordina per priorità (decrescente) e data di consegna (crescente)
        filtered_df = filtered_df.sort_values(
            by=["Priorità", "Consegna"],
            ascending=[False, True]
        )
        
        # Visualizza la tabella
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True
        )

        # Form per aggiornare la priorità manuale
        st.subheader("Imposta Priorità Manuale")
        with st.form("priority_form"):
            priority_inputs = {}

            for _, row in filtered_df.iterrows():
                doc_number = row["Nr. Doc."]
                order_obj = self.orders.get(doc_number)
                current_priority = order_obj.priority_manual
                if current_priority is None:
                    current_priority = order_obj.calculated_priority.value

                priority_inputs[doc_number] = st.number_input(
                    label=f"{doc_number}",
                    min_value=0,
                    max_value=5,
                    step=1,
                    value=int(current_priority),
                    key=f"priority_input_{doc_number}"
                )

            submitted = st.form_submit_button("Aggiorna Priorità")
            if submitted:
                for doc_number, new_val in priority_inputs.items():
                    new_priority = int(new_val)
                    order = self.orders.get(doc_number)
                    if order is None:
                        continue
                    order.priority_manual = new_priority
                    order.calculated_priority = PriorityLevel(min(new_priority, 5))

                    try:
                        asyncio.run(self.event_queue.put(PriorityChange(order.code, doc_number, new_priority)))
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(self.event_queue.put(PriorityChange(order.code, doc_number, new_priority)))
                        loop.close()
                st.success("Priorità aggiornate")

    
    def _render_worker_load_tab(self) -> None:
        """Renderizza la tab del carico operai"""
        st.header("👷 Carico di Lavoro Operai")
        
        if not self.workers or not self.worker_load:
            st.info("Nessun dato disponibile sul carico di lavoro")
            return
        
        # Crea un DataFrame con il carico di lavoro
        load_data = []
        
        today = date.today()
        days_ahead = 30
        dates = [today + timedelta(days=i) for i in range(days_ahead)]
        
        for worker in self.workers:
            worker_id = worker.id
            worker_name = worker.name
            hours_per_day = worker.hours_per_day
            
            for day in dates:
                load = self.worker_load.get(worker_id, {}).get(day, 0)
                utilization = (load / hours_per_day) * 100 if hours_per_day > 0 else 0
                
                load_data.append({
                    "Operaio ID": worker_id,
                    "Operaio": worker_name,
                    "Data": day,
                    "Ore Allocate": load,
                    "Ore Disponibili": hours_per_day,
                    "Utilizzo %": utilization
                })
        
        df_load = pd.DataFrame(load_data)
        
        # Filtri
        col1, col2 = st.columns(2)
        
        with col1:
            worker_filter = st.multiselect(
                "Filtra per operaio",
                options=[w.name for w in self.workers],
                default=[w.name for w in self.workers],
                key="worker_load_filter"
            )
        
        with col2:
            date_range = st.slider(
                "Intervallo di date",
                min_value=0,
                max_value=days_ahead - 1,
                value=(0, 14)
            )
        
        # Applica i filtri
        start_date = today + timedelta(days=date_range[0])
        end_date = today + timedelta(days=date_range[1])
        
        filtered_df = df_load[
            (df_load["Operaio"].isin(worker_filter)) &
            (df_load["Data"] >= start_date) &
            (df_load["Data"] <= end_date)
        ]
        
        # Grafico del carico di lavoro
        fig = px.bar(
            filtered_df,
            x="Data",
            y="Ore Allocate",
            color="Operaio",
            barmode="group",
            title="Carico di Lavoro Giornaliero",
            labels={
                "Data": "Data",
                "Ore Allocate": "Ore Allocate",
                "Operaio": "Operaio"
            }
        )
        
        # Aggiungi linee per le ore disponibili
        for worker in self.workers:
            if worker.name in worker_filter:
                fig.add_trace(
                    go.Scatter(
                        x=[start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)],
                        y=[worker.hours_per_day] * ((end_date - start_date).days + 1),
                        mode="lines",
                        name=f"{worker.name} - Disponibilità",
                        line=dict(dash="dash")
                    )
                )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabella del carico di lavoro
        st.subheader("Dettaglio Carico di Lavoro")
        
        # Pivot table per visualizzare il carico per operaio e data
        pivot_df = filtered_df.pivot_table(
            index="Operaio",
            columns="Data",
            values="Ore Allocate",
            aggfunc="sum"
        ).fillna(0)
        
        st.dataframe(
            pivot_df,
            use_container_width=True
        )
    
    def _render_alerts_tab(self) -> None:
        """Renderizza la tab degli alert"""
        st.header("⚠️ Alert e Notifiche")
        
        # Alert per ritardi previsti
        st.subheader("Ritardi Previsti")
        
        if not self.delays:
            st.success("Nessun ritardo previsto")
        else:
            alerts_data = []
            
            for order_code, delay in self.delays.items():
                if order_code not in self.orders:
                    continue
                
                order = self.orders[order_code]
                
                alerts_data.append({
                    "Codice": order.code,
                    "Descrizione": order.description,
                    "Consegna": order.due_date.strftime("%d/%m/%Y"),
                    "Ritardo Previsto (giorni)": delay.days,
                    "Priorità": order.calculated_priority.value
                })
            
            df_alerts = pd.DataFrame(alerts_data)
            
            # Ordina per ritardo (decrescente) e priorità (decrescente)
            df_alerts = df_alerts.sort_values(
                by=["Ritardo Previsto (giorni)", "Priorità"],
                ascending=[False, False]
            )
            
            # Visualizza la tabella
            st.dataframe(
                df_alerts,
                use_container_width=True,
                hide_index=True
            )
        
        # Suggerimenti di coordinamento
        st.subheader("Suggerimenti di Coordinamento")
        
        # Identifica i momenti ottimali di interazione con altri reparti
        if not self.orders or not self.schedule.allocations:
            st.info("Dati insufficienti per generare suggerimenti")
        else:
            # Trova gli ordini con priorità alta
            high_priority_orders = [o for o in self.orders.values() 
                                  if o.calculated_priority.value >= 4 and o.pending_qty > 0]
            
            if not high_priority_orders:
                st.info("Nessun ordine ad alta priorità da coordinare")
            else:
                suggestions = []
                
                for order in high_priority_orders:
                    # Calcola la data di inizio produzione
                    order_allocations = self.schedule.get_order_schedule(order.doc_number)
                    if not order_allocations:
                        continue
                    
                    start_date = min(a.allocation_date for a in order_allocations)
                    end_date = max(a.allocation_date for a in order_allocations)
                    
                    # Genera suggerimenti
                    if (start_date - date.today()).days <= 2:
                        suggestions.append({
                            "Codice": order.code,
                            "Descrizione": order.description,
                            "Reparto": "Acquisti",
                            "Azione": "Verificare disponibilità materiali",
                            "Data Ottimale": date.today().strftime("%d/%m/%Y"),
                            "Urgenza": "Alta"
                        })
                    
                    if (end_date - date.today()).days <= 5:
                        suggestions.append({
                            "Codice": order.code,
                            "Descrizione": order.description,
                            "Reparto": "Collaudo",
                            "Azione": "Pianificare collaudo",
                            "Data Ottimale": end_date.strftime("%d/%m/%Y"),
                            "Urgenza": "Media"
                        })
                
                if not suggestions:
                    st.info("Nessun suggerimento di coordinamento disponibile")
                else:
                    df_suggestions = pd.DataFrame(suggestions)
                    
                    # Visualizza la tabella
                    st.dataframe(
                        df_suggestions,
                        use_container_width=True,
                        hide_index=True
                    )
        
        # Suggerimenti per allocazione operai
        st.subheader("Suggerimenti per Allocazione Operai")
        
        if not self.workers or not self.worker_load or not self.orders:
            st.info("Dati insufficienti per generare suggerimenti di allocazione")
        else:
            # Analizza il carico di lavoro attuale
            today = date.today()
            next_week = [today + timedelta(days=i) for i in range(7)]
            
            # Trova operai con basso carico di lavoro
            underutilized_workers = []
            for worker in self.workers:
                worker_id = worker.id
                avg_utilization = 0
                days_count = 0
                
                for day in next_week:
                    load = self.worker_load.get(worker_id, {}).get(day, 0)
                    utilization = (load / worker.hours_per_day) * 100 if worker.hours_per_day > 0 else 0
                    avg_utilization += utilization
                    days_count += 1
                
                if days_count > 0:
                    avg_utilization /= days_count
                    
                    if avg_utilization < 70:  # Soglia di sottoutilizzo
                        underutilized_workers.append({
                            "worker_id": worker_id,
                            "worker_name": worker.name,
                            "avg_utilization": avg_utilization,
                            "available_capacity": worker.hours_per_day * 7 - sum(self.worker_load.get(worker_id, {}).get(day, 0) for day in next_week)
                        })
            
            # Trova ordini in ritardo o ad alta priorità che potrebbero beneficiare di più operai
            critical_orders = []
            for order_code, delay in self.delays.items():
                if order_code in self.orders and delay.days > 0:
                    order = self.orders[order_code]
                    critical_orders.append({
                        "order_code": order.code,
                        "description": order.description,
                        "delay_days": delay.days,
                        "priority": order.calculated_priority.value,
                        "remaining_hours": order.remaining_work_hours
                    })
            
            # Ordina per ritardo e priorità
            critical_orders.sort(key=lambda x: (x["delay_days"], x["priority"]), reverse=True)
            
            # Genera suggerimenti di allocazione
            allocation_suggestions = []
            
            for worker_data in underutilized_workers:
                available_capacity = worker_data["available_capacity"]
                
                for order_data in critical_orders:
                    if available_capacity > 0 and order_data["remaining_hours"] > 0:
                        # Calcola quante ore allocare
                        hours_to_allocate = min(available_capacity, order_data["remaining_hours"])
                        
                        # Calcola l'impatto sul ritardo
                        days_saved = round(hours_to_allocate / 8, 1)  # Approssimazione
                        
                        allocation_suggestions.append({
                            "Operaio": worker_data["worker_name"],
                            "Utilizzo Attuale": f"{worker_data['avg_utilization']:.1f}%",
                            "Codice Ordine": order_data["order_code"],
                            "Descrizione": order_data["description"],
                            "Ritardo Attuale": order_data["delay_days"],
                            "Ore da Allocare": round(hours_to_allocate, 1),
                            "Giorni Risparmiati": days_saved,
                            "Priorità": order_data["priority"]
                        })
                        
                        # Aggiorna le capacità disponibili
                        available_capacity -= hours_to_allocate
                        order_data["remaining_hours"] -= hours_to_allocate
            
            if not allocation_suggestions:
                st.info("Nessun suggerimento di allocazione disponibile")
            else:
                df_allocations = pd.DataFrame(allocation_suggestions)
                
                # Visualizza la tabella
                st.dataframe(
                    df_allocations,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Visualizza un grafico che mostra l'impatto delle allocazioni suggerite
                if len(df_allocations) > 0:
                    fig = px.bar(
                        df_allocations,
                        x="Codice Ordine",
                        y="Giorni Risparmiati",
                        color="Operaio",
                        title="Impatto delle Allocazioni Suggerite (Giorni Risparmiati)",
                        labels={
                            "Codice Ordine": "Codice Ordine",
                            "Giorni Risparmiati": "Giorni Risparmiati",
                            "Operaio": "Operaio"
                        }
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
    
    def _render_progress_tab(self) -> None:
        """Renderizza la tab dell'avanzamento"""
        st.header("📈 Avanzamento Ordini")

        if not self.orders:
            st.info("Nessun dato disponibile sull'avanzamento")
            return

        # Form per inserire un avanzamento manuale
        st.subheader("Aggiorna Avanzamento")
        with st.form("progress_update_form"):
            order_code = st.selectbox(
                "Nr. Documento", options=sorted(self.orders.keys())
            )
            worker_option = st.selectbox(
                "Operaio",
                options=[(w.id, w.name) for w in self.workers],
                format_func=lambda x: f"{x[0]} - {x[1]}",
            )
            qty_done = st.number_input("Quantità prodotta", min_value=0, step=1)
            done_date = st.date_input("Data", value=date.today())
            submitted = st.form_submit_button("Aggiorna")

        if submitted and qty_done > 0:
            update = ProgressUpdate(
                order_code=self.orders[order_code].code,
                doc_number=order_code,
                worker_id=worker_option[0],
                qty_done=int(qty_done),
                allocation_date=done_date,
            )

            try:
                self.event_queue.put_nowait(update)
            except Exception:
                asyncio.create_task(self.event_queue.put(update))

            # Aggiorna lo stato locale dell'ordine
            order = self.orders[order_code]
            order.consumed_qty += int(qty_done)
            total_hours = order.ordered_qty * order.cycle_time
            if total_hours <= 0:
                percentage = 100.0
            else:
                consumed_hours = order.consumed_qty * order.cycle_time
                percentage = min((consumed_hours / total_hours) * 100, 100.0)
            self.progress[order_code] = percentage
            st.success("Avanzamento registrato")
        
        # Crea un DataFrame con l'avanzamento
        progress_data = []
        
        for order_code, percentage in self.progress.items():
            if order_code not in self.orders:
                continue
            
            order = self.orders[order_code]
            
            progress_data.append({
                "Codice": order.code,
                "Descrizione": order.description,
                "Avanzamento %": percentage,
                "Ordinato": order.ordered_qty,
                "Consumato": order.consumed_qty,
                "Residuo": order.pending_qty,
                "Consegna": order.due_date.strftime("%d/%m/%Y"),
                "Priorità": order.calculated_priority.value
            })
        
        df_progress = pd.DataFrame(progress_data)
        
        # Filtri
        col1, col2 = st.columns(2)
        
        with col1:
            progress_filter = st.slider(
                "Filtra per avanzamento",
                min_value=0.0,
                max_value=100.0,
                value=(0.0, 100.0),
                step=5.0
            )
        
        with col2:
            priority_filter = st.multiselect(
                "Filtra per priorità",
                options=list(range(6)),
                default=list(range(6)),
                key="progress_priority_filter"
            )
        
        # Applica i filtri
        filtered_df = df_progress[
            (df_progress["Avanzamento %"] >= progress_filter[0]) &
            (df_progress["Avanzamento %"] <= progress_filter[1]) &
            (df_progress["Priorità"].isin(priority_filter))
        ]
        
        # Ordina per avanzamento (crescente) e priorità (decrescente)
        filtered_df = filtered_df.sort_values(
            by=["Avanzamento %", "Priorità"],
            ascending=[True, False]
        )
        
        # Grafico dell'avanzamento
        fig = px.bar(
            filtered_df,
            x="Codice",
            y="Avanzamento %",
            color="Priorità",
            hover_data=["Descrizione", "Ordinato", "Consumato", "Residuo", "Consegna"],
            title="Avanzamento Percentuale degli Ordini",
            labels={
                "Codice": "Codice Ordine",
                "Avanzamento %": "Avanzamento (%)",
                "Priorità": "Priorità"
            }
        )
        
        # Aggiungi una linea al 100%
        fig.add_shape(
            type="line",
            x0=-0.5,
            y0=100,
            x1=len(filtered_df) - 0.5,
            y1=100,
            line=dict(color="red", width=2, dash="dash")
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabella dell'avanzamento
        st.subheader("Dettaglio Avanzamento")
        
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True
        )

    def _render_gantt_tab(self) -> None:
        """Visualizza lo schedule in formato Gantt"""
        st.header("📆 Pianificazione Gantt")

        if not self.schedule.allocations:
            st.info("Nessuna allocazione disponibile")
            return

        data = []
        for alloc in self.schedule.allocations:
            order = self.orders.get(alloc.doc_number)
            worker = next((w for w in self.workers if w.id == alloc.worker_id), None)
            if not order or not worker:
                continue

            start = alloc.allocation_date
            finish = alloc.allocation_date + timedelta(hours=alloc.hours)

            data.append({
                "Task": order.code,
                "Start": start,
                "Finish": finish,
                "Resource": worker.name,
            })

        df = pd.DataFrame(data)
        fig = px.timeline(df, x_start="Start", x_end="Finish", y="Task", color="Resource")
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

    def _render_workers_tab(self) -> None:
        """Pagina per gestire gli operai e le loro competenze"""
        st.header("👥 Gestione Operai")

        if not self.workers:
            st.info("Nessun operaio presente")
        else:
            data = [
                {
                    "ID": w.id,
                    "Nome": w.name,
                    "Competenze": ", ".join(sorted(w.skills)) if w.skills else "-",
                }
                for w in self.workers
            ]
            st.table(pd.DataFrame(data))

        if self.workers:
            st.subheader("Modifica Competenze")
            for w in self.workers:
                with st.expander(f"{w.name} (ID {w.id})"):
                    with st.form(f"edit_worker_{w.id}"):
                        skill_options = sorted({o.code for o in self.orders.values()})
                        default_skills = [s for s in sorted(w.skills) if s in skill_options]
                        selected = st.multiselect(
                            "Competenze", options=skill_options,
                            default=default_skills, key=f"skills_{w.id}"
                        )
                        hours = st.number_input(
                            "Ore per giorno", min_value=1.0, max_value=24.0,
                            step=0.5, value=float(w.hours_per_day), key=f"hp_{w.id}"
                        )
                        saved = st.form_submit_button("Salva")
                    if saved:
                        w.skills = set(selected)
                        w.hours_per_day = float(hours)
                        if self.workers_file:
                            from domain.models import save_workers_to_yaml
                            save_workers_to_yaml(self.workers, self.workers_file)
                        update = ScheduleUpdated()
                        try:
                            self.event_queue.put_nowait(update)
                        except Exception:
                            asyncio.create_task(self.event_queue.put(update))
                        st.success("Dati operaio aggiornati")

        st.subheader("Aggiungi Operaio")
        with st.form("add_worker_form"):
            name = st.text_input("Nome")
            skills = st.multiselect(
                "Codici conosciuti",
                options=sorted(self.orders.keys()),
            )
            submitted = st.form_submit_button("Aggiungi")

            if submitted and name:
                new_id = max([w.id for w in self.workers], default=0) + 1
                worker = Worker(
                    id=new_id,
                    name=name,
                    hours_per_day=self.config["resources"]["hours_per_day"],
                    skills=set(skills),
                )
                self.workers.append(worker)
                if self.workers_file:
                    from domain.models import save_workers_to_yaml
                    save_workers_to_yaml(self.workers, self.workers_file)
                st.success("Operaio aggiunto")

    def _complete_orders(self, codes: List[str]) -> None:
        """Segna come completati gli ordini selezionati"""
        if not codes:
            return

        excel_path = self.config["excel"]["path"]
        sheet_name = self.config["excel"]["sheet_name"]

        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
        except Exception as e:
            st.error(f"Errore nel caricamento del file Excel: {e}")
            return

        for code in codes:
            order = self.orders.get(code)
            if not order:
                continue

            order.consumed_qty = order.ordered_qty

            from domain.events import OrderUpdated

            update = OrderUpdated(
                order_code=order.code,
                doc_number=order.doc_number,
                ordered_qty=order.ordered_qty,
                consumed_qty=order.ordered_qty,
                due_date=order.due_date,
                priority_manual=order.priority_manual,
            )
            asyncio.create_task(self.event_queue.put(update))

            mask = df["Codice"] == order.code
            df.loc[mask, "Da cons."] = df.loc[mask, "Ordinato"]
            if "Val. Residuo" in df.columns:
                df.loc[mask, "Val. Residuo"] = 0

            del self.orders[code]

        try:
            df.to_excel(excel_path, sheet_name=sheet_name, index=False)
        except Exception as e:
            st.error(f"Errore nel salvataggio del file Excel: {e}")


def run_dashboard():
    """Funzione principale per avviare la dashboard"""
    # Crea la dashboard con la configurazione predefinita
    dashboard = Dashboard()
    
    # Carica i dati iniziali dal file Excel
    try:
        from data_loader.excel_monitor import ExcelMonitor
        from domain.models import Worker, load_workers_from_yaml
        import yaml
        
        # Carica la configurazione
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        # Carica gli operai dal file YAML se disponibile
        workers_file = config["resources"].get("workers_file")
        workers = []
        if workers_file and os.path.exists(workers_file):
            workers = load_workers_from_yaml(workers_file)

        if not workers:
            num_workers = config["resources"]["workers"]
            hours_per_day = config["resources"]["hours_per_day"]

            for i in range(1, num_workers + 1):
                worker = Worker(
                    id=i,
                    name=f"Operaio {i}",
                    hours_per_day=hours_per_day,
                )
                workers.append(worker)
        
        # Crea il monitor Excel per caricare i dati
        excel_monitor = ExcelMonitor("config.yaml")
        orders = excel_monitor._parse_excel()
        orders_dict = {order.doc_number: order for order in orders}
        
        # Crea lo scheduler per calcolare i dati
        from planner.algorithms import Scheduler, PriorityCalculator
        
        # Inizializza il calcolatore di priorità
        urgency_thresholds = config["priority"]["urgency_thresholds"]
        size_threshold = config["priority"]["size_threshold"]
        priority_calculator = PriorityCalculator(urgency_thresholds, size_threshold)
        
        # Calcola le priorità degli ordini
        for order in orders_dict.values():
            order.calculated_priority = priority_calculator.compute_priority(
                order, date.today()
            )
        
        # Inizializza lo scheduler
        scheduler = Scheduler(workers, priority_calculator)
        
        # Crea lo schedule
        active_orders = [o for o in orders_dict.values() if o.pending_qty > 0]
        schedule = scheduler.create_schedule(active_orders, date.today())
        
        # Calcola i ritardi previsti
        delays = scheduler.check_delays(active_orders)
        
        # Calcola il carico di lavoro degli operai
        worker_load = scheduler.get_worker_load()
        
        # Calcola l'avanzamento degli ordini
        progress = scheduler.get_order_progress(active_orders)
        
        # Aggiorna i dati nella dashboard
        dashboard.update_data(
            orders=orders_dict,
            workers=workers,
            schedule=schedule,
            delays=delays,
            progress=progress,
            worker_load=worker_load
        )
        
        print("Dati iniziali caricati nella dashboard")
    except Exception as e:
        print(f"Errore durante il caricamento dei dati iniziali: {e}")
    
    # Avvia la dashboard
    dashboard.run()


if __name__ == "__main__":
    run_dashboard()
