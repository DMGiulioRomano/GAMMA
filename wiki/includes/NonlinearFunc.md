---
name: NonlinearFunc
description: UDO generatore di valori ritmici da deterministico a caotico, 4 modalita' (convergente, periodico, caotico, caos vero).
sources: [includes/NonlinearFunc.udo]
updated: 2026-05-28
---

# NonlinearFunc

UDO (`opcode NonlinearFunc, i, ippo`). Restituisce un intero ritmico in `[iMinVal, iMaxVal]` partendo dal valore precedente.

## Firma

```
iResult NonlinearFunc iX, iMode [, iMinVal [, iMaxVal]]
```

| Input | Default | Significato |
|---|---|---|
| `iX` | — | valore precedente (seme) |
| `iMode` | — | 0 conv, 1 periodico, 2 caotico, 3 caos vero |
| `iMinVal` | 1 | minimo output |
| `iMaxVal` | 35 | massimo output |

`iX` viene clampato in `[1, 100]`.

## Modalita'

- **0 — Convergente**: mappa logistica con `r=2.8`, converge a punto fisso.
- **1 — Periodica**: `|sin(x·π/18) · cos(x·π/10)| * 20 + 10` → oscillazione regolare.
- **2 — Caotica deterministica**: logistica `r=3.99` + piccolo noise (±0.05). Mappato nel range richiesto.
- **3 — Caos vero** (default): 60% deterministico (mix di sin/cos/tan con seed × costanti irrazionali) + 40% random uniforme + perturbazione periodica ogni 7 step.

Risultato finale: `round(iTemp)` clampato in `[iMinVal, iMaxVal]`.

## Ruolo nel sistema

- Chiamato da [[voce]] nel ramo `generateNewRhythm` quando gli step ritmici espliciti finiscono.
- Mappato in YAML via `nonlinear_mode` nello stato del layer (es. `{choices: [1, 0], weights: [0.8, 0.2]}`).
- I "ritmi" generati alimentano poi `calcFrequenza` ([[pfield_comp]]) come terzo parametro (offset nella tabella di intonazione) e definiscono la suddivisione `i_DurataArmonica / i_RitmoCorrente`.

## Note

- Mode 3 è non riproducibile fra run (usa `random:i`).
- Mode 2 introduce piccolo rumore ma resta semi-deterministico.
- Vedi parametro YAML `tipo_ritmi` (DA SCRIVERE) per la sequenza esplicita iniziale.
