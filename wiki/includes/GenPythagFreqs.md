---
name: GenPythagFreqs
description: UDO che genera tabella di frequenze pitagoriche (catena di quinte 3/2) ridotte all'ottava, ordinate, replicate su N ottave.
sources: [includes/GenPythagFreqs.udo]
updated: 2026-05-28
---

# GenPythagFreqs

UDO (`opcode GenPythagFreqs, i, iiii`). Riempie una f-table con frequenze derivate dall'accordatura pitagorica.

## Firma

```
iRes GenPythagFreqs iFund, iNumIntervals, iNumOctaves, iTblNum
```

| Input | Significato |
|---|---|
| `iFund` | frequenza fondamentale (Hz) |
| `iNumIntervals` | numero di intervalli per ottava (catena di quinte) |
| `iNumOctaves` | numero di ottave da replicare |
| `iTblNum` | numero della f-table da riempire |

Output: `iRes = 1` se completato.

## Algoritmo

1. Per ogni ottava `iOctave`:
   - parte da rapporto 1 → scrive `iFund * 2^iOctave` come primo valore
   - itera moltiplicando per `3/2` (quinta giusta)
   - riduce il rapporto modulo 2 finché `<2` (riconduce all'ottava)
   - genera `iNumIntervals` rapporti
2. Bubble sort dei valori all'interno dell'ottava
3. Scrive tutto in `iTblNum` via `tabw_i`

## Uso nel sistema

- Riempie `gi_Intonazione` consumata da `calcFrequenza` ([[pfield_comp]]).
- Macro `$INTERVALLI` e `$REGISTRI` controllano la suddivisione usata dal calcolo `(ottava, registro) → freq`.
- Collegato concettualmente ai parametri [[parametri/ottava]] e [[parametri/registro]] (DA SCRIVERE).

## Note

- Bubble sort è O(n²) ma eseguito una volta sola in init.
- Nessuna gestione di rapporti alternativi (terza maggiore, ecc.) — solo quinte.
