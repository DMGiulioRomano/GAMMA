---
name: eventoSonoro
description: Strumento eventoSonoro — singolo evento, oscillatore con glissando esponenziale, ampiezza isofonica k-rate, spazializzazione Mid/Side.
sources: [includes/eventoSonoro.orc]
updated: 2026-05-28
---

# eventoSonoro

`instr eventoSonoro`. Sintetizzatore del **singolo evento** schedulato da [[voce]] per ogni step ritmico interno al layer.

## p-fields

| Pos | Nome | Significato |
|---|---|---|
| p4 | `i_DynamicIndex` | indice dinamica (per `GetIsoAmp_k`) |
| p5 | `ifreq1` | freq iniziale (Hz, clampata `[20, sr/2]`) |
| p6 | `iwhichZero` | offset di fase (intero, scala in radianti) |
| p7 | `iHR` | "rateo" spaziale — periodo Mid/Side `2π/HR` |
| p8 | `ifreq2` | freq finale (glissando) |
| p9 | `ifn_shape` | f-table inviluppo locale (default 2 = abs-sin) |
| p10 | `id_evento` | id evento |
| p11 | `id_comportamento` | id layer |
| p12 | `i_senso` | direzione spaziale, default 1 |
| p13 | `i_ifn_section_env` | f-table inviluppo sezione (>20 attivo) |
| p14 | `i_section_start_time` | t inizio sezione assoluto |
| p15 | `i_section_duration` | durata sezione |

## Inviluppi

- **Locale** (`kEnv_local`): se `ifn_shape == 2` → `abs(sin(krad * iHR / 2))` (rectified sin). Altrimenti → lettura diretta dalla f-table.
- **Sezione** (`kEnv_section`): attivo solo se `i_ifn_section_env > 20 && section_duration > 0`. Indice normalizzato `(time_now - section_start) / section_duration`, letto con `tablei`.

## Glissando

```
ifreq1 > ifreq2  → expseg 1 → 0.0001    decrescente
ifreq1 < ifreq2  → expseg 0.0001 → 1    crescente
ifreq1 = ifreq2  → costante
```
Mappato linearmente sul range `[ifreq2, ifreq1]` (o viceversa).

## Ampiezza

`kamp GetIsoAmp_k i_DynamicIndex, ifreq1, ifreq2` — interpola l'ampiezza isofonica fra inizio e fine (vedi [[initIsoAmp]]).

## Spazializzazione Mid/Side

```
krad   = iradi + (ktab * 2π/HR * i_senso)
kMid   = cos(krad)
kSide  = sin(krad)
aL     = (aMid + aSide) / √2
aR     = (aMid - aSide) / √2
```
Movimento orbitale stereo controllato da `krad`. `ktab` letto dall'inviluppo locale (`kndx_local line 0, p3, 1`).

## DC block

`asigEnv dcblock asigEnvPre` — rimuove offset DC introdotto dalla moltiplicazione.

## Debug

Macro `$DEBUG_Evento_print_Pfields`: se `gi_debug >= 2` scrive `.sco` file con tutti i p-fields per evento + un master `All.sco`.

## Errore critico

Se `p7 == 0` (HR nullo) → `exitnow`. Il divide-by-zero nel periodo distruggerebbe il render.
