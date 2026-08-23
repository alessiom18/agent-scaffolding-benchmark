# L'impalcatura non è neutra

**Dieci modelli LLM messi dentro lo stesso agente. Uno solo sopravvive: quello su cui l'agente
è stato messo a punto. Due che risolvono tutti i compiti da soli, dentro l'agente non ne
risolvono nessuno.**

Banco di prova su modelli che girano **interamente in locale** (Ollama, una RTX 3060 da 12 GB e
un portatile) — nessun servizio cloud, nessuna API a pagamento.
Di [SudoWAI](https://sudowai.com), Livorno · 23 agosto 2026.

📊 **Tutte le risposte e i grafici:** [sudowai.com/confronto-modelli](https://sudowai.com/confronto-modelli/)
📕 **La ricerca precedente** («non esiste il modello migliore»): [local-llm-benchmark](https://github.com/alessiom18/local-llm-benchmark)

---

## Il risultato

Ogni modello è stato misurato **due volte sugli stessi cinque compiti operativi**:

- **da solo** — i dati già nel prompt, deve solo dare la risposta giusta;
- **dentro l'agente** — deve cercarsi i dati con gli strumenti e *fare* la cosa davvero.

La verifica non guarda cosa ha scritto il modello: guarda il **filesystem**. Il file esiste?
Il contenuto è quello giusto? Nessuna opinione, nessun giudice.

| Modello | Da solo | Dentro l'agente | Δ | Tempo nell'agente |
|---|---:|---:|---:|---:|
| **Gemma 4 12B** *(quello su cui l'agente è tarato)* | **5/5** | **5/5** | **0** | 165 s |
| Qwen 3.5 4B | 4/5 | 2/5 | −2 | 266 s |
| Qwen 3 4B | 5/5 | 1/5 | −4 | 3 447 s |
| Qwen 2.5 3B | 5/5 | **0/5** | −5 | 245 s |
| Qwen 3.5 0.8B | 5/5 | **0/5** | −5 | 164 s |
| Cogito 8B | 4/5 | **0/5** | −4 | 1 788 s |
| Phi-4 mini 3.8B | 3/5 | 0/5 | −3 | 813 s |
| Qwen 2.5 0.5B | 2/5 | 0/5 | −2 | 20 s |
| Gemma 2B *(senza tool-calling)* | 2/5 | 0/5 | −2 | 98 s |
| BitNet b1.58 2B | 0/5 | 0/5 | 0 | 110 s |

Due numeri da tenere: **Qwen 2.5 3B e Qwen 3.5 0.8B fanno cinque su cinque da soli e zero
dentro l'agente.** Non sono modelli scarsi messi alla prova: sono modelli capaci, resi
inservibili dall'impalcatura.

E il costo non è solo in punteggio: Cogito 8B ha bruciato **1 788 secondi con zero chiamate agli
strumenti** — mezz'ora a parlare senza mai agire. Qwen 3 4B ne ha consumati **3 447** per otto
compiti, riuscendone due.

## Perché succede

Guardando cosa fanno davvero, i fallimenti si ripetono uguali:

1. **Cerca nel posto sbagliato.** Otto giri a frugare in una cartella che non era quella di
   lavoro, conclusione: *«il file non esiste, cercalo su Google»*. Il file era lì.
2. **Dichiara senza verificare.** *«0 file nella sottocartella»* — erano tre. Un giro, 1,2
   secondi, 9 857 token di contesto bruciati per una risposta sbagliata data a occhi chiusi.
3. **Va alla deriva, e l'agente la amplifica.** Compito: cambiare `0 pezzi` in `5 pezzi` in una
   riga di testo. Risultato: **73 giri**, finiti a cercare batterie su Amazon.

Nessuna di queste è una carenza di conoscenza. Sono carenze di **procedura** — e l'impalcatura,
invece di correggerle, le moltiplica.

## La contro-prova

In [`codice/impalcatura3.py`](codice/impalcatura3.py) c'è un agente costruito sulle quattro
contromisure che i fallimenti indicano:

- **ancoraggio** — la prima cosa che il modello vede è l'albero reale della cartella, con i primi
  byte di ogni file: non deve indovinare dove si trova;
- **verifica** — dopo ogni azione il risultato viene controllato sul disco e l'esito torna al
  modello *come fatto*. Chi dichiara «fatto» senza aver fatto viene smentito e rimandato al lavoro;
- **perimetro** — niente web, niente percorsi fuori dalla cartella: la deriva su Amazon non viene
  corretta, diventa **impossibile per costruzione**;
- **budget** — due giri identici e ci si ferma. Meglio un fallimento pulito in venti secondi che
  settantatré chiamate.

Sugli stessi compiti che avevano fatto crollare i modelli:

| Compito | Agente tarato su un modello | Agente con verifica |
|---|---|---|
| trova un codice sepolto e scrivilo in un file | 8 giri, file mai creato | **2 giri, file corretto** |
| cambia una riga dentro un file | **73 giri**, finito su Amazon | **1 giro, 16 secondi** |

Lo stesso Qwen 3.5 4B che nell'agente originale faceva 2/5 risolve il compito in **2 giri**.
Non era il modello a non essere all'altezza.

## Cosa c'è in questo repo

```
dati/        le risposte grezze, integrali, di ogni prova (JSONL)
codice/      gli script del banco di prova + l'agente con verifica
immagini/    le immagini generate per i test di lettura (con ground truth certa)
```

I compiti sono cinque, tutti verificabili sul filesystem: trovare un codice sepolto in una
sottocartella e scriverlo in un file, contare i file, modificare una riga lasciando il resto
intatto, incrociare listino e giacenze per calcolare un totale, produrre un riepilogo.

## Riprodurlo

Serve [Ollama](https://ollama.com) e i modelli scaricati. Poi:

```bash
python3 codice/bench_impalcatura.py                    # tutti i modelli, due modalità
MODELLI_LISTA="gemma4:12b,qwen3.5:4b" python3 codice/bench_impalcatura.py   # solo alcuni
```

E per usare l'agente con verifica su una cartella qualsiasi:

```bash
python3 codice/impalcatura3.py "il compito" --dir /percorso --model gemma4:12b
```

## Cosa non dimostra

Cinque compiti su una famiglia sola (manipolazione di file di testo), un solo agente di
partenza, una sola macchina. Non è una classifica di modelli e non dice quale agente sia il
migliore in assoluto.

Dice una cosa sola, ma con i numeri sotto: **un'impalcatura ottimizzata su un modello smette di
essere un'impalcatura e diventa un vincolo.** Se scegliete un agente guardando come si comporta
col modello per cui è stato scritto, non state misurando l'agente.

---

*Tutto in locale, nessun dato uscito dalla macchina. [SudoWAI](https://sudowai.com) — l'AI del tuo lavoro.*
