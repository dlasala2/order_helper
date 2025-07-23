# Sistema di Schedulazione Ordini di Produzione

Questo sistema implementa un'architettura multi-agente (sciame di agenti) per la gestione e schedulazione degli ordini di produzione, con monitoraggio automatico di un file Excel di input.

## Caratteristiche Principali

- **Monitoraggio Excel**: Importazione e aggiornamento automatico da file Excel con cadenza configurabile
- **Prioritizzazione Intelligente**: Calcolo automatico delle priorità (0-5) basato su urgenza, dimensione e priorità manuale
- **Allocazione Dinamica**: Assegnazione ottimizzata delle risorse di lavoro agli ordini
- **Dashboard Interattiva**: Visualizzazione di carichi di lavoro, avanzamento e alert
- **Gestione Adattiva**: Ricalcolo automatico delle allocazioni in caso di cambiamenti

## Architettura

Il sistema è strutturato in moduli separati:

```
scadenziario/
├── config.yaml              # Configurazione del sistema
├── main.py                  # Avvio del sistema
├── data_loader/             # Importazione dati da Excel
│   └── excel_monitor.py     # Monitoraggio del file Excel
├── domain/                  # Modelli di dominio
│   ├── models.py            # Entità: Order, Worker, Allocation
│   └── events.py            # Eventi per la comunicazione
├── planner/                 # Logica di pianificazione
│   ├── worker_agent.py      # Agente operaio
│   ├── planner_agent.py     # Agente pianificatore
│   └── algorithms.py        # Algoritmi di prioritizzazione e scheduling
└── dashboard/               # Interfaccia utente
    └── app.py               # Dashboard Streamlit
```

## Protocollo di Comunicazione

Gli agenti comunicano tramite un sistema di eventi asincrono:

1. **BidRequest**: Il PlannerAgent richiede offerte per un ordine
2. **BidResponse**: I WorkerAgent rispondono con la loro capacità disponibile
3. **AllocationAward**: Il PlannerAgent assegna il lavoro agli operai
4. **ProgressUpdate**: I WorkerAgent riportano l'avanzamento del lavoro
5. **OrderUpdated/OrderCreated**: Il DataLoader notifica cambiamenti negli ordini

## Requisiti

- Python 3.8+
- pandas
- pyyaml
- streamlit
- plotly

## Installazione

1. Clona il repository:
   ```
   git clone https://github.com/tuouser/scadenziario.git
   cd scadenziario
   ```

2. Crea un ambiente virtuale (opzionale ma consigliato):
   ```
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. Installa le dipendenze:
   ```
   pip install -r requirements.txt
   ```

## Configurazione

Modifica il file `config.yaml` per personalizzare:

- Percorso del file Excel e frequenza di aggiornamento
- Numero di operai e ore di lavoro giornaliere
- Parametri dell'algoritmo di prioritizzazione
- Configurazione della dashboard

## Utilizzo

1. Prepara il file Excel con il formato richiesto (vedi sotto)
2. Avvia il sistema:
   ```
   python main.py
   ```
3. Accedi alla dashboard all'indirizzo: http://localhost:8501

## Formato del File Excel

Il file Excel deve contenere le seguenti colonne:

| Codice | Descrizione | Ordinato | Da cons. | Val. Residuo | Ore_Pezzo | PriorityManual | Nr. doc. | Data Doc. | Consegna |
|--------|-------------|----------|----------|--------------|-----------|----------------|----------|-----------|----------|
| SL2524‑L | Filtro 20 µm | 500 | 120 | 380 | 0,15 | | 4567 | 01/07/2025 | 05/08/2025 |

Note:
- `Ore_Pezzo` è opzionale (verrà usato un valore di default se mancante)
- `PriorityManual` è opzionale (priorità manuale da 0 a 5)

## Licenza

MIT"# order_helper" 
