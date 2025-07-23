import asyncio
import os
import sys
import logging
import traceback
from datetime import date
from pathlib import Path
import subprocess
import threading

import yaml

# Configurazione del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scheduler.log')
    ]
)
logger = logging.getLogger('scheduler')

from data_loader.excel_monitor import ExcelMonitor
from domain.models import Worker
from planner.planner_agent import PlannerAgent
from planner.worker_agent import WorkerAgent


async def run_agents(config_path: str = "config.yaml"):
    """Avvia gli agenti del sistema
    
    Args:
        config_path: Percorso del file di configurazione
    """
    # Carica la configurazione
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Errore durante il caricamento della configurazione: {e}")
        raise
    
    # Crea la coda di eventi condivisa
    event_queue = asyncio.Queue()
    
    # Crea la directory dei dati se non esiste
    excel_path = config["excel"]["path"]
    data_dir = Path(excel_path).parent
    os.makedirs(data_dir, exist_ok=True)
    
    # Carica gli operai dal file YAML se disponibile
    from domain.models import load_workers_from_yaml

    workers_file = config["resources"].get("workers_file")
    workers = []

    if workers_file and os.path.exists(workers_file):
        workers = load_workers_from_yaml(workers_file)

    if not workers:
        # Fallback: crea operai di default
        num_workers = config["resources"]["workers"]
        hours_per_day = config["resources"]["hours_per_day"]

        for i in range(1, num_workers + 1):
            worker = Worker(
                id=i,
                name=f"Operaio {i}",
                hours_per_day=hours_per_day,
            )
            workers.append(worker)

    logger.info(f"Creati {len(workers)} operai")
    
    # Crea il monitor Excel
    excel_monitor = ExcelMonitor(config_path, event_queue)
    
    # Crea l'agente pianificatore
    planner_agent = PlannerAgent(workers, config, event_queue)
    
    # Crea gli agenti operaio
    worker_agents = [WorkerAgent(worker, event_queue) for worker in workers]
    
    # Avvia gli agenti
    tasks = [
        excel_monitor.start_monitoring(),
        planner_agent.start()
    ]
    
    for agent in worker_agents:
        tasks.append(agent.start())
    
    try:
        # Esegui tutti i task in parallelo
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Arresto degli agenti in corso...")
        # Gestione della cancellazione
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()
        
        # Attendi che tutti i task siano cancellati
        pending = asyncio.all_tasks() - {asyncio.current_task()}
        if pending:
            await asyncio.wait(pending, timeout=5)
        logger.info("Tutti gli agenti sono stati arrestati")
    except Exception as e:
        logger.error(f"Errore durante l'esecuzione degli agenti: {e}", exc_info=True)
        raise


def run_dashboard():
    """Avvia la dashboard in un processo separato"""
    dashboard_port = 8501  # Porta predefinita di Streamlit
    
    try:
        # Avvia la dashboard con Streamlit
        dashboard_process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", 
             "dashboard/app.py", "--server.port", str(dashboard_port)]
        )
        
        # Verifica che il processo sia stato avviato correttamente
        if dashboard_process.poll() is None:
            logger.info(f"Dashboard avviata su http://localhost:{dashboard_port}")
        else:
            logger.error(f"Errore durante l'avvio della dashboard. Codice di uscita: {dashboard_process.returncode}")
    except Exception as e:
        logger.error(f"Errore durante l'avvio della dashboard: {e}", exc_info=True)


def main():
    """Funzione principale"""
    try:
        logger.info("Avvio del sistema di schedulazione ordini")
        
        # Avvia la dashboard in un thread separato
        dashboard_thread = threading.Thread(target=run_dashboard)
        dashboard_thread.daemon = True
        dashboard_thread.start()
        
        # Avvia gli agenti nel loop di eventi asyncio
        asyncio.run(run_agents())
    except KeyboardInterrupt:
        logger.info("Interruzione manuale del sistema")
    except Exception as e:
        logger.critical(f"Errore critico durante l'esecuzione: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()