; ====================================================================
; eventoSonoro.orc (Versione pulita per il generatore di gamma)
; Strumento di sintesi spazializzata.
; ====================================================================

#define DEBUG_Evento_print_Pfields #
   if (int(i_debug) >=2) then
      Snamefile sprintf "%sComp%d.sco", gSdirSco, id_comportamento
      if i_debug >=3 then
         prints "\n\t\t\tevento sonoro %d del comportamento %d",id_evento, id_comportamento
         prints "\n\t\t\t\tattacco: %.3f\n\t\t\t\tdurata: %.3f\n\t\t\t\tamp: %f\n\t\t\t\tfreq1: %.3f\n\t\t\t\twz: %.3f\n\t\t\t\tdir: %.3f\n\t\t\t\tHR: %.3f\n\t\t\t\tfreq2: %.3f\n\t\t\t\tifn: %.3f\n\t\t\t\tid_evento: %.3f\n\n", p2, p3, p4, p5, p6, signum(p6),p7, p8, p9, p10    
      endif
      if (id_evento%100==0) then
      ;fprints Snamefile,"\n\t;\t\t\t\t\t\tattacco:\tdurata:\t\tamp:\t\tfreq1:\t\t\twz:\t\t\tdir:\t\tHR:\t\t\t\tfreq2:\t\tifn:\t\tid_evento:"
      endif
      fprints Snamefile,"\n\n\t;\t\t\t\t\t\tattacco:\tdurata:\t\tamp:\t\tfreq1:\t\t\t\twz:\t\tHR:\t\tfreq2:\t\t\tifn:\tid_evento:\t\tid_comportamento:\t\ti_senso:\t\ti_ifn_section_env:\t\ti_section_start_time:\t\ti_section_duration:"
      fprints Snamefile,"\n\ti \"eventoSonoro\"\t\t%.3f\t\t%.3f\t\t%.3f\t\t%f\t\t\t%d\t\t%d\t\t%f\t\t%d\t\t%d\t\t\t\t%d\t\t\t\t\t\t%d\t\t\t\t%d\t\t\t\t\t\t%f\t\t\t\t%f", p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14, p15  
      SentireSco sprintf "%sAll.sco", gSdirSco
      fprints SentireSco,"\n\n\t; [comp %d]\t\t\t\tattacco:\tdurata:\t\tamp:\t\tfreq1:\t\t\twz:\t\tHR:\t\tfreq2:\t\t\tifn:\tid_evento:\t\ti_senso:\t\ti_ifn_section_env:\t\ti_section_start_time:\t\ti_section_duration:", p11
      fprints SentireSco,"\n\ti \"eventoSonoro\"\t\t%.3f\t\t%.3f\t\t%f\t\t%f\t\t%d\t\t%d\t\t%f\t\t%d\t\t\t%d\t\t%d\t\t\t\t%d\t\t\t\t\t\t%f\t\t\t\t%f", p2, p3, p4, p5, p6, p7, p8, p9, p10, p12, p13, p14, p15
   endif#

instr eventoSonoro
   ;--------------------------------------------------------------
   ; Parameter Initialization
   ;--------------------------------------------------------------
   i_DynamicIndex = p4
   i_debug=gi_debug
   ifreq1 = limit(p5, 20, sr/2)   
   iwhichZero = abs(p6)    
   iHR = max(1, abs(p7))

   iPeriod = $M_PI * 2 / iHR
   
   iradi = (iwhichZero > 0 ? (iwhichZero - 1) * iPeriod : 0)
   ifreq2 = limit(p8, 20, sr/2)

   ifn_shape = (p9 == 0 ? 2 : p9) 
   id_evento=p10
   id_comportamento=p11
   i_senso = (p12 == 0 ? 1 : p12) 
   i_ifn_section_env = p13
   i_section_start_time = p14
   i_section_duration = p15


   $DEBUG_Evento_print_Pfields
   if p7 == 0 then
      prints "ERROR p7==0\n"
      prints "evento: %d , comp: %d", id_evento, id_comportamento
      exitnow
   endif
   
   ;--------------------------------------------------------------
   ; Position and Envelope Generation
   ;--------------------------------------------------------------
   kndx_local line 0, p3, 1
   ktab tab kndx_local, ifn_shape, 1
   krad = iradi + (ktab * iPeriod * i_senso)

   if ifn_shape == 2 then
      kEnv_local = abs(sin(krad * iHR / 2))
   else
      kEnv_local tab kndx_local, ifn_shape, 1
   endif


   kEnv_section = 1 ; Valore di default neutro
   if i_ifn_section_env > 20 && i_section_duration > 0 then
      k_time_absolute times      
      ; Calcola da quanto tempo è iniziata la sezione
      k_time_since_section_start = k_time_absolute - i_section_start_time
      ; Normalizza questo tempo rispetto alla durata totale della sezione
      kndx_section = limit(k_time_since_section_start / i_section_duration,0,1)
      ;kEnv_section=1 
      kEnv_section tablei kndx_section, i_ifn_section_env,1
   endif
   ;--------------------------------------------------------------
   ; Sound Generation and Spatialization
   ;--------------------------------------------------------------
   if ifreq1 > ifreq2 then
      kf expseg  1, p3, 0.0001
      kfreq = (kf * (ifreq1-ifreq2))+ifreq2
   elseif ifreq1 < ifreq2 then
      kf expseg  0.0001, p3, 1
      kfreq = (kf * (ifreq2-ifreq1))+ifreq1
   else
      kfreq = ifreq1
   endif

   kamp GetIsoAmp_k i_DynamicIndex, ifreq1, ifreq2

   asig poscil3 kamp, kfreq
   asigLocalEnv = asig * kEnv_local
   asigEnvPre = asigLocalEnv * kEnv_section

   asigEnv dcblock asigEnvPre
   kMid = cos(krad)
   kSide = sin(krad)
   
   aMid = kMid * asigEnv 
   aSide = kSide * asigEnv
   
   ;--------------------------------------------------------------
   ; Output Stage
   ;--------------------------------------------------------------
   aL = (aMid + aSide) / $SQRT2
   aR = (aMid - aSide) / $SQRT2
   
   outs aL, aR
endin
