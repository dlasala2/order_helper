import os
import pandas as pd
from datetime import datetime, timedelta
import random

# Definisci il percorso del file Excel
data_dir = "data"
os.makedirs(data_dir, exist_ok=True)
excel_path = os.path.join(data_dir, "ordini.xlsx")

# Crea dati di esempio
today = datetime.now()
data = []

# Codici prodotto di esempio
product_codes = [
    "SL2524-L", "SL1845-M", "SL3010-S", "FT4520-XL", "FT2230-L",
    "FT1815-M", "CB5040-L", "CB3025-M", "CB2015-S", "VL6030-XL",
    "VL4520-L", "VL3015-M", "TP7035-XL", "TP5025-L", "TP3520-M"
]

# Descrizioni di esempio
descriptions = [
    "Filtro 20 µm", "Filtro 30 µm", "Filtro 50 µm", "Valvola di controllo",
    "Valvola di sicurezza", "Sensore di pressione", "Sensore di temperatura",
    "Connettore rapido", "Guarnizione speciale", "Tubo flessibile",
    "Raccordo a T", "Raccordo a L", "Pompa idraulica", "Motore elettrico",
    "Centralina di controllo"
]

# Genera 15 ordini di esempio
for i in range(15):
    # Seleziona un codice e una descrizione
    code = product_codes[i]
    description = descriptions[i]
    
    # Genera quantità casuali
    ordered_qty = random.randint(100, 1000)
    consumed_qty = random.randint(0, ordered_qty // 2)
    residual_qty = ordered_qty - consumed_qty
    
    # Genera tempi di produzione casuali (in ore)
    cycle_time = round(random.uniform(0.05, 0.5), 2)
    
    # Genera numeri documento casuali
    doc_number = random.randint(1000, 9999)
    
    # Genera date casuali
    doc_date = today - timedelta(days=random.randint(10, 60))
    due_date = today + timedelta(days=random.randint(5, 90))
    
    # Genera priorità manuale casuale (alcuni ordini non hanno priorità manuale)
    priority_manual = random.randint(0, 5) if random.random() > 0.3 else None
    
    # Aggiungi l'ordine ai dati
    data.append({
        "Codice": code,
        "Descrizione": description,
        "Ordinato": ordered_qty,
        "Da cons.": consumed_qty,
        "Val. Residuo": residual_qty,
        "Ore_Pezzo": cycle_time,
        "PriorityManual": priority_manual,
        "Nr. doc.": doc_number,
        "Data Doc.": doc_date.strftime("%d/%m/%Y"),
        "Consegna": due_date.strftime("%d/%m/%Y")
    })

# Crea il DataFrame
df = pd.DataFrame(data)

# Salva il DataFrame in un file Excel
df.to_excel(excel_path, sheet_name="Ordini", index=False)

print(f"File Excel di esempio creato: {excel_path}")