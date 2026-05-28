---
name: initIsoAmp
description: Calibrazione dinamica centralizzata + UDO GetIsoAmp/GetIsoAmp_k che mappano (frequenza, indice dinamica) a ampiezza lineare compensata ISO 226:2003.
sources: [includes/initIsoAmp.orc]
updated: 2026-05-28
---

# initIsoAmp

Cuore del **modello dinamico** del sistema. Mappa simbolico → fisico: i nomi `ppp..fff` diventano livelli `Phon` e `dBFS`, poi compensati per la curva isofonica della frequenza target.

## Calibrazione (header)

```
giPhonFFF  = 100   ; livello fff in Phon
giPhonStep = 6     ; step fra dinamiche

giDbfsFFF  = -30   ; livello fff in dBFS @1kHz
giDbfsStep = 6     ; step dBFS
```

Tutto il sistema si ritara cambiando queste 4 costanti.

## Tabelle di mappatura

| Tabella | Contenuto |
|---|---|
| `giDynamicsToPhon` | `[ppp .. fff]` → livello Phon, scalato da `giPhonFFF` e `giPhonStep` |
| `giDynamicsToDbfsRef` | `[ppp .. fff]` → livello dBFS @1kHz |

Indici dinamica: `0=ppp, 1=pp, 2=p, 3=mf, 4=f, 5=ff, 6=fff` (`giNumDynamics = 7`).

## Tabelle ISO 226:2003

`giIsoFreqs`, `giAf`, `giLu`, `giTf` — 32 punti dalla curva isofonica standard, frequenze 20-12500 Hz.

## UDO chiave

### `GetDynamicParams(iDynamicIndex) -> iPhon, iDbfsRef`
Legge le due tabelle di mappatura. Versione `kk, k` anche disponibile.

### `Interp(iX, iXp_tab, iFp_tab) -> iY`
Interpolazione lineare equivalente a `numpy.interp`. Trova l'indice corretto nella tabella `iXp_tab`, interpola fra i due punti contigui in `iFp_tab`. Gestisce clamp ai bordi.

### `PhonToSpl_i(iphon, ifreq) -> ispl`
Implementa la formula ISO 226:2003 punto-punto:
```
af = Interp(freq, giIsoFreqs, giAf)
lu = Interp(freq, giIsoFreqs, giLu)
tf = Interp(freq, giIsoFreqs, giTf)
af_value = 4.47e-3 * (10^(0.025·phon) - 1.15) + (0.4 · 10^((tf+lu)/10 - 9))^af
spl = (10/af) · log10(af_value) - lu + 94
```
Caso degenere (`af_value <= 0`): fallback lineare `tf + (phon/40) * 20`. A 1000 Hz esatto: `spl = phon` (definizione del Phon).

### `GetIsoAmp(iFreq, iDynamicIndex) -> iAmp_lineare`
Pipeline completa i-rate:
1. `GetDynamicParams` → `phon`, `dBFS_ref` @1kHz
2. `PhonToSpl_i(phon, freq)` → `dBSPL_target`
3. `offset = dBSPL_target - phon` (compensazione spettrale)
4. `dBFS_final = dBFS_ref + offset`
5. `ampdbfs(dBFS_final)`

### `GetIsoAmp_k(iDynamicIndex, iFreqStart, iFreqEnd) -> kAmp`
Variante per glissando. Calcola `iAmpStart`/`iAmpEnd` a i-rate, poi `expseg` fra i due. Usata da [[eventoSonoro]].

## Filosofia

Equivalenza esplicita con il vecchio metodo Python `generate_note`. Il documento e' "il pannello di controllo": tutta la calibrazione dinamica vive qui, non sparsa nei layer YAML.

## Consumatori

- [[eventoSonoro]] (`GetIsoAmp_k`)
- [[voce]] (`GetIsoAmp` per amp per-evento)
- Indirettamente: parametro YAML `dinamica` (DA SCRIVERE) → tradotto in `i_DynamicIndex` dal Python prima di entrare nello score.
