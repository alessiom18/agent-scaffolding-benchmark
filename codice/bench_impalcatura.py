#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUANTO CONTA L'IMPALCATURA? — 23/08/2026

Domanda di Alessio: «noi usiamo gemma ed è buono... ma con un modello minuscolo e
con tutti i RAG e tutto quanto, cosa riuscirebbe a fare? Quanto influisce la nostra
impalcatura (Bruno) rispetto ai risultati di benchmark di un modello?»

I benchmark classici misurano il MODELLO da solo. Qui si misura il SISTEMA: lo stesso
agente (Bruno: tool su file/bash/web, loop, retry, esperti) con cervelli di taglia
molto diversa — da 0,4 GB a 7,6 GB — sugli stessi compiti operativi reali.

Non si chiede al modello di *sapere* qualcosa: gli si chiede di FARE qualcosa.
La verifica non guarda cosa ha scritto, guarda il filesystem: il file c'è? il contenuto
è giusto? Nessuna opinione, solo fatti.

Ogni compito gira in una sandbox pulita, ricreata da zero: nessun rischio per il resto.
"""
import json, os, re, shutil, subprocess, time, datetime, sys

BRUNO = "/home/alessio/bruno.py"
BASE = "/home/alessio/llm_bench/sandbox_impalcatura"
TS = datetime.datetime.now().strftime("%Y%m%d_%H%M")
OUT = f"/home/alessio/llm_bench/results/impalcatura_{TS}.jsonl"
LOG = f"/home/alessio/llm_bench/impalcatura_{TS}.log"
TIMEOUT = int(os.environ.get("IMP_TIMEOUT", "600"))

# cervelli da provare: dal piu' piccolo al nostro attuale
# NB: Bruno usa il TOOL-CALLING NATIVO di ollama (/api/chat con "tools").
# Un modello senza la capability `tools` non puo' funzionare dentro Bruno: non e' che
# sia scarso, non parla il protocollo. Ne teniamo uno apposta come banco di controllo.
MODELLI = [
    ("qwen2.5:0.5b", "0,4 GB · 494 milioni · tools · 32k"),
    ("qwen3.5:0.8b", "1,0 GB · 873 milioni · tools+vision+thinking · 256k"),
    ("qwen3.5:4b", "· 4 mld · tools+vision+thinking · 256k"),
    ("gemma:2b", "1,7 GB · 3 mld · SENZA tools · 8k — banco di controllo"),
    ("qwen2.5:3b", "1,9 GB · 3,1 mld · tools · 32k"),
    ("phi4-mini:latest", "2,5 GB · 3,8 mld · tools · 128k"),
    ("qwen3:4b", "2,5 GB · 4 mld · tools+thinking · 256k"),
    # Bonsai 27B a 1 bit: e' agentico e multimodale, ma su 12 GB gira in offload e
    # divora decine di minuti per compito -> fuori dalla batteria (scelta di Alessio).
    ("cogito:8b", "4,9 GB · 8 mld · tools · 128k"),
    ("gemma4:12b", "7,6 GB · il nostro attuale (riferimento)"),
]

def log(*a):
    riga = f"[{datetime.datetime.now():%H:%M:%S}] " + " ".join(str(x) for x in a)
    print(riga, flush=True)
    open(LOG, "a", encoding="utf-8").write(riga + "\n")

# ---------------------------------------------------------------- sandbox
def prepara_sandbox(nome):
    """Ricrea da zero la cartella di lavoro con contenuti noti."""
    d = os.path.join(BASE, nome)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    # un piccolo magazzino finto, con un dato "sepolto" da trovare
    os.makedirs(f"{d}/magazzino", exist_ok=True)
    open(f"{d}/magazzino/batterie.txt", "w").write(
        "36V 10Ah — 12 pezzi\n48V 14Ah — 3 pezzi\n24V 8Ah — 0 pezzi\n")
    open(f"{d}/magazzino/caricabatterie.txt", "w").write(
        "42V 2A — 7 pezzi\n54,6V 2A — 2 pezzi\n")
    open(f"{d}/magazzino/note.txt", "w").write(
        "Il codice di magazzino della scorta critica e' MG-7741.\n"
        "Ricordarsi di riordinare le 24V, sono a zero.\n")
    open(f"{d}/listino.csv", "w").write(
        "prodotto;prezzo\nbatteria 36V;148,00\ncaricabatterie 42V;19,50\ncavo;3,20\n")
    open(f"{d}/README.md", "w").write("# Officina\nAppunti sparsi.\n")
    return d

# ---------------------------------------------------------------- compiti
# (id, descrizione del compito per Bruno, funzione di verifica(dir) -> (ok, nota))
def v_trova_codice(d):
    p = os.path.join(d, "risposta.txt")
    if not os.path.exists(p):
        return False, "file risposta.txt non creato"
    t = open(p, encoding="utf-8", errors="replace").read()
    return ("MG-7741" in t), (f"contenuto: {t.strip()[:60]}" if t.strip() else "file vuoto")

def v_conta_file(d):
    p = os.path.join(d, "conteggio.txt")
    if not os.path.exists(p):
        return False, "file conteggio.txt non creato"
    t = open(p, encoding="utf-8", errors="replace").read()
    return ("3" in t), f"contenuto: {t.strip()[:60]}"

def v_modifica(d):
    p = os.path.join(d, "magazzino/batterie.txt")
    t = open(p, encoding="utf-8", errors="replace").read()
    ok = "5 pezzi" in t and "24V 8Ah" in t
    return ok, ("riga 24V aggiornata" if ok else f"non aggiornata: {t.strip()[:70]}")

def v_totale(d):
    p = os.path.join(d, "totale.txt")
    if not os.path.exists(p):
        return False, "file totale.txt non creato"
    t = open(p, encoding="utf-8", errors="replace").read().replace(".", "").replace(" ", "")
    # 12*148 + 7*19,50 = 1776 + 136,50 = 1912,50
    ok = ("1912,5" in t.replace(",", ",")) or ("1912.5" in t) or ("19125" in t)
    return ok, f"contenuto: {t.strip()[:60]}"

def v_riepilogo(d):
    p = os.path.join(d, "riepilogo.md")
    if not os.path.exists(p):
        return False, "file riepilogo.md non creato"
    t = open(p, encoding="utf-8", errors="replace").read().lower()
    pezzi = sum(x in t for x in ("36v", "48v", "24v", "42v"))
    return (pezzi >= 3), f"{pezzi}/4 voci di magazzino citate"

COMPITI = [
    ("trova_codice",
     "Nella cartella corrente c'e' una sottocartella magazzino. Cerca in quei file il codice "
     "di magazzino della scorta critica (ha la forma MG-numero) e scrivi SOLO quel codice "
     "dentro un nuovo file chiamato risposta.txt nella cartella corrente.",
     v_trova_codice),

    ("conta_file",
     "Conta quanti file ci sono dentro la sottocartella magazzino e scrivi il numero "
     "dentro un file chiamato conteggio.txt nella cartella corrente.",
     v_conta_file),

    ("modifica",
     "Nel file magazzino/batterie.txt la riga delle 24V 8Ah dice 0 pezzi. "
     "Modificala in modo che dica 5 pezzi, lasciando tutto il resto identico.",
     v_modifica),

    ("calcolo_da_file",
     "Usa listino.csv e magazzino/batterie.txt e magazzino/caricabatterie.txt: "
     "calcola quanto vale la scorta di batterie 36V (quantita' x prezzo) piu' quella dei "
     "caricabatterie 42V, e scrivi il totale in euro dentro un file totale.txt.",
     v_totale),

    ("riepilogo",
     "Leggi tutti i file della sottocartella magazzino e scrivi un file riepilogo.md "
     "con l'elenco di tutti gli articoli e le rispettive quantita'.",
     v_riepilogo),
]

# ---------------------------------------------------------------- modello NUDO
# Stesso compito, ma senza impalcatura: niente tool, niente loop, niente retry.
# I dati che Bruno andrebbe a cercare qui glieli mettiamo gia' nel prompt: si misura
# solo la testa del modello. La differenza con la versione "dentro Bruno" e' il valore
# aggiunto dell'impalcatura.
import urllib.request

CONTESTO = """Contenuto dei file dell'officina:

--- magazzino/batterie.txt ---
36V 10Ah — 12 pezzi
48V 14Ah — 3 pezzi
24V 8Ah — 0 pezzi

--- magazzino/caricabatterie.txt ---
42V 2A — 7 pezzi
54,6V 2A — 2 pezzi

--- magazzino/note.txt ---
Il codice di magazzino della scorta critica e' MG-7741.
Ricordarsi di riordinare le 24V, sono a zero.

--- listino.csv ---
prodotto;prezzo
batteria 36V;148,00
caricabatterie 42V;19,50
cavo;3,20
"""

DOMANDE_NUDE = {
    "trova_codice":   ("Qual e' il codice di magazzino della scorta critica? Rispondi SOLO col codice.",
                       lambda t: "mg-7741" in t.lower()),
    "conta_file":     ("Quanti file ci sono nella cartella magazzino? Rispondi SOLO col numero.",
                       lambda t: "3" in t),
    "modifica":       ("Riscrivi il contenuto di batterie.txt mettendo 5 pezzi al posto di 0 pezzi "
                       "per le 24V 8Ah, lasciando il resto identico.",
                       lambda t: "5 pezzi" in t.lower() and "24v" in t.lower()),
    "calcolo_da_file":("Quanto vale la scorta di batterie 36V (quantita' x prezzo) piu' quella dei "
                       "caricabatterie 42V? Rispondi col totale in euro.",
                       lambda t: "1912" in t.replace(".", "").replace(" ", "")),
    "riepilogo":      ("Elenca tutti gli articoli di magazzino con le rispettive quantita'.",
                       lambda t: sum(x in t.lower() for x in ("36v", "48v", "24v", "42v")) >= 3),
}

def esegui_nudo(modello, compito_id):
    domanda, verifica = DOMANDE_NUDE[compito_id]
    payload = {"model": modello, "prompt": CONTESTO + "\n" + domanda, "stream": False,
               "think": False, "options": {"num_predict": 900, "temperature": 0.2},
               "keep_alive": "10m"}
    t0 = time.time()
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.loads(r.read())
        risp = d.get("response", "") or ""
        ok = bool(verifica(risp))
        err = None
        tok = d.get("eval_count", 0)
    except Exception as e:
        risp, ok, err, tok = "", False, str(e)[:120], 0
    rec = {"modello": modello, "compito": compito_id, "modalita": "nudo",
           "ok": ok, "secondi": round(time.time() - t0, 1), "token": tok,
           "errore": err, "risposta": risp[:1500]}
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log(f"    {compito_id:16s} NUDO   {'✅' if ok else '❌'}  {rec['secondi']:5.0f}s  "
        f"{tok:5d} tok  {(err or risp.strip()[:45] or 'vuoto')}")
    return ok

# ---------------------------------------------------------------- esecuzione
def token_spesi(modello):
    """Token generati finora dal modello (contatore cumulativo lato ollama).
    Non esiste un contatore globale: lo ricavo dalla somma delle risposte del job,
    quindi qui misuro il TEMPO e i giri, e i token li conto dall'uscita di Bruno."""
    return 0

def conta_token_uscita(uscita):
    """Bruno stampa le risposte del modello: stimo i token dai caratteri (~4 char/token).
    Non e' preciso al singolo token, ma serve a confrontare gli ORDINI DI GRANDEZZA
    fra un modello che risolve in un giro e uno che ne fa venti."""
    return int(len(uscita) / 4)

def esegui(modello, compito_id, testo, verifica):
    d = prepara_sandbox(f"{modello.replace(':','_').replace('/','_')}__{compito_id}")
    env = dict(os.environ, BRUNO_NOCAVE="1", BRUNO_MARKER="1")
    t0 = time.time()
    scaduto = False
    try:
        p = subprocess.run(
            ["python3", BRUNO, testo, "--model", modello, "--dir", d, "--auto"],
            capture_output=True, text=True, timeout=TIMEOUT, env=env)
        uscita = (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        uscita = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
        scaduto = True
    dur = time.time() - t0
    ok, nota = verifica(d)
    # quanti giri di strumento ha fatto (indice di quanto l'impalcatura ha lavorato)
    giri = len(re.findall(r"(?:🔧|\[tool\]|chiamo|eseguo)", uscita))
    rec = {"modello": modello, "compito": compito_id, "modalita": "bruno", "ok": bool(ok), "nota": nota,
           "secondi": round(dur, 1), "timeout": scaduto, "giri_tool": giri,
           "token_stimati": conta_token_uscita(uscita),
           "uscita": uscita[-4000:]}
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    esito = "✅" if ok else ("⏱ TIMEOUT" if scaduto else "❌")
    log(f"    {compito_id:16s} BRUNO  {esito}  {dur:5.0f}s  {giri:2d} giri  "
        f"~{rec['token_stimati']:5d} tok  {nota[:45]}")
    return ok

def main():
    os.makedirs(BASE, exist_ok=True)
    lista = os.environ.get("MODELLI_LISTA")
    filtro = os.environ.get("SOLO_MODELLO")
    if lista:                      # per riprendere senza rifare i modelli gia' misurati
        noti = dict(MODELLI)
        modelli = [(v.strip(), noti.get(v.strip(), "")) for v in lista.split(",") if v.strip()]
    else:
        modelli = [m for m in MODELLI if not filtro or filtro in m[0]]
    log("=" * 66)
    log(f"IMPALCATURA — {len(modelli)} cervelli x {len(COMPITI)} compiti operativi")
    log("Stesso agente (Bruno), stessi compiti, cervelli di taglia diversa.")
    log(f"risultati: {OUT}")
    log("=" * 66)
    punteggi = {}
    for modello, taglia in modelli:
        log(f"--- {modello}  ({taglia}) ---")
        nudo = 0
        for cid, _, _ in COMPITI:
            try:
                if esegui_nudo(modello, cid):
                    nudo += 1
            except Exception as e:
                log(f"    !! {cid} nudo: {e}")
        con = 0
        for cid, testo, verifica in COMPITI:
            try:
                if esegui(modello, cid, testo, verifica):
                    con += 1
            except Exception as e:
                log(f"    !! {cid} bruno: {e}")
        punteggi[modello] = (nudo, con)
        log(f"    → NUDO {nudo}/{len(COMPITI)} · DENTRO BRUNO {con}/{len(COMPITI)}")
    log("=" * 66)
    log(f"  {'modello':46s} {'nudo':>6} {'bruno':>7} {'delta':>7}")
    for m, (a, b) in punteggi.items():
        log(f"  {m:46s} {a}/{len(COMPITI):<4} {b}/{len(COMPITI):<5} {b-a:+d}")
    log("FINITO — " + OUT)

if __name__ == "__main__":
    main()
