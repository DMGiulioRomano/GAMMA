---
type: concept
sources: [yaml/guida.yaml, generative_composerYaml2.py:L133]
updated: 2026-05-28
---

# Maschera di tendenza

Filosofia del sistema: non valori fissi, ma **spazi di possibilità**. Ogni parametro definisce un range/distribuzione da cui il sistema campiona stocasticamente a ogni evento.

## Forma base

```yaml
parametro: { range: [min, max], distribution: "uniform" }
parametro: { choices: [a, b, c], weights: [0.5, 0.3, 0.2] }
parametro: { explicit_values: [1, 2, 4, 3, 2] }
parametro: "valore_fisso"
```

## Interpolazione temporale

Un [[layer]] ha `stato_iniziale` e `stato_finale`. La maschera evolve linearmente (o con `interp_shape`) nel `lifespan` del layer.

```yaml
stato_iniziale:
    ottava: { range: [0, 2] }
stato_finale:
    ottava: { range: [3, 8], interp_shape: 2.0 }
```

A metà lifespan, il range di `ottava` è interpolato.

## Collegamenti

- [[layer]]
- [[sezione]]
- [[timing_model]]
- Sintassi canonica: [yaml/guida.yaml](../../yaml/guida.yaml)
