# CLAUDE.md — GAMMA

Guida per Claude Code in questo repo. Istruzioni operative + schema wiki.

**Lingua:** italiano. No emoji. Tono terso (caveman-friendly), nessun filler.

---

## 1. Cosa è il repo

Composizione algoritmica assistita.

- **Partitura** = `yaml/*.yaml`. Maschere di tendenza, non valori fissi: definisco spazi di possibilità, il sistema campiona stocasticamente.
- **Orchestratore** = `generative_composerYaml2.py` (~1900 righe). Legge YAML, genera `.csd` per ogni layer/sezione, lancia Csound, assembla i WAV.
- **DSP** = `includes/*.orc` + `*.udo`. Strumenti, inviluppi, waveshaper, util.
- **Output** = `composizioni_generate/{csd,wav,logs}/` + `composizioni_generate/<nome>_partitura.pdf` (plot).

Pipeline:
```
yaml/<nome>.yaml
  → python3.11 generative_composerYaml2.py yaml/<nome>.yaml
    → composizioni_generate/csd/*.csd (uno per layer)
      → csound (per ogni csd) → wav/<layer>.wav
        → csd assembler per sezione → wav/<sezione>.wav
          → csd assembler finale → wav/<nome>.wav
```

### Comandi

```bash
make                        # default: lancia python su YAML=Gamma
make YAML=Beta2             # cambia partitura
make clean                  # rimuove composizioni_generate/ e sco/
```

`make py` è l'unico step reale; python fa tutto (genera csd, lancia csound, assembla).

### File chiave

- [generative_composerYaml2.py](generative_composerYaml2.py) — classi: `GenerativeComposer` (genera), `TimeScheduler` (timing), `CompositionDebugger` (plot PDF). Funzioni assemblaggio: `plan_render_jobs`, `execute_layer_rendering_and_collect_data`, `execute_section_assembly`, `execute_final_assembly`.
- [yaml/guida.yaml](yaml/guida.yaml) — documentazione canonica dei parametri (commenti inline). **Fonte di verità per la sintassi YAML.**
- [yaml/tables.yaml](yaml/tables.yaml) — tabelle (inviluppi, dinamiche, ritmi).
- [yaml/Gamma.yaml](yaml/Gamma.yaml) — partitura concreta (opera per CIM 2026).
- [includes/](includes/) — DSP Csound riusabile.

### Gerarchia concettuale

```
Composizione (file YAML, lista documenti)
  └─ Sezione (blocco temporale, durata, ratio_temporale, offset_inizio)
      └─ Layer (flusso parallelo, lifespan, num_attivazioni, timing_model)
          └─ Stato iniziale / Stato finale (maschera tendenza interpolata)
              └─ Parametri sonori (ottava, registro, durata_armonica, densità_cluster, ...)
```

---

## 2. Wiki — schema e regole

Costruiamo wiki Karpathy-style: artefatto markdown persistente, interlinkato, mantenuto incrementalmente. Sorgenti immutabili, wiki rigenerata/aggiornata da Claude.

### Layout

```
wiki/
  index.md           # catalogo: ogni pagina, link, one-liner
  log.md             # append-only: ingest, query, lint con timestamp
  pipeline.md        # flusso end-to-end yaml→wav
  concepts/          # maschera_tendenza.md, layer.md, sezione.md, timing_model.md, lifespan.md, ...
  parametri/         # uno per parametro: ottava.md, durata_armonica.md, dinamica.md, ...
  composizioni/      # Gamma.md, Beta.md, Beta2.md — analisi per partitura
  includes/          # uno per .orc/.udo: comportamento.md, waveshaper.md, ...
  python/            # mappa funzioni/classi di generative_composerYaml2.py
```

### Sorgenti grezze (immutabili)

Wiki **non riscrive mai**:
- `yaml/*.yaml`
- `generative_composerYaml2.py`
- `includes/*`
- `Makefile`

Artefatti generati (`composizioni_generate/`, `wav/`, `sco/`) sono out-of-scope per la wiki tranne come dati di sessioni passate citati nel log.

### Convenzioni pagine

- Frontmatter YAML obbligatorio:
  ```yaml
  ---
  type: concept|parametro|composizione|include|python|pipeline
  sources: [yaml/Gamma.yaml, generative_composerYaml2.py:L450-520]
  updated: 2026-05-28
  ---
  ```
- Wikilink Obsidian-style: `[[maschera_tendenza]]`, `[[parametri/ottava]]`.
- Citazioni codice con path:linea: `[generative_composerYaml2.py:133](generative_composerYaml2.py#L133)`.
- Contraddizioni con sorgenti: blocco `> CONFLITTO:` esplicito.

### index.md

Una riga per pagina:
```
- [maschera_tendenza](concepts/maschera_tendenza.md) — DNA stocastico di un layer, interpolato fra stato_iniziale e stato_finale.
```
Categorie: Concetti, Parametri, Composizioni, Includes, Python, Pipeline.

### log.md

Append-only. Prefisso parseabile:
```
## [2026-05-28] ingest | yaml/Gamma.yaml
## [2026-05-28] query  | come funziona accelerando in timing_model
## [2026-05-28] lint   | pass settimanale
```
Grep: `grep "^## \[" wiki/log.md | tail -10`.

---

## 3. Operazioni

### Ingest

Quando l'utente dice "ingest X" (es. `yaml/Beta2.yaml`, un nuovo `.orc`, un articolo PDF):

1. Leggi sorgente intera.
2. Riassumi key takeaways in 3-5 punti, chiedi conferma su cosa enfatizzare.
3. Crea/aggiorna pagina dedicata (`composizioni/Beta2.md`, `includes/X.md`).
4. Tocca pagine collegate: parametri usati, concetti, includes referenziati.
5. Aggiorna `index.md`.
6. Append `log.md`.

Una singola partitura YAML può toccare 10-20 pagine wiki (un parametro per file). OK.

### Query

Utente fa domanda → leggi `index.md` → scegli pagine rilevanti → sintetizza risposta con citazioni `[[wikilink]]` e `path:linea`. Se la sintesi è non banale, **proponi di filarla come nuova pagina** (`wiki/<categoria>/<slug>.md`).

### Lint

Comando "lint wiki" o "audit wiki":
- contraddizioni fra pagine
- claim superati da sorgenti nuove
- pagine orfane (nessun inbound link)
- concetti citati senza pagina propria
- gap dati colmabili leggendo il Python

Output: lista azioni proposte, l'utente sceglie.

---

## 4. Stile e disciplina

- **Risposte terse.** Caveman-friendly già attivo globalmente. Niente "Certo! Procedo con...".
- **Niente file inutili.** Non creare README, summary, planning doc se non richiesti. La wiki è l'unico artefatto persistente.
- **Niente refactor del Python** salvo richiesta. È sorgente immutabile dal punto di vista wiki.
- **Niente modifiche YAML** salvo richiesta esplicita. Sono partiture, non config.
- **Plot/PDF** generati dal Python (`CompositionDebugger`): citarli, non rigenerarli a mano.
- **Csound errors:** quotare verbatim dai log in `composizioni_generate/logs/`.

---

## 5. Stack tecnico

- Python 3.11 (vedi `Makefile`). Dipendenze: `numpy`, `pyyaml`, `matplotlib`, `seaborn`.
- Csound (CLI `csound`). Subprocess chiamato dal Python.
- Includes Csound in `includes/`, paths assoluti iniettati nei `.csd` generati.

---

## 6. Bootstrap wiki

Al primo `/init` wiki, scaffold minimo:

1. `wiki/index.md` vuoto con sezioni.
2. `wiki/log.md` con primo entry `ingest | bootstrap`.
3. `wiki/pipeline.md` da questo CLAUDE.md sezione 1.
4. `wiki/concepts/maschera_tendenza.md` da `yaml/guida.yaml`.
5. `wiki/composizioni/Gamma.md` da `yaml/Gamma.yaml`.

Poi ingest incrementale guidato dall'utente.
