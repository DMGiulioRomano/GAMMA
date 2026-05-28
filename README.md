# GAMMA

Composer generativo per Csound. Trasforma una partitura YAML in una composizione multi-layer renderizzata in WAV con plot PDF della partitura.

Estratto dal repo [`delta`](https://github.com/DMGiulioRomano/delta) (branch `adaptiveSystem`) come progetto indipendente.

## Pipeline

```
yaml/<partitura>.yaml
   │
   ▼  generative_composerYaml2.py
   │
composizioni_generate/
   ├── csd/layers/*.csd           # un csd per layer
   ├── csd/sections/*_assembler.csd
   ├── csd/<nome>_final_assembler.csd
   ├── wav/                       # rendering audio per layer/sezione/finale
   └── <nome>_partitura.pdf       # plot grafico della partitura
```

## Requisiti

- Python 3.11
- [Csound](https://csound.com/) (binario `csound` in `PATH`)
- Pacchetti Python: `numpy`, `matplotlib`, `seaborn`, `pyyaml`

```bash
pip install numpy matplotlib seaborn pyyaml
```

## Uso

```bash
make                  # default: genera csd + render della partitura Gamma
make YAML=Beta2       # usa yaml/Beta2.yaml
make clean            # rimuove composizioni_generate/ e sco/
```

Oppure diretto:

```bash
python3.11 generative_composerYaml2.py yaml/Gamma.yaml
```

## Struttura

| Path | Contenuto |
|------|-----------|
| `generative_composerYaml2.py` | Composer principale: parser YAML, generatore CSD, plot partitura |
| `yaml/` | Partiture: `Gamma`, `Beta`, `Beta2`, `guida` (esempio commentato), `tables.yaml` (tabelle condivise) |
| `includes/` | Moduli Csound: `comportamento`, `eventoSonoro`, `voce`, `inviluppoSezione`, `waveshaper`, `NonlinearFunc`, `pfield_comp`, `GenPythagFreqs`, `initIsoAmp`, `gamma_utils` |
| `Makefile` | Target `all`, `py`, `clean` |
| `composizioni_generate/` | Output (ignorato da git) |
| `wav/` | Audio storico esperimenti (ignorato da git) |

## Modello compositivo

Una partitura YAML è una lista di **sezioni**. Ogni sezione contiene **layer** con:

- `lifespan: [start, end]` — frazione temporale di vita del layer nella sezione (0.0–1.0)
- `num_attivazioni` — quante voci nascono nel lifespan
- `timing_model` — `accelerando`, `rallentando`, `uniform`, con `shape`
- `stato_iniziale` / `stato_finale` — parametri (ottava, registro, durata armonica, densità cluster, dinamica, jitter, nonlinear_mode, inviluppo) con range, distribuzione e interpolazione

Multi-documento YAML (`---`) per più composizioni nello stesso file.

### Modalità

- **veteran_mode** (sezione): non re-renderizza, eredita wav esistenti — utile per iterare su una singola sezione.
- **MODALITA_PARTITURA_ASCOLTO**: plot multi-pagina PDF.
- **offset_inizio** sezione: positivo (silenzio) o negativo (crossfade fra sezioni).
- Parallelizzazione: sezioni renderizzate in parallelo con Csound multi-thread.

## Vedi anche

Repo correlati nello stesso ecosistema sintesi Csound:
- [`delta`](https://github.com/DMGiulioRomano/delta) — motore Csound adattivo con stati e transizioni
- [`PythonGranularEngine`](https://github.com/DMGiulioRomano/PythonGranularEngine) — sintesi granulare YAML → SCO → AIF

## Autore

Giulio Romano De Mattia
