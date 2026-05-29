---
type: composizione
sources: [yaml/Gamma.yaml]
updated: 2026-05-29
---

# Gamma

Partitura principale. File: [yaml/Gamma.yaml](../../yaml/Gamma.yaml), 351 righe.

## Sezioni

1. **I. Nascita Lenta di Cluster** — durata 140s, ratio_temporale 0.8. Layer: "salita di gamma" (lifespan pieno, accelerando 2.0), "scintillii" (lifespan [.8, 1], stocastico).
2. _(TODO)_
3. **III. Dalle nubi allo sciame** — durata 60s, offset -15. Layer: "Nubi Sparse verso sciame" (accelerando 2.0, densità cluster 4→20), "sciame" (stocastico, ottave alte, coda).
4. **IV. Rottura** — durata 80s, offset -60. Layer: "impulso" (accelerando, 13 att., full range ottava, ppp→ff), "impulso grave" (lifespan [.7,1], 4 att., ottava [0,1], basso registro).
5. **V. Cluster** — durata 50s. Layer: "cluster" (1 attivazione, densità_cluster 200-250, inviluppo mega-impulsivo).
6. **VI. Ultra glissando** — durata 110s, offset -30. Layer: "ultra glissando" (lifespan [0,.75]).

## Layer notevoli

- **salita di gamma** — accelerando, ottava sale da [0,2] a [3,8] con interp_shape 2.0, densità cluster cresce 2→7.
- **scintillii** — coda sezione I, dinamica `ppp`, ottave alte.
- **Nubi Sparse verso sciame** — accelerando, densità cluster 4→20, onset_jitter cresce: transizione da nube a sciame.
- **sciame** — stocastico, ottava [6,7]→[8,9], piccoli ritmi in coda sezione III.
- **impulso** — IV.1, 13 att., full ottava [0,8], ppp→ff in accelerando.
- **impulso grave** — IV.2, entra a 70%, ottava [0,1], 4 att., cluster piccoli.
- **cluster** — V, singola attivazione massiva, densità 200-250, mega-impulsivo.

## Parametri usati

_(popolare cross-link)_ [[parametri/ottava]] [[parametri/registro]] [[parametri/durata_armonica]] [[parametri/densita_cluster]] [[parametri/dinamica]] [[parametri/timing_model]] [[parametri/nonlinear_mode]]

## Render

```bash
make YAML=Gamma
```

Output: `composizioni_generate/wav/Gamma.wav`, plot `composizioni_generate/Gamma_partitura.pdf`.
