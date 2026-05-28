; ===========================================================================
; waveshaper.orc - Strumento di sintesi per Waveshaping (Distorsione Non Lineare)
; ===========================================================================
;
; p-fields:
; p1: instr
; p2: tempo di attacco
; p3: durata
; p4: ampiezza (in dBFS, es. -6)
; p5: frequenza fondamentale (Hz)
; p6: numero della f-table della funzione di shaping
; p7: indice di shaping iniziale (controlla la quantità di distorsione)
; p8: indice di shaping finale
; p9: pan (0=sinistra, 0.5=centro, 1=destra)

instr WaveShaper
    ; -----------------------------------------------------------------------
    ; 1. INIZIALIZZAZIONE PARAMETRI
    ; -----------------------------------------------------------------------
    iAmp        = ampdbfs(p4)     ; Converte l'ampiezza da dB a lineare
    ifreq       = p5              ; Frequenza della sinusoide di base
    ifn_shape   = p6              ; La tabella che deforma l'onda
    iIndexStart = p7              ; Quantità di distorsione all'inizio
    iIndexEnd   = p8              ; Quantità di distorsione alla fine
    iPan        = (p9 == 0 ? 0.5 : p9) ; Default a centro se p9 è 0

    ; -----------------------------------------------------------------------
    ; 2. GENERAZIONE DEGLI INVILUPPI
    ; -----------------------------------------------------------------------
    ; Inviluppo di ampiezza generale (ADSR-like)
    kAmpEnv linseg 0, 0.05, 1, p3 - 0.1, 1, 0.05, 0

    ; Inviluppo dell'INDICE di shaping. Questo è il controllo più importante
    ; per l'evoluzione del timbro. Passa da iIndexStart a iIndexEnd.
    kIndexEnv line iIndexStart, p3, iIndexEnd

    ; -----------------------------------------------------------------------
    ; 3. MOTORE DI SINTESI (IL CUORE DEL WAVESHAPING)
    ; -----------------------------------------------------------------------
    ; 3a. Genera il segnale di ingresso: una semplice sinusoide.
    ; La sua ampiezza è 1 perché verrà scalata dall'indice di shaping.
    ; L'f-table 1 è la sinusoide standard.
    aInput oscil 1, ifreq, 1

    ; 3b. Applica la distorsione (waveshaping).
    ; L'ampiezza del segnale di ingresso (aInput * kIndexEnv) viene usata
    ; come INDICE per leggere i valori dalla tabella di shaping (ifn_shape).
    ; Se kIndexEnv è piccolo, leggiamo solo il centro della tabella.
    ; Se è grande, leggiamo tutta la tabella, introducendo la distorsione.
    aShaped tablei aInput * kIndexEnv, ifn_shape, 1, 0.5, 1
    ; L'opcode 'tablei' con interpolazione lineare è ottimo qui.
    ; -----------------------------------------------------------------------
    ; 4. STADIO DI USCITA
    ; -----------------------------------------------------------------------
    ; Applica l'inviluppo di ampiezza finale
    aOut = aShaped * kAmpEnv * iAmp

    ; Panning
    aL, aR pan2 aOut, iPan

    outs aL, aR
endin