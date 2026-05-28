---
type: pipeline
sources: [Makefile, generative_composerYaml2.py]
updated: 2026-05-28
---

# Pipeline GAMMA

```
yaml/<nome>.yaml
  → python3.11 generative_composerYaml2.py yaml/<nome>.yaml
    → composizioni_generate/csd/*.csd   (uno per layer)
      → csound (subprocess per ogni csd)
        → composizioni_generate/wav/<layer>.wav
          → csd assembler per sezione → wav/<sezione>.wav
            → csd assembler finale → wav/<nome>.wav
```

## Step

1. **Parse YAML** — [`load_all_compositions_from_yaml`](../generative_composerYaml2.py#L43). Multi-documento separato da `---`.
2. **Risoluzione maschere** — [`GenerativeComposer`](../generative_composerYaml2.py#L133) campiona stato iniziale/finale per ogni layer, interpola nel tempo.
3. **Timing eventi** — [`TimeScheduler`](../generative_composerYaml2.py#L77). Modelli: `lineare`, `accelerando`, `stochastic`.
4. **Genera CSD per layer** — emette score Csound con score events, include `includes/*.orc`+`*.udo`.
5. **Plan render jobs** — [`plan_render_jobs`](../generative_composerYaml2.py#L1477).
6. **Render layer** — [`execute_layer_rendering_and_collect_data`](../generative_composerYaml2.py#L1581) → subprocess `csound`.
7. **Assembly sezione** — [`execute_section_assembly`](../generative_composerYaml2.py#L1779). Genera CSD assembler che fa mix con onset.
8. **Assembly finale** — [`execute_final_assembly`](../generative_composerYaml2.py#L1802).
9. **Plot** — [`CompositionDebugger`](../generative_composerYaml2.py#L955) emette `composizioni_generate/<nome>_partitura.pdf`.

## Comandi

```bash
make                 # YAML=Gamma default
make YAML=Beta2
make clean
```

## Output

- `composizioni_generate/csd/` — CSD generati
- `composizioni_generate/wav/` — render parziali e finale
- `composizioni_generate/logs/` — log csound per debug
- `composizioni_generate/<nome>_partitura.pdf` — plot evoluzione parametri

## Collegamenti

- [[concepts/maschera_tendenza]]
- [[composizioni/Gamma]]
