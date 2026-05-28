---
type: composizione
sources: [yaml/Gamma.yaml]
updated: 2026-05-28
---

# Gamma

Partitura principale. File: [yaml/Gamma.yaml](../../yaml/Gamma.yaml), 351 righe.

## Sezioni

_(da approfondire via ingest mirato — placeholder)_

1. **I. Nascita Lenta di Cluster** — durata 140s, ratio_temporale 0.8. Layer: "salita di gamma" (lifespan pieno, accelerando 2.0), "scintillii" (lifespan [.8, 1], stocastico).
2. _(TODO)_
3. _(TODO)_
4. _(TODO)_

## Layer notevoli

- **salita di gamma** — accelerando, ottava sale da [0,2] a [3,8] con interp_shape 2.0, densità cluster cresce 2→7.
- **scintillii** — coda sezione, dinamica `ppp`, ottave alte.

## Parametri usati

_(popolare cross-link)_ [[parametri/ottava]] [[parametri/registro]] [[parametri/durata_armonica]] [[parametri/densita_cluster]] [[parametri/dinamica]] [[parametri/timing_model]] [[parametri/nonlinear_mode]]

## Render

```bash
make YAML=Gamma
```

Output: `composizioni_generate/wav/Gamma.wav`, plot `composizioni_generate/Gamma_partitura.pdf`.
