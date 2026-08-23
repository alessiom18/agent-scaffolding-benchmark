#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera le immagini per i task VISION del bench, con ground truth CERTA.
Motivo: le foto reali dei menu non sono piu' sul disco, e con immagini generate
sappiamo esattamente cosa contengono -> il punteggio e' oggettivo, non opinabile.

Output in ~/llm_bench/img/
"""
import os, json
from PIL import Image, ImageDraw, ImageFont

OUT = "/home/alessio/llm_bench/img"
os.makedirs(OUT, exist_ok=True)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def f(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)

verita = {}

# ---------- 1. MENU con 12 piatti e prezzi ----------
PIATTI = [
    ("Bruschetta al pomodoro", "4,50"), ("Tagliere di salumi", "9,00"),
    ("Spaghetti alle vongole", "13,00"), ("Risotto ai funghi porcini", "12,50"),
    ("Lasagna della casa", "10,00"), ("Tagliata di manzo", "18,00"),
    ("Baccala alla livornese", "15,50"), ("Cacciucco", "22,00"),
    ("Insalata mista", "5,00"), ("Patate al forno", "4,00"),
    ("Tiramisu", "6,00"), ("Panna cotta", "5,50"),
]
img = Image.new("RGB", (900, 1250), "#FFFDF7")
d = ImageDraw.Draw(img)
d.rectangle([0, 0, 900, 110], fill="#8B1A1A")
d.text((450, 55), "TRATTORIA DA MARIO", font=f(38, True), fill="white", anchor="mm")
y = 160
for titolo, righe in [("ANTIPASTI", PIATTI[0:2]), ("PRIMI", PIATTI[2:5]),
                      ("SECONDI", PIATTI[5:8]), ("CONTORNI", PIATTI[8:10]),
                      ("DOLCI", PIATTI[10:12])]:
    d.text((60, y), titolo, font=f(26, True), fill="#8B1A1A"); y += 45
    for nome, prezzo in righe:
        d.text((80, y), nome, font=f(22), fill="#222")
        d.text((840, y), prezzo + " EUR", font=f(22), fill="#222", anchor="ra")
        y += 38
    y += 25
img.save(f"{OUT}/menu.png")
verita["menu"] = {"n_piatti": len(PIATTI), "piatti": dict(PIATTI),
                  "locale": "Trattoria da Mario",
                  "prezzo_max": "22,00", "piatto_caro": "Cacciucco"}

# ---------- 2. SCONTRINO con totale ----------
VOCI = [("Caffe", 2, 1.20), ("Cornetto", 2, 1.50), ("Spremuta", 1, 3.50),
        ("Acqua 0,5", 3, 1.00)]
tot = sum(q * p for _, q, p in VOCI)          # = 12,30
img = Image.new("RGB", (520, 700), "white")
d = ImageDraw.Draw(img)
d.text((260, 40), "BAR CENTRALE", font=f(26, True), fill="black", anchor="mm")
d.text((260, 75), "Via Grande 14 - Livorno", font=f(16), fill="black", anchor="mm")
d.text((260, 100), "P.IVA 01234567890", font=f(15), fill="black", anchor="mm")
d.line([30, 130, 490, 130], fill="black", width=2)
y = 160
for nome, q, p in VOCI:
    d.text((40, y), f"{q} x {nome}", font=f(19), fill="black")
    d.text((480, y), f"{p*q:.2f}".replace(".", ","), font=f(19), fill="black", anchor="ra")
    y += 34
d.line([30, y + 10, 490, y + 10], fill="black", width=2)
d.text((40, y + 35), "TOTALE", font=f(24, True), fill="black")
d.text((480, y + 35), f"{tot:.2f}".replace(".", ",") + " EUR", font=f(24, True), fill="black", anchor="ra")
d.text((40, y + 90), "CONTANTI      15,00", font=f(18), fill="black")
d.text((40, y + 118), "RESTO          2,70", font=f(18), fill="black")
d.text((260, y + 180), "SCONTRINO N. 0147", font=f(16), fill="black", anchor="mm")
d.text((260, y + 205), "23/08/2026  08:42", font=f(16), fill="black", anchor="mm")
img.save(f"{OUT}/scontrino.png")
verita["scontrino"] = {"totale": "12,30", "resto": "2,70", "contanti": "15,00",
                       "n_caffe": 2, "numero": "0147", "locale": "Bar Centrale"}

# ---------- 3. ETICHETTA BATTERIA (lettura tecnica) ----------
img = Image.new("RGB", (800, 500), "#1A1A1A")
d = ImageDraw.Draw(img)
d.rectangle([20, 20, 780, 480], outline="#FFD400", width=4)
d.text((400, 70), "LI-ION BATTERY PACK", font=f(30, True), fill="#FFD400", anchor="mm")
righe = [("Model", "SW-36104"), ("Nominal Voltage", "36 V"), ("Capacity", "10.4 Ah"),
         ("Energy", "374 Wh"), ("Max Charge Voltage", "42.0 V"),
         ("Max Discharge Current", "20 A"), ("Cells", "10S4P")]
y = 130
for k, v in righe:
    d.text((60, y), k, font=f(21), fill="#CCCCCC")
    d.text((740, y), v, font=f(21, True), fill="white", anchor="ra")
    y += 45
img.save(f"{OUT}/etichetta_batteria.png")
verita["etichetta_batteria"] = {"volt": "36", "ah": "10.4", "wh": "374",
                                "carica_max": "42", "config": "10S4P", "modello": "SW-36104"}

# ---------- 4. CONTEGGIO forme (percezione pura) ----------
img = Image.new("RGB", (700, 500), "white")
d = ImageDraw.Draw(img)
cerchi_rossi = [(80, 80), (200, 150), (330, 90), (480, 200), (600, 120), (150, 330), (420, 380)]
quadrati_blu = [(260, 260), (390, 120), (540, 340), (100, 210)]
triangoli_verdi = [(300, 430), (620, 260)]
for x, y in cerchi_rossi:
    d.ellipse([x - 28, y - 28, x + 28, y + 28], fill="#D32F2F")
for x, y in quadrati_blu:
    d.rectangle([x - 26, y - 26, x + 26, y + 26], fill="#1565C0")
for x, y in triangoli_verdi:
    d.polygon([(x, y - 30), (x - 30, y + 25), (x + 30, y + 25)], fill="#2E7D32")
img.save(f"{OUT}/conteggio.png")
verita["conteggio"] = {"cerchi_rossi": len(cerchi_rossi), "quadrati_blu": len(quadrati_blu),
                       "triangoli_verdi": len(triangoli_verdi),
                       "totale": len(cerchi_rossi) + len(quadrati_blu) + len(triangoli_verdi)}

# ---------- 5. DISPLAY con codice errore (diagnosi visiva) ----------
img = Image.new("RGB", (700, 450), "#0B0B0B")
d = ImageDraw.Draw(img)
d.rounded_rectangle([40, 40, 660, 410], radius=20, outline="#333", width=3, fill="#101418")
d.text((350, 100), "E-BIKE DISPLAY", font=f(20), fill="#666", anchor="mm")
d.text((350, 180), "ERROR 21", font=f(58, True), fill="#FF3B30", anchor="mm")
d.text((350, 245), "SPEED SENSOR", font=f(26), fill="#FF9500", anchor="mm")
d.text((160, 330), "BATT 82%", font=f(24), fill="#4CD964")
d.text((420, 330), "0 km/h", font=f(24), fill="#EEE")
d.text((350, 380), "ASSIST: OFF", font=f(20), fill="#888", anchor="mm")
img.save(f"{OUT}/display_errore.png")
verita["display_errore"] = {"codice": "21", "componente": "speed sensor / sensore velocita",
                            "batteria": "82", "velocita": "0", "assistenza": "off"}

with open(f"{OUT}/verita.json", "w", encoding="utf-8") as fh:
    json.dump(verita, fh, ensure_ascii=False, indent=2)

print("Immagini generate in", OUT)
for k in verita:
    p = f"{OUT}/{k}.png"
    print(f"  {k:20s} {os.path.getsize(p)//1024:4d} KB")
print("Ground truth -> verita.json")

# ---------- 6-7. "DOVE TI TROVI?" — deduzione da indizi (idea di Alessio) ----------
# Il nome della citta' NON compare MAI: va dedotto da prefisso telefonico, toponimi e insegne.

def cartello(d, x, y, w, h, testo, sfondo, colore="white", size=22, bordo="white"):
    d.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=sfondo, outline=bordo, width=3)
    d.text((x + w / 2, y + h / 2), testo, font=f(size, True), fill=colore, anchor="mm")

# --- 6: indizi -> LIVORNO (prefisso 0586, Porto Mediceo, Via Grande, Quartiere Venezia) ---
img = Image.new("RGB", (1000, 700), "#BFD8E8")
d = ImageDraw.Draw(img)
d.rectangle([0, 470, 1000, 700], fill="#9E9E9E")            # strada
d.rectangle([0, 430, 1000, 470], fill="#7CB342")            # aiuola
cartello(d, 60, 90, 380, 62, "PORTO MEDICEO  ➜", "#1565C0")
cartello(d, 60, 165, 380, 62, "TERMINAL CROCIERE  ➜", "#1565C0")
cartello(d, 60, 240, 380, 55, "QUARTIERE VENEZIA  ➜", "#1565C0", size=20)
cartello(d, 560, 110, 380, 70, "VIA GRANDE", "#FFFFFF", colore="#111", size=26, bordo="#111")
cartello(d, 560, 205, 380, 58, "PARCO LEVANTE  300 m", "#2E7D32", size=20)
# insegna negozio col prefisso telefonico: l'indizio decisivo
d.rounded_rectangle([560, 300, 940, 400], radius=10, fill="#FFF3E0", outline="#8D6E63", width=4)
d.text((750, 330), "TABACCHERIA DA NANDO", font=f(21, True), fill="#4E342E", anchor="mm")
d.text((750, 368), "Tel. 0586 89 12 34", font=f(23, True), fill="#B71C1C", anchor="mm")
# insegna catena internazionale (indizio "città media", non identificante)
d.rounded_rectangle([60, 330, 440, 400], radius=10, fill="#D32F2F", outline="#7F0000", width=3)
d.text((250, 365), "FAST FOOD  •  APERTO 24H", font=f(20, True), fill="white", anchor="mm")
img.save(f"{OUT}/dove_sono_1.png")
verita["dove_sono_1"] = {"citta": "Livorno", "regione": "Toscana",
                         "indizi": ["prefisso 0586", "Porto Mediceo", "Terminal Crociere",
                                    "Quartiere Venezia", "Via Grande", "Parco Levante"],
                         "accetta": ["livorno"]}

# --- 7: indizi -> CHIANTI / provincia di FIRENZE (prefisso 055, Figline Valdarno, Greve) ---
img = Image.new("RGB", (1000, 700), "#DCEAF7")
d = ImageDraw.Draw(img)
d.rectangle([0, 480, 1000, 700], fill="#8D9B6A")            # colline
d.rectangle([0, 560, 1000, 700], fill="#A1887F")            # strada sterrata
cartello(d, 80, 90, 420, 60, "FIGLINE VALDARNO   8", "#2E7D32")
cartello(d, 80, 165, 420, 60, "GREVE IN CHIANTI  12", "#2E7D32")
cartello(d, 80, 240, 420, 60, "SIENA             45", "#2E7D32")
cartello(d, 560, 110, 380, 70, "CHIANTI CLASSICO", "#7B1FA2", size=24)
d.rounded_rectangle([560, 220, 940, 330], radius=10, fill="#FFFDE7", outline="#6D4C41", width=4)
d.text((750, 252), "AZIENDA AGRICOLA", font=f(20, True), fill="#4E342E", anchor="mm")
d.text((750, 285), "VENDITA DIRETTA VINO", font=f(18), fill="#4E342E", anchor="mm")
d.text((750, 315), "Tel. 055 85 43 21", font=f(21, True), fill="#B71C1C", anchor="mm")
img.save(f"{OUT}/dove_sono_2.png")
verita["dove_sono_2"] = {"zona": "Chianti, provincia di Firenze", "regione": "Toscana",
                         "indizi": ["prefisso 055", "Figline Valdarno", "Greve in Chianti",
                                    "Siena 45 km", "Chianti Classico"],
                         "accetta": ["chianti", "firenze", "toscana", "valdarno"]}

with open(f"{OUT}/verita.json", "w", encoding="utf-8") as fh:
    json.dump(verita, fh, ensure_ascii=False, indent=2)
print("  + dove_sono_1 (Livorno) e dove_sono_2 (Chianti/Firenze) — il nome NON compare nell'immagine")

# ---------- 8. QUANDO siamo? — deduzione temporale da indizi ----------
img = Image.new("RGB", (1000, 640), "#FFF8E1")
d = ImageDraw.Draw(img)
d.rectangle([0, 470, 1000, 640], fill="#BCAAA4")
cartello(d, 60, 70, 420, 80, "SALDI ESTIVI  -50%", "#E53935", size=28)
cartello(d, 60, 175, 420, 60, "CHIUSO PER FERIE", "#37474F", size=22)
cartello(d, 60, 255, 420, 60, "dal 12 al 26", "#37474F", size=22)
d.rounded_rectangle([560, 70, 940, 200], radius=12, fill="#0D47A1", outline="#082C61", width=3)
d.text((750, 110), "FARMACIA", font=f(24, True), fill="#8BC34A", anchor="mm")
d.text((750, 155), "34°C   14:20", font=f(30, True), fill="#8BC34A", anchor="mm")
d.rounded_rectangle([560, 235, 940, 330], radius=10, fill="#FFFFFF", outline="#555", width=3)
d.text((750, 262), "GELATERIA - CODA", font=f(19, True), fill="#333", anchor="mm")
d.text((750, 300), "SPIAGGIA 200 m", font=f(19, True), fill="#333", anchor="mm")
img.save(f"{OUT}/quando.png")
verita["quando"] = {"stagione": "estate", "mese_probabile": "agosto (o fine luglio)",
                    "ora": "14:20 primo pomeriggio", "temperatura": "34",
                    "indizi": ["saldi estivi", "chiuso per ferie 12-26", "34 gradi",
                               "gelateria con coda", "spiaggia"],
                    "accetta": ["estate", "agosto", "luglio"]}

# ---------- 9. TROVA L'ERRORE — schema di collegamento sbagliato ----------
img = Image.new("RGB", (1000, 620), "#FAFAFA")
d = ImageDraw.Draw(img)
d.text((500, 40), "SCHEMA COLLEGAMENTO BATTERIA - MOTORE", font=f(24, True), fill="#222", anchor="mm")
# batteria
d.rounded_rectangle([60, 140, 300, 340], radius=10, fill="#263238", outline="#000", width=3)
d.text((180, 175), "BATTERIA", font=f(20, True), fill="white", anchor="mm")
d.text((180, 215), "36 V  10 Ah", font=f(19), fill="#B0BEC5", anchor="mm")
d.text((180, 265), "+", font=f(40, True), fill="#E53935", anchor="mm")
d.text((180, 310), "-", font=f(40, True), fill="#2196F3", anchor="mm")
# controller
d.rounded_rectangle([420, 140, 660, 340], radius=10, fill="#37474F", outline="#000", width=3)
d.text((540, 175), "CONTROLLER", font=f(20, True), fill="white", anchor="mm")
d.text((540, 215), "48 V  25 A", font=f(19), fill="#FFCC80", anchor="mm")
# motore
d.rounded_rectangle([760, 180, 940, 320], radius=10, fill="#455A64", outline="#000", width=3)
d.text((850, 230), "MOTORE", font=f(20, True), fill="white", anchor="mm")
d.text((850, 270), "250 W", font=f(19), fill="#B0BEC5", anchor="mm")
# cavi: il ROSSO (+) va al morsetto BLU (-) del controller e viceversa -> POLARITA' INVERTITA
d.line([(300, 265), (360, 265), (360, 300), (420, 300)], fill="#E53935", width=9)
d.line([(300, 310), (380, 310), (380, 240), (420, 240)], fill="#2196F3", width=9)
d.text((362, 200), "+", font=f(26, True), fill="#E53935", anchor="mm")
d.text((408, 232), "-", font=f(26, True), fill="#2196F3", anchor="mm")
d.text((408, 292), "+", font=f(26, True), fill="#E53935", anchor="mm")
d.line([(660, 240), (760, 240)], fill="#444", width=7)
# fusibile chiaramente sottodimensionato
d.rounded_rectangle([420, 400, 660, 470], radius=8, fill="#FFF9C4", outline="#F57F17", width=3)
d.text((540, 435), "FUSIBILE  3 A", font=f(22, True), fill="#E65100", anchor="mm")
d.text((500, 520), "Corrente massima assorbita in salita: 18 A", font=f(20), fill="#333", anchor="mm")
d.text((500, 560), "Batteria 36V  -  Controller 48V", font=f(20), fill="#333", anchor="mm")
img.save(f"{OUT}/trova_errore.png")
verita["trova_errore"] = {
    "errori": ["polarita invertita: il + della batteria va al - del controller",
               "fusibile da 3 A su un carico che assorbe 18 A (sottodimensionato)",
               "controller da 48 V alimentato con batteria da 36 V (tensione non corrispondente)"],
    "accetta_parole": ["invertit", "polarit", "fusibil", "3 a", "sottodimension", "48", "36"]}

with open(f"{OUT}/verita.json", "w", encoding="utf-8") as fh:
    json.dump(verita, fh, ensure_ascii=False, indent=2)
print("  + quando.png (deduzione temporale) e trova_errore.png (3 errori tecnici da individuare)")
