---
name: voce
description: Strumento Voce — unico generatore di eventi di un layer attualmente schedulato dal sistema. Dinamica isofonica, glissando ottava/registro, inviluppo di sezione, safety buffer di fine.
sources: [includes/voce.orc]
updated: 2026-05-28
---

# Voce

`instr Voce`. **Unico generatore di eventi di layer** schedulato dal Python ([generative_composerYaml2.py:845](../../generative_composerYaml2.py#L845)). Gestisce **glissando** (`ottava_arrivo`, `registro_arrivo`), **dynamics index** (isofonico via [[initIsoAmp]]), **inviluppo di sezione per-evento** e **safety buffer** opzionale per tagliare eventi che eccedono il fine sezione.

## p-fields

| Pos | Nome | Significato |
|---|---|---|
| p2 | `i_CAttacco` | attacco assoluto del layer |
| p3 | `i_Durata` | durata layer |
| p4 | `i_RitmiTab` | f-table ritmi iniziali |
| p5 | `i_DurataArmonica` | durata armonica di riferimento |
| p6 | `i_DynamicIndex` | indice dinamica (0..6) — vedi [[initIsoAmp]] |
| p7-p8 | `i_Ottava`, `i_Registro` | partenza |
| p9-p10 | `i_ottava_arrivo`, `i_registro_arrivo` | arrivo glissando |
| p11 | `i_PosTab` | tabella posizioni |
| p12 | `i_IdComp` | id layer |
| p13 | `i_NonlinearMode` | default 3 ([[NonlinearFunc]]) |
| p14 | `i_SensoMovimento` | direzione spaziale, default 1 (antiorario) |
| p15 | `i_ifnAttacco` | inviluppo locale (default 10) |
| p16 | `i_ifn_section_env` | inviluppo di sezione (0 = disattivato) |
| p17 | `i_section_start_time` | t inizio sezione |
| p18 | `i_section_duration` | durata sezione |
| p19 | `i_duration_leeway` | jitter di taglio finale |
| p20 | `iSafetyBuffer` | 1 = taglia eventi che sforano, 0 = lascia passare |

## Loop di generazione

1. Legge ritmo dalla tabella; se esaurito → genera con `NonlinearFunc`.
2. Tempo di attacco evento `= attacco_precedente + i_DurataArmonica / ritmo_vecchio`.
3. Calcola `i_Freq1`/`i_Freq2` con [[pfield_comp]] `calcFrequenza` (partenza e arrivo).
4. **Ampiezza isofonica** via `GetIsoAmp(i_Freq1, i_DynamicIndex)` ([[initIsoAmp]]).
5. Posizione spaziale presa da `i_PosTab` o random in `[0, ritmo)`.
6. Durata evento `= (i_DurataArmonica / ritmo) * OverlapFactor` con `OverlapFactor in [1,3]`.
7. **Safety buffer**: se `iSafetyBuffer == 1` e l'evento supera `section_end`, viene tagliato a `section_end - attacco + jitter(0, leeway)`.
8. `schedule "eventoSonoro" ...` con tutti i parametri del glissando + envelope di sezione.

## Memorizzazione

Tabella globale `gi_eve_attacco[gi_Index]` registra l'attacco — usata per calcolare il successivo `EventAttack`.

## Consumatori

Schedulata dal CSD generato dal Python per ogni evento di ogni layer ([generative_composerYaml2.py:845](../../generative_composerYaml2.py#L845)). Branch `if event['type'] == 'voce':` e' l'unico ramo che produce score lines.
