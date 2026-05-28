; ===================================================================
; inviluppoSezione.orc
; Strumento per generare un inviluppo di ampiezza globale per una sezione.
; ===================================================================
instr InviluppoSezione
    ; p4: numero della tabella (f-table) che contiene la forma dell'inviluppo
    i_ifn_shape = p4

    ; Genera un indice di lettura che va da 0 a 1 per tutta la durata dello strumento (p3)
    k_index line 0, p3, 1
    
    ; Legge il valore dalla tabella e lo scrive nella variabile globale
    gk_SectionEnv table k_index, i_ifn_shape, 1
endin
