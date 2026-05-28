# Indice Wiki GAMMA

Catalogo pagine. Una riga per pagina: link + one-liner.

## Pipeline

- [pipeline](pipeline.md) — flusso end-to-end yaml → csd → csound → wav.

## Concetti

- [maschera_tendenza](concepts/maschera_tendenza.md) — DNA stocastico di un layer, interpolato fra stato_iniziale e stato_finale.

## Parametri

_(da popolare via ingest)_

## Composizioni

- [Gamma](composizioni/Gamma.md) — partitura principale, 4 sezioni, cluster e scintillii.

## Includes Csound

### Strumenti (`.orc`)
- [eventoSonoro](includes/eventoSonoro.md) — singolo evento, glissando esponenziale, ampiezza isofonica k-rate, Mid/Side stereo.
- [voce](includes/voce.md) — generatore eventi di layer con dynamics index, glissando ottava/registro, inviluppo di sezione, safety buffer.
- [initIsoAmp](includes/initIsoAmp.md) — calibrazione dinamica centralizzata + UDO `GetIsoAmp`/`GetIsoAmp_k` con curva ISO 226:2003.

### UDO (`.udo`)
- [GenPythagFreqs](includes/GenPythagFreqs.md) — genera tabella di frequenze pitagoriche (catena di quinte) replicata su N ottave.
- [NonlinearFunc](includes/NonlinearFunc.md) — generatore ritmi caotici/periodici, 4 modi (convergente, periodico, caotico, caos vero).
- [pfield_comp](includes/pfield_comp.md) — `calcFrequenza`: mappa (ottava, registro, ritmo) → Hz via `gi_Intonazione`.

## Python

_(da popolare via ingest)_
