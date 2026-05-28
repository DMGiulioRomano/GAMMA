; ====================================================================
; pfield_comp.udo
; UDO per il calcolo della frequenza di un evento a partire da
; (ottava, registro, ritmo). Mappa contro la tabella gi_Intonazione
; riempita da GenPythagFreqs.
; ====================================================================

opcode calcFrequenza, i, iii
    i_Ottava, i_Registro, i_RitmoCorrente xin

    ; Indice base nella tabella per l'ottava richiesta
    i_Indice_Ottava = int(i_Ottava * $INTERVALLI)
    ; Offset all'interno dell'ottava in funzione del registro
    i_OffsetIntervallo = i_Indice_Ottava + int(((i_Registro * $INTERVALLI) / $REGISTRI))

    ; Il ritmo corrente sposta la lettura → modula il pitch
    i_Freq table max(1, i_OffsetIntervallo + i_RitmoCorrente), gi_Intonazione
    ifreq = min(i_Freq, sr/2 - 1)
    xout ifreq
endop
