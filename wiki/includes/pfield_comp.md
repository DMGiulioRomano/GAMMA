---
name: pfield_comp
description: UDO calcFrequenza — mappa (ottava, registro, ritmo) a frequenza Hz leggendo dalla tabella di intonazione pitagorica.
sources: [includes/pfield_comp.udo]
updated: 2026-05-28
---

# pfield_comp

Singolo UDO: `calcFrequenza`. Il file storicamente conteneva validatori e un calcolatore di ampiezza (`calcAmpiezza`) usati dalla vecchia `Comportamento` — tutti rimossi insieme allo strumento legacy.

## Firma

```
iFreq calcFrequenza iOttava, iRegistro, iRitmoCorrente
```

## Logica

```
idx_ottava   = int(iOttava * $INTERVALLI)
idx_registro = idx_ottava + int((iRegistro * $INTERVALLI) / $REGISTRI)
offset       = max(1, idx_registro + iRitmoCorrente)
iFreq        = min( table(offset, gi_Intonazione), sr/2 - 1 )
```

Mappa **(ottava, registro, ritmo)** alla tabella di intonazione `gi_Intonazione` riempita da [[GenPythagFreqs]].

## Punto chiave

Il **ritmo corrente modula la frequenza**: lo stesso `(ottava, registro)` produce note diverse a seconda di `iRitmoCorrente`. Effetto compositivo: la texture pitch dei layer cluster/scintillii nasce dal flusso ritmico, non da una scala fissa.

## Macro richieste

`$INTERVALLI`, `$REGISTRI` — definite nell'header CSD generato dal Python.

## Consumatori

Chiamato due volte per evento da [[voce]]: una per `Freq1` (partenza), una per `Freq2` (arrivo, glissando).
