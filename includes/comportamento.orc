; ===========================================================================
; comportamento.orc (Versione pulita e modificata per il generatore di gamma)
; Generatore di eventi sonori.
; ===========================================================================
instr Comportamento
    ; -----------------------------------------------------------------------
    ; 1. INIZIALIZZAZIONE E ACQUISIZIONE PARAMETRI
    ; -----------------------------------------------------------------------
    i_CAttacco       = p2             ; Tempo di attacco del comportamento
    i_Durata         = p3             ; Durata complessiva
    i_RitmiTab       = p4             ; Tabella dei ritmi
    i_DurataArmonica = p5             ; Durata armonica di riferimento
    i_Ampiezza       = p6             ; Ampiezza in dB
    i_Ottava         = p7             ; Ottava
    i_Registro       = p8             ; Registro
    i_PosTab         = p9             ; Tabella delle posizioni
    i_IdComp         = p10            ; ID del comportamento
    ; Nuovo parametro per la modalità di NonlinearFunc. Default a 3 (caos vero) se non fornito.
    i_NonlinearMode  = (p11 == 0 ? 3 : p11)
    i_SectionStartTime  = p12
    i_SectionDuration   = p13
    i_SectionJitter   = p14 ; Jitter di fine sezione
    i_SectionEndTime_Ideal = i_SectionStartTime + i_SectionDuration
    i_debug = gi_debug
    ; Applica il jitter per ottenere il tempo di fine "reale"
    ; randomh genera un valore casuale tra -i_SectionJitter e +i_SectionJitter
    i_JitterAmount = random:i(0, i_SectionJitter*2)- i_SectionJitter
    i_AbsoluteEndTime = i_SectionEndTime_Ideal + i_JitterAmount
    ; -----------------------------------------------------------------------
    ; 2. PREPARAZIONE DELLE SEQUENZE
    ; -----------------------------------------------------------------------
    i_LenRitmiTab = ftlen(i_RitmiTab)
    i_TempRitmiTab ftgen 0, 0, i_LenRitmiTab + 10000, -2, 0 ; Tabella estendibile per nuovi ritmi
    
    ; Copia i ritmi iniziali nella tabella temporanea
    i_IndexCopy = 0
    while i_IndexCopy < i_LenRitmiTab do
        i_ValRitmo tab_i i_IndexCopy, i_RitmiTab
        tabw_i i_ValRitmo, i_IndexCopy, i_TempRitmiTab
        i_IndexCopy += 1
    od

    ; -----------------------------------------------------------------------
    ; 3. GENERAZIONE DEGLI EVENTI SONORI
    ; -----------------------------------------------------------------------
    i_EventIdx = 0
    i_whileTime = 0

    while i_whileTime < i_Durata do
        ; -------- 3.1 GESTIONE RITMI --------
        if i_EventIdx < i_LenRitmiTab then
            i_RitmoCorrente tab_i i_EventIdx, i_TempRitmiTab
            if i_RitmoCorrente == 0 then
                goto generateNewRhythm
            endif
            i_Vecchio_Ritmo = (i_EventIdx == 0) ? 1 : tab_i(i_EventIdx - 1, i_TempRitmiTab)
        else
            generateNewRhythm:
           i_Vecchio_Ritmo tab_i i_EventIdx - 1, i_TempRitmiTab
           ; **MODIFICA CHIAVE**: Passa la modalità alla NonlinearFunc
           i_RitmoCorrente NonlinearFunc i_Vecchio_Ritmo, i_NonlinearMode
           tabw_i i_RitmoCorrente, i_EventIdx, i_TempRitmiTab
        endif

        ; -------- 3.2 CALCOLO TEMPO DI ATTACCO --------
        if i_EventIdx == 0 then
            i_EventAttack = i_CAttacco
        else
            i_RitmoNormalizzato = 1 / i_Vecchio_Ritmo
            i_PreviousAttack tab_i gi_Index - 1, gi_eve_attacco
            i_EventAttack = i_DurataArmonica * i_RitmoNormalizzato + i_PreviousAttack
        endif

        ; -------- 3.3 CALCOLO PARAMETRI DELL'EVENTO --------
        if i_RitmoCorrente >=1 then 
        i_Amp = calcAmpiezza(i_Ampiezza, i_RitmoCorrente, -0.05)
        else 
        i_Amp = calcAmpiezza(i_Ampiezza, 1, -0.05)
        endif
        i_Freq1 = calcFrequenza(i_Ottava, i_Registro, i_RitmoCorrente, gi_Intonazione, $INTERVALLI, $REGISTRI)
        i_Freq2 = i_Freq1

        ;if i_EventIdx < ftlen(i_PosTab) then
        ;    i_Pos tab_i i_EventIdx, i_PosTab
        ;else
            i_Pos = int(random:i(0, i_RitmoCorrente))
        ;endif

        ; -------- 3.4 CALCOLO DURATA ADATTATIVA --------
        i_GlobalTime = i_whileTime + i_CAttacco
        i_LookbackTime = max(0, i_GlobalTime - 5)

        i_OverlapFactor random 1, 3
        
        i_EventDuration = (i_DurataArmonica / i_RitmoCorrente) * i_OverlapFactor
        if i_debug >= 2 then
            prints "durata armonica comp: %f\tdurata comp:%f\n", i_DurataArmonica, i_Durata
            prints "compAt: %f section end: %f event attck: %f durEvento: %f teorical dur evento: %f evento fine: %d evento: %d\n", p2, i_AbsoluteEndTime, i_EventAttack,i_EventDuration, (i_DurataArmonica / i_RitmoCorrente),i_EventAttack+i_EventDuration, gi_Index
        endif
        if i_AbsoluteEndTime < i_EventAttack+i_EventDuration then 
            i_EventDuration = i_AbsoluteEndTime - i_EventAttack
            if i_debug >= 2 then
                prints "new duration: %f\n", i_EventDuration
            endif
        endif

        tabw_i i_EventAttack, gi_Index, gi_eve_attacco
        ; ... le altre scritture su tabella `gi_eve_*` non sono necessarie per la sola generazione audio,
        ; -------- 3.6 SCHEDULING DELL'EVENTO SONORO --------
        schedule "eventoSonoro", i_EventAttack - p2, i_EventDuration, i_Amp, i_Freq1, i_Pos, i_RitmoCorrente, i_Freq2, 2, gi_Index,i_IdComp

        ; -------- 3.7 AGGIORNAMENTO INDICI E TEMPO --------
        i_EventIdx += 1
        gi_Index += 1
        i_whileTime += (i_DurataArmonica / i_RitmoCorrente)
        if i_debug >= 2 then
            prints "whiletime: %f\n", i_whileTime
        endif
    od
    ftfree i_TempRitmiTab, 0
endin
