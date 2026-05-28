# Log Wiki

Append-only. Prefisso: `## [YYYY-MM-DD] <op> | <target>`.

## [2026-05-28] ingest | bootstrap

Scaffold iniziale wiki: index, pipeline, concepts/maschera_tendenza, composizioni/Gamma.
Sorgenti immutabili identificate: `yaml/*`, `generative_composerYaml2.py`, `includes/*`, `Makefile`.

## [2026-05-28] ingest | includes/*

Ingest completo di 13 file in `includes/`:

- Strumenti `.orc`: eventoSonoro (current), eventoSonoroOld (legacy), voce, comportamento, avvia_comportamento, waveshaper, inviluppoSezione, initIsoAmp, debug (vuoto).
- UDO `.udo`: GenPythagFreqs, NonlinearFunc, gamma_utils, pfield_comp.

Note emerse:
- `eventoSonoro` corrente differisce da `eventoSonoroOld` per: ampiezza isofonica (`GetIsoAmp_k`), glissando esponenziale, inviluppo di sezione per-evento, senso parametrico, dcblock.
- `voce` vs `comportamento`: stesso pattern di loop, differiscono per modello dinamico (isofonico vs sinusoide smorzata) e supporto glissando.
- `avvia_comportamento` impone convenzione `tab_posizioni = tab_ritmi + 1` — vincolo che il Python deve rispettare.
- `initIsoAmp` e' il pannello di controllo dinamico centralizzato (4 costanti `giPhonFFF/Step`, `giDbfsFFF/Step`).
- `pfield_comp.calcFrequenza` mappa `(ottava, registro, ritmo)` → freq via `gi_Intonazione` ([[GenPythagFreqs]]) — il **ritmo modula la frequenza**.
- `debug.orc` vuoto: VERIFICATO dead code, nessun include in tutto il repo.
- `inviluppoSezione` pubblica `gk_SectionEnv` globale, ma l'inviluppo di sezione effettivo gira per-evento dentro `eventoSonoro` — possibile duplicazione.

Index aggiornato (sezione "Includes Csound" popolata, 13 voci).

## [2026-05-28] lint | includes vs CSD generato

Verifica `#include` reali nel CSD generato (`generative_composerYaml2.py:L908-L914`). Solo 7 file su 13 sono effettivamente caricati:

INCLUSI: `gamma_utils.udo`, `pfield_comp.udo`, `NonlinearFunc.udo`, `GenPythagFreqs.udo`, `initIsoAmp.orc`, `eventoSonoro.orc`, `voce.orc`.

DEAD (presenti ma mai inclusi): `debug.orc`, `eventoSonoroOld.orc`, `comportamento.orc`, `avvia_comportamento.orc`, `waveshaper.orc`, `inviluppoSezione.orc`.

Implicazioni:
- Lo strumento `Comportamento` e relativo wrapper `AvviaComportamento` non sono usati dalla pipeline corrente — il modello attivo e' solo `Voce` → `eventoSonoro`.
- `WaveShaper` non e' raggiungibile.
- `InviluppoSezione` non viene mai schedulato → `gk_SectionEnv` resta unset, l'inviluppo di sezione gira solo per-evento dentro `eventoSonoro`.
- Le pagine wiki dei file dead vanno marcate con un avviso di stato.

## [2026-05-28] lint | drop dead includes

Eliminato il codice non utilizzato dalla pipeline corrente (Voce → eventoSonoro):

File rimossi da `includes/`:
- `debug.orc` (vuoto)
- `eventoSonoroOld.orc` (legacy)
- `comportamento.orc` (sostituito da Voce)
- `avvia_comportamento.orc` (wrapper di Comportamento)
- `waveshaper.orc` (mai schedulato)
- `inviluppoSezione.orc` (mai schedulato, section env gira per-evento dentro eventoSonoro)
- `gamma_utils.udo` (catena di chiamanti tutta dead)

`pfield_comp.udo` riscritto: solo `calcFrequenza` (gli altri opcode — validatori, `calcAmpiezza`, `calculateMaxAmplitude` — erano chiamati esclusivamente dal vecchio `Comportamento`).

Python aggiornato ([generative_composerYaml2.py](../generative_composerYaml2.py)): rimosso `#include "gamma_utils.udo"` dal template CSD.

Wiki pages corrispondenti eliminate; index ridotto a 7 voci. Voce wiki page aggiornata: riferimenti a Comportamento rimossi, indicato come unico generatore di eventi di layer.

Stato finale `includes/` (7 file, tutti effettivamente caricati dal CSD generato):
- ORC: `eventoSonoro.orc`, `voce.orc`, `initIsoAmp.orc`
- UDO: `GenPythagFreqs.udo`, `NonlinearFunc.udo`, `pfield_comp.udo`
