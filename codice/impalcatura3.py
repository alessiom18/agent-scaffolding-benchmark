#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMPALCATURA 3 — agente locale con VERIFICA (23/08/2026)

Nasce dai fallimenti misurati oggi su Bruno con i modelli piccoli:

  1. cercava nella cartella sbagliata (~/bruno_scratch invece della cartella di lavoro)
     e concludeva "il file non esiste, cercalo su Google";
  2. rispondeva senza guardare ("0 file" quando erano 3), bruciando 9.857 token;
  3. andava alla deriva: per cambiare "0 pezzi" in "5 pezzi" ha fatto 73 giri
     finendo a cercare batterie su Amazon.

Le quattro contromisure, tutte qui dentro:

  ANCORAGGIO   il modello non deve indovinare dove si trova: la prima cosa che vede
               e' l'albero reale della cartella, con i primi byte di ogni file.
  VERIFICA     dopo OGNI azione il risultato viene controllato davvero e l'esito
               (giusto/sbagliato, e cosa manca) torna al modello come fatto, non come
               opinione. Un modello che dichiara "fatto" senza aver fatto viene smentito.
  PERIMETRO    niente web e niente comandi fuori dalla cartella di lavoro quando il
               compito e' locale: la deriva su Amazon diventa impossibile per costruzione.
  BUDGET       pochi giri, e se due giri di fila non cambiano nulla si ferma. Meglio
               un fallimento pulito in 20 secondi che 73 chiamate inutili.

Uso da riga di comando:
    python3 impalcatura3.py "compito" --dir CARTELLA [--model gemma4:12b] [--giri 12]

Uso come libreria (e' cosi' che lo chiama il benchmark):
    from impalcatura3 import esegui
    esito = esegui(compito, cartella, modello)
"""
import json, os, re, subprocess, sys, time, urllib.request

OLLAMA = os.environ.get("IMP3_OLLAMA", "http://127.0.0.1:11434")
MAX_BYTE_FILE = 20000
COLORE = sys.stdout.isatty()

def c(t, code):
    return f"\033[{code}m{t}\033[0m" if COLORE else t

# ─────────────────────────────────────────────── strumenti
def _sicuro(base, percorso):
    """Impedisce di uscire dalla cartella di lavoro (niente ../.. né percorsi assoluti)."""
    p = os.path.realpath(os.path.join(base, percorso))
    if not p.startswith(os.path.realpath(base)):
        raise ValueError(f"fuori dalla cartella di lavoro: {percorso}")
    return p

def t_elenca(base, args):
    sub = args.get("cartella", ".") or "."
    d = _sicuro(base, sub)
    if not os.path.isdir(d):
        return {"errore": f"'{sub}' non è una cartella"}
    voci = []
    for n in sorted(os.listdir(d)):
        p = os.path.join(d, n)
        voci.append({"nome": n, "tipo": "cartella" if os.path.isdir(p) else "file",
                     "byte": os.path.getsize(p) if os.path.isfile(p) else None})
    return {"cartella": sub, "voci": voci, "quanti": len(voci)}

def t_leggi(base, args):
    f = args.get("file", "")
    p = _sicuro(base, f)
    if not os.path.isfile(p):
        vicini = []
        d = os.path.dirname(p) or base
        if os.path.isdir(d):
            vicini = sorted(os.listdir(d))[:12]
        return {"errore": f"il file '{f}' non esiste", "file_presenti_qui": vicini}
    return {"file": f, "contenuto": open(p, encoding="utf-8", errors="replace").read()[:MAX_BYTE_FILE]}

def t_scrivi(base, args):
    f = args.get("file", "")
    testo = args.get("contenuto", "")
    p = _sicuro(base, f)
    os.makedirs(os.path.dirname(p) or base, exist_ok=True)
    open(p, "w", encoding="utf-8").write(testo)
    return {"scritto": f, "byte": len(testo.encode()),
            "verifica": open(p, encoding="utf-8", errors="replace").read()[:400]}

def t_sostituisci(base, args):
    f = args.get("file", "")
    vecchio, nuovo = args.get("cerca", ""), args.get("sostituisci", "")
    p = _sicuro(base, f)
    if not os.path.isfile(p):
        return {"errore": f"il file '{f}' non esiste"}
    testo = open(p, encoding="utf-8", errors="replace").read()
    if vecchio not in testo:
        return {"errore": f"il testo cercato non compare in {f}",
                "contenuto_attuale": testo[:800]}
    nuovo_testo = testo.replace(vecchio, nuovo)
    open(p, "w", encoding="utf-8").write(nuovo_testo)
    return {"file": f, "sostituzioni": testo.count(vecchio),
            "contenuto_dopo": nuovo_testo[:800]}

def t_cerca(base, args):
    testo = args.get("testo", "")
    trovati = []
    for radice, _, files in os.walk(base):
        for n in files:
            p = os.path.join(radice, n)
            try:
                cont = open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for i, riga in enumerate(cont.splitlines(), 1):
                if testo.lower() in riga.lower():
                    trovati.append({"file": os.path.relpath(p, base), "riga": i,
                                    "testo": riga.strip()[:200]})
    return {"cercato": testo, "trovati": trovati[:40], "quanti": len(trovati)}

STRUMENTI = {
    "elenca_cartella": (t_elenca, "Elenca file e sottocartelle", {
        "cartella": {"type": "string", "description": "sottocartella, '.' per quella corrente"}}, []),
    "leggi_file": (t_leggi, "Legge il contenuto di un file", {
        "file": {"type": "string", "description": "percorso relativo del file"}}, ["file"]),
    "scrivi_file": (t_scrivi, "Crea o sovrascrive un file", {
        "file": {"type": "string"}, "contenuto": {"type": "string"}}, ["file", "contenuto"]),
    "sostituisci_in_file": (t_sostituisci, "Sostituisce un testo dentro un file esistente", {
        "file": {"type": "string"}, "cerca": {"type": "string"}, "sostituisci": {"type": "string"}},
        ["file", "cerca", "sostituisci"]),
    "cerca_testo": (t_cerca, "Cerca un testo in tutti i file della cartella di lavoro", {
        "testo": {"type": "string"}}, ["testo"]),
}

def schema_strumenti():
    out = []
    for nome, (_, desc, props, req) in STRUMENTI.items():
        out.append({"type": "function", "function": {
            "name": nome, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": req}}})
    return out

# ─────────────────────────────────────────────── ancoraggio
def fotografia(base, max_file=40):
    """Cosa c'e' davvero nella cartella: il modello parte da qui, non da un'ipotesi."""
    righe = []
    for radice, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith(".")][:12]
        rel = os.path.relpath(radice, base)
        pre = "" if rel == "." else rel + "/"
        for n in sorted(files)[:max_file]:
            p = os.path.join(radice, n)
            try:
                testa = open(p, encoding="utf-8", errors="replace").read(160).replace("\n", " ⏎ ")
            except Exception:
                testa = "(binario)"
            righe.append(f"  {pre}{n}  [{os.path.getsize(p)} byte]  {testa}")
    return "\n".join(righe) or "  (cartella vuota)"

def verifica_automatica(compito, base, prima):
    """Se non viene data una verifica esplicita, se ne deduce una dal compito:
    i nomi di file citati devono ESISTERE, e se il compito parla di modificare,
    il contenuto deve essere CAMBIATO rispetto a com'era all'inizio.
    Serve a rendere impossibile il caso visto oggi: il modello dichiara 'fatto'
    con zero chiamate agli strumenti e nessun file creato."""
    nominati = re.findall(r"\b([\w/\-]+\.(?:txt|md|csv|json|py|js|html|log|yaml|yml))\b", compito)
    attesi = [f for f in dict.fromkeys(nominati)]
    if not attesi:
        return None                      # nessun file citato: non so cosa verificare
    def _v(cartella):
        mancanti, immutati = [], []
        for f in attesi:
            p = os.path.join(cartella, f)
            if not os.path.exists(p):
                mancanti.append(f); continue
            ora = open(p, encoding="utf-8", errors="replace").read()
            if f in prima and prima[f] == ora:
                immutati.append(f)
        if mancanti:
            return False, "Non esiste ancora: " + ", ".join(mancanti)
        if immutati and re.search(r"modific|sostitu|cambia|aggiorn", compito, re.I):
            return False, "Non è cambiato nulla in: " + ", ".join(immutati)
        return True, ""
    return _v

SISTEMA = """Sei un agente che LAVORA su una cartella, in locale. Non hai accesso a internet.

REGOLE, in ordine di importanza:
1. Lavori SOLO dentro la cartella di lavoro che ti viene mostrata. Non esistono altre cartelle.
   Se cerchi un file, e' li' dentro: usa elenca_cartella o cerca_testo, non immaginare percorsi.
2. NON dichiarare mai di aver fatto una cosa che non hai fatto con uno strumento.
   Dopo ogni tua azione ti viene detto il risultato REALE: se dice che e' andata male, e' andata male.
3. Una cosa alla volta, con lo strumento giusto. Per cambiare una riga dentro un file usa
   sostituisci_in_file, non riscrivere tutto a memoria.
4. Quando hai finito e la verifica lo conferma, rispondi con una riga sola che inizia con FATTO:
   seguita da cosa hai fatto. Se non ci riesci, rispondi NON RIUSCITO: e il motivo preciso.

Non chiedere conferme: agisci."""

# ─────────────────────────────────────────────── ciclo
def _chiama(modello, messaggi, num_ctx, timeout=600):
    corpo = json.dumps({"model": modello, "messages": messaggi, "tools": schema_strumenti(),
                        "stream": False, "think": False,
                        "options": {"num_predict": 1200, "temperature": 0.1, "num_ctx": num_ctx},
                        "keep_alive": "10m"}).encode()
    req = urllib.request.Request(OLLAMA + "/api/chat", data=corpo,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def esegui(compito, cartella, modello="gemma4:12b", max_giri=12, verifica=None,
           num_ctx=16384, verboso=True):
    """verifica: funzione(cartella) -> (ok: bool, cosa_manca: str). Se c'e', dopo ogni
    giro il suo esito viene RIMANDATO AL MODELLO: e' quello che impedisce di dichiarare
    'fatto' a vuoto e quello che permette di correggere la rotta subito."""
    base = os.path.realpath(cartella)
    os.makedirs(base, exist_ok=True)
    t0 = time.time()
    prima = {}
    for radice, _, files in os.walk(base):
        for n in files:
            p = os.path.join(radice, n)
            try:
                prima[os.path.relpath(p, base)] = open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                pass
    if verifica is None:
        verifica = verifica_automatica(compito, base, prima)
    messaggi = [
        {"role": "system", "content": SISTEMA},
        {"role": "user", "content":
            f"CARTELLA DI LAVORO: {base}\n\nCosa c'e' dentro, adesso:\n{fotografia(base)}\n\n"
            f"COMPITO:\n{compito}"},
    ]
    giri = 0
    chiamate = []
    firma_precedente = None
    fermi = 0
    while giri < max_giri:
        giri += 1
        try:
            d = _chiama(modello, messaggi, num_ctx)
        except Exception as e:
            return {"ok": False, "motivo": f"il modello non risponde: {e}", "giri": giri,
                    "secondi": round(time.time() - t0, 1), "chiamate": chiamate}
        msg = d.get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        testo = (msg.get("content") or "").strip()

        if tool_calls:
            messaggi.append({"role": "assistant", "content": msg.get("content", ""),
                             "tool_calls": tool_calls})
            for tc in tool_calls:
                fn = tc.get("function", {}) or {}
                nome = fn.get("name")
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                # il modello piccolo infila virgolette dentro le stringhe: le tolgo
                args = {k: (v.strip('"').strip("'") if isinstance(v, str) else v)
                        for k, v in (args or {}).items()}
                if nome not in STRUMENTI:
                    esito = {"errore": f"lo strumento '{nome}' non esiste",
                             "strumenti_disponibili": list(STRUMENTI)}
                else:
                    try:
                        esito = STRUMENTI[nome][0](base, args)
                    except Exception as e:
                        esito = {"errore": str(e)}
                chiamate.append({"strumento": nome, "argomenti": args,
                                 "esito_ok": "errore" not in esito})
                if verboso:
                    segno = c("✗", "31") if "errore" in esito else c("✓", "32")
                    print(f"  {segno} {nome}({json.dumps(args, ensure_ascii=False)[:90]})")
                messaggi.append({"role": "tool",
                                 "content": json.dumps(esito, ensure_ascii=False)[:4000]})
        else:
            messaggi.append({"role": "assistant", "content": testo})

        # ── VERIFICA: il fatto batte la dichiarazione ──
        if verifica:
            ok, manca = verifica(base)
            if ok:
                return {"ok": True, "motivo": "verificato", "giri": giri,
                        "secondi": round(time.time() - t0, 1), "chiamate": chiamate,
                        "testo": testo}
            if not tool_calls:
                # ha parlato senza agire, e il risultato non c'e': glielo dico e basta
                messaggi.append({"role": "user", "content":
                    f"Ho controllato la cartella: NON è ancora fatto. {manca}\n"
                    f"Agisci con gli strumenti, non descrivere."})
        elif not tool_calls:
            scritture = [x for x in chiamate
                         if x["strumento"] in ("scrivi_file", "sostituisci_in_file") and x["esito_ok"]]
            if testo.upper().startswith("NON RIUSCITO"):
                return {"ok": False, "motivo": testo[:300], "giri": giri,
                        "secondi": round(time.time() - t0, 1), "chiamate": chiamate, "testo": testo}
            if testo.upper().startswith("FATTO") and scritture:
                return {"ok": True, "motivo": testo[:300], "giri": giri,
                        "secondi": round(time.time() - t0, 1), "chiamate": chiamate, "testo": testo}
            # dichiara di aver finito senza aver toccato nulla: lo smentisco e lo rimando al lavoro
            messaggi.append({"role": "user", "content":
                "Non hai usato nessuno strumento, quindi sul disco non è cambiato niente. "
                "Non descrivere quello che faresti: fallo, chiamando gli strumenti."})

        # ── anti-stallo: due giri identici e ci si ferma ──
        firma = json.dumps([(x["strumento"], x["argomenti"]) for x in chiamate[-2:]],
                           ensure_ascii=False, sort_keys=True)
        if firma == firma_precedente:
            fermi += 1
            if fermi >= 2:
                return {"ok": False, "motivo": "fermo: ripete la stessa azione senza avanzare",
                        "giri": giri, "secondi": round(time.time() - t0, 1), "chiamate": chiamate}
        else:
            fermi = 0
        firma_precedente = firma

    ok, manca = (verifica(base) if verifica else (False, "budget di giri esaurito"))
    return {"ok": ok, "motivo": "verificato" if ok else f"budget esaurito. {manca}",
            "giri": giri, "secondi": round(time.time() - t0, 1), "chiamate": chiamate}

# ─────────────────────────────────────────────── riga di comando
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Agente locale con verifica")
    ap.add_argument("compito")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--model", default=os.environ.get("IMP3_MODEL", "gemma4:12b"))
    ap.add_argument("--giri", type=int, default=12)
    a = ap.parse_args()
    r = esegui(a.compito, a.dir, a.model, max_giri=a.giri)
    print()
    print(c("✅ " + r["motivo"], "32") if r["ok"] else c("❌ " + r["motivo"], "31"))
    print(f"   {r['giri']} giri · {r['secondi']}s · {len(r['chiamate'])} chiamate")
