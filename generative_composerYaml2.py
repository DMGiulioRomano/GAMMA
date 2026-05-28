#!/usr/bin/env python3
"""
Generative Composer (v1.0)
===============================================
"""

import numpy as np
import random
import sys
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import seaborn as sns
import yaml
import subprocess 
import re
import json

OTTAVE_RANGE = (0, 10)
REGISTRI_RANGE = (1, 50)
INTERVALLI_PER_OTTAVA = 200 

def load_yaml_file(file_path):
    """
    Carica un file YAML generico e gestisce gli errori comuni.
    """
    print(f"Caricamento file di configurazione: {file_path}")
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            print(f"ERRORE: Il file YAML '{file_path}' deve contenere un dizionario (mappatura).")
            sys.exit(1)
        print(f"✓ File '{Path(file_path).name}' caricato con successo.")
        return data
    except FileNotFoundError:
        print(f"ERRORE CRITICO: File di configurazione non trovato: '{file_path}'")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERRORE CRITICO: Errore nella sintassi del file YAML '{file_path}': {e}")
        sys.exit(1)

def load_all_compositions_from_yaml(file_path):
    """
    Carica una o più composizioni da un singolo file YAML.
    I documenti multipli devono essere separati da '---'.
    Restituisce una lista di strutture di composizione.
    """
    print(f"Caricamento partiture dal file multi-documento: {file_path}")
    composizioni = []
    try:
        with open(file_path, 'r') as f:
            # safe_load_all restituisce un generatore, lo convertiamo in lista
            docs = list(yaml.safe_load_all(f))
        
        if not docs or all(d is None for d in docs):
             print(f"ERRORE: Il file YAML '{file_path}' è vuoto o non contiene documenti validi.")
             sys.exit(1)

        for i, composition in enumerate(docs):
            if composition is None: continue # Salta documenti vuoti (es. solo '---')
            
            if not isinstance(composition, list):
                print(f"ERRORE nel documento #{i+1} del file YAML: deve contenere una lista di sezioni.")
                sys.exit(1)
            composizioni.append(composition)

        print(f"✓ Trovati e caricati {len(composizioni)} documenti di composizione.")
        return composizioni
    except FileNotFoundError:
        print(f"ERRORE CRITICO: File della partitura non trovato: '{file_path}'")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERRORE CRITICO: Errore nella sintassi del file YAML: {e}")
        sys.exit(1)

class TimeScheduler:
    """Genera sequenze temporali (onsets) basate su diversi modelli."""
    def generate_onsets(self, model, duration, num_events):
        if num_events == 0: return []
        if num_events == 1: return [0.0]

        base_progress = np.linspace(0, 1, num_events, endpoint=False) # Endpoint False per evitare un evento a durata esatta
        final_progress = np.zeros_like(base_progress)
        model_type = model.get('type', 'linear')

        if model_type == 'ritardando':
            shape = model.get('shape', 2.0)
            final_progress = base_progress ** shape
        elif model_type == 'accelerando':
            shape = model.get('shape', 2.0) # La forma > 1.0 rallenta se invertita
            final_progress = 1 - (1 - base_progress) ** shape
        elif model_type == 'breakpoint':
            points = model['points']
            
            # Itera su ogni segmento della spezzata (da punto i a punto i+1)
            for i in range(len(points) - 1):
                start_point = points[i]
                end_point = points[i+1]
                # Estrai i dati del segmento
                t_start, v_start = start_point[0], start_point[1]
                t_end, v_end = end_point[0], end_point[1]
                # La forma è definita dal punto di arrivo. Default a lineare (1.0).
                shape = end_point[2] if len(end_point) > 2 else 1.0
                # Trova quali eventi cadono in questo intervallo di tempo
                segment_mask = (base_progress >= t_start) & (base_progress < t_end)
                if not np.any(segment_mask):
                    continue
                
                # Seleziona solo i punti di tempo in questo segmento
                segment_times = base_progress[segment_mask]

                # --- CUORE DELLA LOGICA ---
                # 1. Normalizza il tempo all'interno del segmento (da 0 a 1)
                time_in_segment = (segment_times - t_start) / (t_end - t_start)
                # 2. Applica la funzione di shaping (curva)
                shaped_time = time_in_segment ** shape
                # 3. Interpola linearmente tra i VALORI usando il tempo curvato
                interpolated_values = v_start + (v_end - v_start) * shaped_time                
                # Assegna i valori calcolati all'array finale
                final_progress[segment_mask] = interpolated_values            
            # Gestisci l'ultimo punto esatto, se presente
            if base_progress[-1] == 1.0:
                final_progress[-1] = points[-1][1]

        elif model_type == 'stochastic':
            final_progress = np.sort(np.random.rand(num_events))
        else: # Default a lineare
            final_progress = base_progress
            
        return final_progress * duration

class GenerativeComposer:
    """Classe principale che orchestra la generazione della composizione."""

    def __init__(self, output_dir="composizioni_generate", tables_config_path="yaml/tables.yaml"):
        self.base_path = Path(__file__).parent.resolve() # <-- MODIFICA: usa resolve() per un percorso assoluto
        self.output_path = self.base_path / output_dir
        self.output_path.mkdir(exist_ok=True)
        self.wav_output_path = self.output_path / "wav"
        self.wav_output_path.mkdir(exist_ok=True)
        
        self.time_scheduler = TimeScheduler()
        
        # Mappa per le tabelle di Csound. Verrà popolata dinamicamente.
        self.rhythm_table_map = {}
        self.next_table_id = 1000

        # --- CARICAMENTO DELLE CONFIGURAZIONI DELLE TABELLE DAL FILE YAML ---
        full_tables_path = self.base_path / tables_config_path
        tables_config = load_yaml_file(full_tables_path)
        
        # 1. Salva l'intera struttura di configurazione in attributi dedicati.
        # Questi attributi verranno usati da `generate_csd`.
        self.event_envelopes_config = tables_config.get('event_envelopes', {})
        self.section_envelopes_config = tables_config.get('section_envelopes', {})

        # Controlla che le configurazioni siano state caricate correttamente
        if not self.event_envelopes_config or not self.section_envelopes_config:
            print(f"ATTENZIONE: 'event_envelopes' o 'section_envelopes' sono mancanti o vuoti in '{tables_config_path}'.")
            print("Questo potrebbe causare errori se vengono referenziati nella partitura.")

        # 2. Ora, da queste configurazioni complete, crea le mappe semplici nome->numero.
        # Queste mappe più semplici verranno usate internamente per la logica esistente.
        self.envelope_map = {name: config['number'] for name, config in self.event_envelopes_config.items() if 'number' in config}
        self.section_envelope_map = {name: config['number'] for name, config in self.section_envelopes_config.items() if 'number' in config}

        # 3. Imposta i valori di default
        self.default_envelope = 'lineare'
        self.default_section_envelope = 'continua'

        # Mappa per tradurre la dinamica in un indice per Csound
        self.dynamic_to_index = {
            'ppp': 0, 'pp': 1, 'p': 2, 'mf': 3, 'f': 4, 'ff': 5, 'fff': 6
        }
        self.id_comp_counter = 0
        
    def _valida_parametri(self, params):
        """
        Valida un set di parametri generati per assicurarsi che siano
        tecnicamente validi per il motore Csound.
        """
        # 2. Validazione Durata
        min_ritmo = min(r for r in params['ritmi'] if r > 0)
        if not min_ritmo: return False
        min_event_dur = params['durata_armonica'] / min_ritmo
        if params['durata_totale'] <= min_event_dur:
            return False
            
        return True

    def _normalize_mask(self, mask):
        """
        Converte i valori non-dizionario in una maschera nel formato {value: ...}.
        Esempio: 'dinamica: "p"' diventa 'dinamica: {"value": "p"}'.
        """
        if not mask:
            return {}
        normalized = {}
        for key, value in mask.items():
            if not isinstance(value, dict):
                normalized[key] = {'value': value}
            else:
                normalized[key] = value
        return normalized
    
    def _generate_rhythm_pattern(self, tipo_ritmi):
        """Genera una lista di ritmi basata su una categoria."""
        if tipo_ritmi == 'piccoli':
            return random.choice([[1, 2, 3], [2, 3, 5], [3, 4, 2]])
        elif tipo_ritmi == 'medi':
            return random.choice([[6, 8, 10], [7, 9, 12], [8, 12, 8]])
        elif tipo_ritmi == 'grandi':
            return random.choice([[16, 20, 24], [18, 25, 30], [20, 28, 20]])
        elif tipo_ritmi == 'misti':
            return random.choice([[2, 10, 4, 15], [3, 20, 5, 8]])
        return [4, 4, 4] # Default

    def _generate_params_from_mask(self, mask):
        """
        Il cuore del generatore. Versione semplificata e unificata.
        Tutti i parametri sono gestiti dalla stessa logica coerente.
        """
        params = {}

        # Definiamo un set di chiavi che sono gestite da logiche specializzate
        # più avanti in questa funzione o al di fuori di essa (es. densita_cluster).
        # Queste chiavi devono essere saltate dal ciclo di generazione generico.
        SKIPPED_KEYS = {
            'choices', 'weights', 'distribution', # Metadati
            'dynamic_index',      # Valore pre-calcolato dall'interpolazione
            'dinamica',           # Gestito da logica speciale
            'nonlinear_mode',     # Gestito da logica speciale
            'senso_movimento',    # Gestito da logica speciale
            'inviluppo_attacco',  # Gestito da logica speciale
            'tipo_ritmi',         # Gestito da logica speciale
            'densita_cluster'     
        }

        # Itera su ogni parametro definito nella maschera.
        for key, p_mask in mask.items():
            # Salta le chiavi di controllo che non sono parametri diretti.
            if key in SKIPPED_KEYS: 
                continue
            
            val = 0
            
            # --- PERCORSO 1: DISTRIBUZIONE NORMALE ---
            # Se la maschera contiene 'mean' e 'std', usa la generazione Gaussiana.
            if 'mean' in p_mask and 'std' in p_mask:
                mean = p_mask['mean']
                std = p_mask['std']
                val = np.random.normal(loc=mean, scale=std)

            # --- PERCORSO 2: DISTRIBUZIONE UNIFORME (da un range) ---
            elif 'range' in p_mask:
                min_val, max_val = p_mask['range']
                if isinstance(min_val, int) and isinstance(max_val, int):
                    val = random.randint(min_val, max_val)
                else:
                    val = random.uniform(min_val, max_val)
            
            # --- PERCORSO 3: SCELTA PESATA (da una lista) ---
            elif 'choices' in p_mask:
                val = random.choices(p_mask['choices'], weights=p_mask.get('weights'), k=1)[0]
            
            params[key] = val

        # --- nonlinear_mode ---
        # Cerchiamo la maschera per nonlinear_mode
        nonlinear_mask = mask.get('nonlinear_mode')
        if nonlinear_mask:
            # Se la maschera esiste, generiamo il valore da essa
            if 'value' in nonlinear_mask:
                params['nonlinear_mode'] = nonlinear_mask['value']
            elif 'choices' in nonlinear_mask:
                params['nonlinear_mode'] = random.choices(
                    nonlinear_mask['choices'], 
                    weights=nonlinear_mask.get('weights'), 
                    k=1
                )[0]
            else:
                # Fallback se la maschera è malformata
                params['nonlinear_mode'] = 3
        else:
            # Default se la chiave 'nonlinear_mode' è completamente assente
            params['nonlinear_mode'] = 3 # Modalità Caos "Vero" di default

        # --- senso_movimento ---
        mov_mask = mask.get('senso_movimento')
        if mov_mask:
            if 'value' in mov_mask:
                params['senso_movimento'] = mov_mask['value']
            elif 'choices' in mov_mask:
                params['senso_movimento'] = random.choices(
                    mov_mask['choices'], 
                    weights=mov_mask.get('weights'), 
                    k=1
                )[0]
            else:
                params['senso_movimento'] = 1 # Fallback se la maschera è malformata
        else:
            # Default se la chiave 'senso_movimento' è assente
            params['senso_movimento'] = 1

        # --- inviluppo_attacco ---
        env_mask = mask.get('inviluppo_attacco')
        chosen_envelope_name = self.default_envelope
        if env_mask:
            if 'value' in env_mask:
                chosen_envelope_name = env_mask['value']
            elif 'choices' in env_mask:
                chosen_envelope_name = random.choices(
                    env_mask['choices'],
                    weights=env_mask.get('weights'),
                    k=1
                )[0]
        # Traduci il nome dell'inviluppo nel suo numero di tabella Csound
        params['ifn_attacco'] = self.envelope_map.get(chosen_envelope_name, self.envelope_map[self.default_envelope])

        # --- dinamica ---
        # La logica è stata riscritta per essere più robusta e gestire tutti i casi.

        # Priorità 1: L'indice è già stato calcolato e fornito dalla funzione di interpolazione?
        # Se sì, lo usiamo direttamente. Questo è il caso dei layer dinamici.
        if 'dynamic_index' in mask:
            params['dynamic_index'] = mask['dynamic_index']
        else:
            # Priorità 2: L'indice non è pre-calcolato, quindi lo generiamo dalla maschera 'dinamica'.
            dynamic_mask = mask.get('dinamica')
            if dynamic_mask:
                # Caso A: La dinamica è definita come una scelta pesata.
                if 'choices' in dynamic_mask:
                    dynamic_str = random.choices(
                        dynamic_mask['choices'], 
                        weights=dynamic_mask.get('weights'), 
                        k=1
                    )[0]
                    params['dynamic_index'] = self.dynamic_to_index.get(dynamic_str, 3) # Default 'mf'
                
                # Caso B: La dinamica è un valore fisso (es. dinamica: 'f').
                # Questo è il caso che mancava e causava l'errore per i layer statici.
                elif 'value' in dynamic_mask:
                    dynamic_str = dynamic_mask['value']
                    params['dynamic_index'] = self.dynamic_to_index.get(dynamic_str, 3) # Default 'mf'
                    
                # Fallback: la maschera 'dinamica' esiste ma è malformata.
                else:
                    params['dynamic_index'] = 3 # 'mf'
                    
            # Priorità 3: La chiave 'dinamica' non è proprio presente nella maschera.
            else:
                params['dynamic_index'] = 3 # 'mf'

        # --- APPLICAZIONE DEI CLIPPING E GENERAZIONE DERIVATA (POST-GENERAZIONE) ---
        
        # Clipping per garantire che i valori rimangano nei limiti tecnici globali.
        params['ottava'] = int(round(np.clip(params.get('ottava', 5), OTTAVE_RANGE[0], OTTAVE_RANGE[1])))
        params['registro'] = int(params.get('registro', 5))

        # 2. Logica Gerarchica per calcolare la frequenza di ARRIVO

        # CASO 1: MODALITÀ OFFSET (ha la precedenza su tutto)
        # Controlliamo se la maschera originale conteneva le chiavi di offset.
        # Usiamo la maschera 'mask' perché il dizionario 'params' conterrà solo i valori generati.
        if 'offset_ottava' in mask or 'offset_registro' in mask:
            
            # Recupera i valori di offset generati dal dizionario 'params'.
            # Se un offset non è stato specificato nel YAML, il suo valore generato non esisterà in 'params'.
            # In tal caso, il default è 0.
            offset_ottava = params.get('offset_ottava', 0)
            offset_registro = params.get('offset_registro', 0)
            
            # Calcola i parametri di arrivo sommando gli offset a quelli di partenza.
            ottava_arrivo_calc = params['ottava'] + offset_ottava
            registro_arrivo_calc = params['registro'] + offset_registro
            
            # Salva i valori calcolati nel dizionario 'params'. Questi verranno clippati dopo.
            params['ottava_arrivo'] = ottava_arrivo_calc
            params['registro_arrivo'] = registro_arrivo_calc
            
        # CASO 2: MODALITÀ ASSOLUTA (usata solo se non ci sono offset)
        # Controlliamo se la maschera originale conteneva le chiavi di arrivo assolute.
        elif 'ottava_arrivo' in mask or 'registro_arrivo' in mask:
            
            # I valori sono già stati generati dal ciclo e sono in 'params'.
            # Dobbiamo solo assicurarci che ci siano dei default sensati se ne manca uno.
            # Se 'ottava_arrivo' è specificata ma 'registro_arrivo' no, quest'ultimo sarà uguale al registro di partenza.
            params['ottava_arrivo'] = params.get('ottava_arrivo', params['ottava'])
            params['registro_arrivo'] = params.get('registro_arrivo', params['registro'])

        # CASO 3: DEFAULT (nessun glissando)
        else:
            # Se non sono stati specificati né offset né parametri assoluti di arrivo,
            # la frequenza di arrivo è semplicemente uguale a quella di partenza.
            params['ottava_arrivo'] = params['ottava']
            params['registro_arrivo'] = params['registro']

        # 3. Clipping finale e conversione a intero per i parametri di ARRIVO
        #    Questo è un passaggio di sicurezza fondamentale che si applica a TUTTI i casi.
        params['ottava_arrivo'] = int(round(np.clip(params['ottava_arrivo'], OTTAVE_RANGE[0], OTTAVE_RANGE[1])))
        params['registro_arrivo'] = int(np.clip(params['registro_arrivo'], REGISTRI_RANGE[0], REGISTRI_RANGE[1]))



        # Generazione di parametri derivati
        rhythm_mask = mask.get('tipo_ritmi', {'choices': ['medi']}) # Default a categoria 'medi'
        if 'explicit_values' in rhythm_mask:
            # --- MODALITÀ 1: L'utente ha fornito una lista esplicita ---
            params['ritmi'] = rhythm_mask['explicit_values']

        elif 'choices' in rhythm_mask:
            # --- MODALITÀ 2: L'utente ha fornito una lista di scelte ---
            choice = random.choices(rhythm_mask['choices'], weights=rhythm_mask.get('weights'), k=1)[0]
            
            if isinstance(choice, list):
                # Sottocaso 2a: La scelta è già una lista di ritmi (es. [[2,3,5], [7,7]])
                params['ritmi'] = choice
            else:
                # Sottocaso 2b: La scelta è una categoria stringa (vecchio comportamento)
                params['ritmi'] = self._generate_rhythm_pattern(choice)
        else:
            # Fallback se la maschera 'tipo_ritmi' è malformata
            params['ritmi'] = self._generate_rhythm_pattern('medi')

        params['posizioni'] = [i % r for i, r in enumerate(params['ritmi']) if r > 0]
        
        moltiplicatore = params.get('moltiplicatore_durata', random.choice([1, 1.25, 1.6]))
        params['durata_totale'] = params['durata_armonica'] * moltiplicatore
        
        self.id_comp_counter += 1
        params['id_comp'] = self.id_comp_counter

        return params

    def _interpolate_mask(self, start_mask, end_mask, progress):
        """
        (Versione Completa e Robusta) Interpola tra due maschere per ottenere una maschera intermedia.
        Gestisce correttamente i parametri che esistono solo in una delle due maschere.
        """
        interp_mask = {}
        all_keys = set(start_mask.keys()) | set(end_mask.keys())

        for key in all_keys:
            s_mask = start_mask.get(key)
            e_mask = end_mask.get(key)

            # --- GESTIONE DEI PARAMETRI ASIMMETRICI (LA VERA CORREZIONE) ---
            if s_mask is None:
                s_mask = e_mask
            
            if e_mask is None:
                e_mask = s_mask

            shape = e_mask.get('interp_shape', 1.0)
            shaped_progress = progress ** shape
            
            interp_mask[key] = {}

            # --- INIZIO LOGICA DI INTERPOLAZIONE COMPLETA ---

            # Blocco 1: Gestione speciale per la dinamica lineare
            # NOTA: questa parte è stata re-integrata.
            if key == 'dinamica' and 'value' in s_mask and 'value' in e_mask:
                start_val_str = s_mask['value']
                end_val_str = e_mask['value']
                
                start_idx = self.dynamic_to_index.get(start_val_str) 
                end_idx = self.dynamic_to_index.get(end_val_str)

                if start_idx is not None and end_idx is not None:
                    interp_idx = start_idx + (end_idx - start_idx) * shaped_progress
                    interp_mask['dynamic_index'] = interp_idx
                    # Aggiungiamo anche la maschera originale per coerenza, sebbene non venga usata nel plot
                    interp_mask[key] = s_mask
                    continue # Abbiamo gestito questa chiave, passiamo alla successiva

            # Blocco 2: Interpolazione per maschere basate su 'range'
            if 'range' in s_mask:
                s_min, s_max = s_mask['range']
                # Gestione sicura nel caso e_mask non abbia 'range' (improbabile con la logica sopra, ma sicuro)
                e_min, e_max = e_mask.get('range', s_mask['range'])
                i_min = s_min + (e_min - s_min) * shaped_progress
                i_max = s_max + (e_max - s_max) * shaped_progress
                interp_mask[key]['range'] = [i_min, i_max]
                if 'distribution' in s_mask:
                    interp_mask[key]['distribution'] = s_mask['distribution']

            # Blocco 3: Interpolazione per maschere basate su 'mean' e 'std'
            elif 'mean' in s_mask:
                # Gestione sicura dei valori di e_mask
                e_mean = e_mask.get('mean', s_mask['mean'])
                e_std = e_mask.get('std', s_mask['std'])
                i_mean = s_mask['mean'] + (e_mean - s_mask['mean']) * shaped_progress
                i_std = s_mask['std'] + (e_std - s_mask['std']) * shaped_progress
                interp_mask[key]['mean'] = i_mean
                interp_mask[key]['std'] = i_std
                if 'distribution' in s_mask:
                    interp_mask[key]['distribution'] = s_mask['distribution']

            # Blocco 4: Interpolazione/Gestione per maschere basate su 'value'
            elif 'value' in s_mask:
                s_value = s_mask['value']
                e_value = e_mask.get('value', s_value)

                if isinstance(s_value, (int, float)) and isinstance(e_value, (int, float)):
                    # Se sono numeri, interpola
                    i_value = s_value + (e_value - s_value) * shaped_progress
                    interp_mask[key]['value'] = i_value
                else:
                    if s_value != e_value:
                        interp_mask[key] = {
                            'choices': [s_value, e_value],
                            'weights': [1 - shaped_progress, shaped_progress]
                        }
                    else:
                        # Se i valori sono identici, non c'è bisogno di probabilismo.
                        # Manteniamo un valore fisso.
                        interp_mask[key] = s_mask

            # Blocco 5: Interpolazione per maschere basate su 'choices'
            elif 'choices' in s_mask:
                s_choices = s_mask['choices']
                e_choices = e_mask.get('choices', s_choices)
                s_weights = np.array(s_mask.get('weights', [1]*len(s_choices)))
                e_weights = np.array(e_mask.get('weights', [1]*len(e_choices)))
                
                # Cross-fade dei pesi solo se le scelte sono identiche e i pesi compatibili
                if s_choices == e_choices and len(s_weights) == len(e_weights):
                    i_weights = s_weights * (1 - shaped_progress) + e_weights * shaped_progress
                    interp_mask[key] = {'choices': s_choices, 'weights': i_weights.tolist()}
                else:
                    # Altrimenti, transizione a scalino
                    interp_mask[key] = s_mask if shaped_progress < 0.5 else e_mask
            
            # Blocco 6: Fallback per maschere non standard (es. 'tipo_ritmi')
            else:
                # Per maschere complesse che non rientrano nei pattern precedenti
                # (come 'tipo_ritmi' con 'explicit_values'), non interpoliamo.
                # Manteniamo il valore stabile per tutta la durata.
                interp_mask[key] = s_mask

        return interp_mask

    def _process_layer(self, layer, layer_idx, current_time_offset, scaled_section_duration, time_ratio, section_env_table_num, section_name):
        """
        Processa un singolo layer (reale o virtuale) e restituisce i suoi eventi e onsets.
        Questa è una funzione helper per process_composition.
        """
        layer_events = []
        layer_onsets = []
        layer_name = layer.get('nome_layer', "Layer Singolo (compatibilità)")

        print(f"\n  -- Processando {layer_name} --")

        # --- 1: ESTRARRE E INTERPRETARE IL 'LIFESPAN' ---
        lifespan = layer.get('lifespan', [0.0, 1.0])
        start_ratio, end_ratio = lifespan

        # Calcoliamo la durata e il tempo di inizio ASSOLUTI per questo layer
        layer_start_time_abs = current_time_offset + (start_ratio * scaled_section_duration)
        layer_duration_abs = (end_ratio - start_ratio) * scaled_section_duration

        # Controllo di sanità: se la durata è nulla o negativa, salta il layer.
        if layer_duration_abs <= 0:
            print(f"     > ATTENZIONE: Layer '{layer_name}' ha una durata nulla o negativa. Sarà saltato.")
            return [], []

        print(f"     > Finestra Attività: [{start_ratio*100:.0f}%, {end_ratio*100:.0f}%] | Inizio: {layer_start_time_abs:.2f}s, Durata: {layer_duration_abs:.2f}s")

        # --- 1. IDENTIFICA TIPO E TIMING DEL LAYER ---
        is_static_layer = 'stato_unico' in layer
        is_dynamic_layer = 'stato_iniziale' in layer # Aggiunta per chiarezza

        if is_static_layer:
            layer['stato_unico'] = self._normalize_mask(layer['stato_unico'])
        if is_dynamic_layer:
            layer['stato_iniziale'] = self._normalize_mask(layer['stato_iniziale'])
            if 'stato_finale' in layer:
                layer['stato_finale'] = self._normalize_mask(layer['stato_finale'])

        timing_model = layer.get('timing_model', {})
        num_attivazioni = layer.get('num_attivazioni', 10)
        
        print(f"     > Tipo: {'Statico' if is_static_layer else 'Dinamico'}")
        print(f"     > Numero attivazioni: {num_attivazioni}")

        # --- 2. CALCOLA CUSCINETTO E ONSETS PER QUESTO SPECIFICO LAYER ---
        mask_for_buffer = layer.get('stato_unico') if is_static_layer else layer.get('stato_finale')
        if not mask_for_buffer or 'durata_armonica' not in mask_for_buffer or 'range' not in mask_for_buffer['durata_armonica']:
            print(f"     > ERRORE: Maschera 'durata_armonica' mal definita o mancante per il layer '{layer_name}'. Impossibile calcolare il buffer. Layer saltato.")
            return [], []
            
        max_harmonic_dur_unscaled = mask_for_buffer['durata_armonica']['range'][1]
        max_harmonic_dur_scaled = max_harmonic_dur_unscaled * time_ratio
        # 2b. Cerca la maschera per 'moltiplicatore_durata'
        moltiplicatore_mask = mask_for_buffer.get('moltiplicatore_durata')
        max_duration_multiplier = 1.0 # Default se non specificato

        if moltiplicatore_mask and 'choices' in moltiplicatore_mask:
            # Se la maschera esiste, trova il valore massimo tra le scelte possibili
            max_duration_multiplier = max(moltiplicatore_mask['choices'])
        else:
            # Usa LO STESSO default del generatore
            max_duration_multiplier = 1.6        
        print(f"     > Max Durata Armonica: {max_harmonic_dur_scaled:.2f}s, Max Moltiplicatore: {max_duration_multiplier:.2f}x")

        #       Controlla se il safety buffer deve essere usato per questo layer.
        #     Il default è True se il parametro non è specificato nel YAML.
        use_safety_buffer = layer.get('usa_safety_buffer', True)

        safety_buffer = 0.0 # Inizializza a zero
        if use_safety_buffer:
            # 2c. Calcola il cuscinetto usando il VERO moltiplicatore massimo
            safety_buffer = max_harmonic_dur_scaled * max_duration_multiplier
            print(f"     > Cuscinetto di sicurezza calcolato: {safety_buffer:.2f}s")
        else:
            # Se disabilitato, il buffer rimane a 0.0
            print(f"     > Cuscinetto di sicurezza DISABILITATO dall'utente.")
        
        generation_duration = layer_duration_abs - safety_buffer
        
        if generation_duration <= 0:
            print(f"     > ATTENZIONE: Cuscinetto di sicurezza ({safety_buffer:.2f}s) > durata sezione. Nessun evento generato per questo layer.")
            cluster_onsets_relative_to_layer = []
        else:
            cluster_onsets_relative_to_layer = self.time_scheduler.generate_onsets(
                timing_model, generation_duration, num_attivazioni
            )
        
        # --- 3. GENERA GLI EVENTI PER IL LAYER ---
        for onset_relative_to_layer in cluster_onsets_relative_to_layer:
            # Ottieni la maschera di controllo (statica o interpolata) per il layer
            absolute_onset_time = layer_start_time_abs + onset_relative_to_layer

            if is_static_layer:
                center_mask = layer['stato_unico']
            else:
                progress = onset_relative_to_layer / generation_duration if generation_duration > 0 else 0
                start_mask = layer['stato_iniziale']
                end_mask = layer['stato_finale']
                center_mask = self._interpolate_mask(start_mask, end_mask, progress) 


            dens_range = center_mask.get('densita_cluster', {'range': [1,1]})['range']
            num_events_in_cluster = random.randint(int(dens_range[0]), int(dens_range[1]))

            for i in range(num_events_in_cluster):
                for attempt in range(10):
                    event_mask = center_mask.copy()
                    if 'durata_armonica' in event_mask and 'range' in event_mask['durata_armonica']:
                        current_range = event_mask['durata_armonica']['range']
                        scaled_range = [val * time_ratio for val in current_range]
                        event_mask['durata_armonica'] = event_mask['durata_armonica'].copy()
                        event_mask['durata_armonica']['range'] = scaled_range

                    params = self._generate_params_from_mask(event_mask)
                    params['layer_idx_ref'] = layer_idx
                    if self._valida_parametri(params):
                        rhythm_tuple = tuple(params['ritmi'])
                        if rhythm_tuple not in self.rhythm_table_map:
                            self.rhythm_table_map[rhythm_tuple] = {
                                'ritmi_tab_num': self.next_table_id, 'pos_tab_num': self.next_table_id + 1
                            }
                            self.next_table_id += 2
                                # Ora leggiamo il leeway dal layer, con un default di 0.0

                        # 1. Calcola il tempo di inizio REALE dell'evento, INCLUSO il jitter
                        jitter_scale = params.get('onset_jitter', 0.05)
                        jitter = np.random.normal(loc=0.0, scale=jitter_scale)
                        final_event_time = absolute_onset_time + jitter

                        # 2. Calcola la durata desiderata dell'evento
                        base_total_duration = params['durata_totale']
                        layer_leeway = layer.get('leeway_fine_layer', 0.0)
                        leeway_bonus = random.uniform(0.0, layer_leeway) if layer_leeway > 0 else 0.0
                        desired_total_duration = base_total_duration + leeway_bonus

                        # 3. Calcola la durata MASSIMA disponibile partendo dal tempo REALE dell'evento
                        layer_end_time_with_leeway = layer_start_time_abs + layer_duration_abs + layer_leeway
                        available_duration = max(0.0, layer_end_time_with_leeway - final_event_time)

                        # 4. Imposta la durata finale come il minimo tra quella desiderata e quella disponibile
                        params['durata_totale'] = min(desired_total_duration, available_duration)
                        params['ritmi_tab_num'] = self.rhythm_table_map[rhythm_tuple]['ritmi_tab_num']
                        params['pos_tab_num'] = self.rhythm_table_map[rhythm_tuple]['pos_tab_num']
                        params['section_env_table_num'] = section_env_table_num
                        params['section_start_time'] = current_time_offset
                        params['section_duration'] = scaled_section_duration
                        params['section_name'] = section_name
                        params['layer_leeway'] = layer_leeway 



                        layer_onsets.append(absolute_onset_time)

                        event_data = {'type': 'voce', 'time': final_event_time, 'params': params}
                        layer_events.append(event_data)
                        break
                else:
                    print(f"     > ATTENZIONE: Impossibile generare parametri validi per un evento nel layer '{layer_name}'.")

        print(f"     > Eventi 'voce' generati per questo layer: {len(layer_events)}")
        return layer_events, layer_onsets

    def process_composition(self, composition_structure):
        """
        Elabora l'intera struttura della composizione, gestendo sezioni
        con e senza la struttura a layer per retrocompatibilità.
        """
        full_sequence = []
        onsets_by_section = [] 
        all_onsets_flat = [] # Manteniamo anche la lista piatta per usi esistenti
        current_time_offset = 0.0

        solo_mode_active = False
        # Itera su tutta la struttura per trovare almeno un layer con 'solo: True'
        for section in composition_structure:
            if 'layers' in section:
                for layer in section['layers']:
                    if layer.get('solo', False):
                        solo_mode_active = True
                        break # Trovato uno, non serve cercare oltre
            if solo_mode_active:
                break

        if solo_mode_active:
            print("\nMODALITÀ SOLO ATTIVA: Verranno processati solo i layer con 'solo: True'.")


        print("Inizio elaborazione della composizione...")
        for i, section in enumerate(composition_structure):
            section_name = section['nome_sezione']
            section_onsets_data = {'section_name': section['nome_sezione'], 'layers': []}

            # --- 1. GESTIONE PARAMETRI A LIVELLO DI SEZIONE ---
            time_ratio = section.get('ratio_temporale', 1.0)
            scaled_section_duration = section['durata'] * time_ratio
            section_env_table_num = 0 # 0 significa "nessun inviluppo"

            print(f"\n--- Sezione {i+1}: '{section['nome_sezione']}' (Durata: {section['durata']}s, riscalata a x{time_ratio}: {scaled_section_duration}s ) ---")

            section_env_name = section.get('inviluppo_sezione', self.default_section_envelope)
            if section_env_name:
                if section_env_name in self.section_envelope_map:
                    section_env_table_num = self.section_envelope_map[section_env_name]
                    print(f"  > Inviluppo di sezione globale: '{section_env_name}' (userà la tabella f{section_env_table_num})")
                else:
                    print(f"  > ATTENZIONE: Inviluppo di sezione '{section_env_name}' non trovato. Verrà ignorato.")

            layers_to_process = []
            if 'layers' in section:
                layers_to_process = section['layers']
            else: # Retrocompatibilità
                layers_to_process = [section]

            for layer_idx,layer in layers_to_process:
                layer_name = layer.get('nome_layer', "Layer Singolo")

                # Se la modalità solo è attiva, controlliamo se questo layer deve essere saltato.
                if solo_mode_active and not layer.get('solo', False):
                    print(f"\n  -- Saltando layer '{layer_name}' (non in solo) --")
                    # Aggiungiamo un placeholder per il plotting, se necessario
                    section_onsets_data['layers'].append({
                        'layer_name': layer_name,
                        'onsets': []
                    })
                    continue # Salta al prossimo layer
                # La chiamata a _process_layer e il resto della logica rimangono identici
                layer_events, layer_onsets = self._process_layer(
                    layer, 
                    layer_idx, 
                    current_time_offset, 
                    scaled_section_duration, 
                    time_ratio, 
                    section_env_table_num, 
                    section_name
                )
                full_sequence.extend(layer_events)
                section_onsets_data['layers'].append({
                    'layer_name': layer_name,
                    'onsets': layer_onsets
                })
                all_onsets_flat.extend(layer_onsets)

            onsets_by_section.append(section_onsets_data)
            current_time_offset += scaled_section_duration

        last_event_end_time = 0
        if full_sequence:
            last_event = full_sequence[-1]
            last_event_end_time = last_event['time'] + last_event['params']['durata_totale']

        total_calculated_duration = max(current_time_offset, last_event_end_time)
        num_voce_events = len([e for e in full_sequence if e.get('type') == 'voce'])
        print(f"\n✓ Elaborazione completata. Generati {num_voce_events} eventi 'voce' totali.")
        print(f"  > Durata totale calcolata per questa parte: {total_calculated_duration:.2f} secondi.")
        print(f"Mappati {len(self.rhythm_table_map)} pattern di ritmi unici a tabelle Csound.")

        # RESTITUISCI LA DURATA CALCOLATA
        return full_sequence, all_onsets_flat, onsets_by_section, total_calculated_duration

    def generate_csd(self, composition_name, events, csd_file_path, wav_file_path): # <<< PARAMETRI AGGIUNTI
        """Genera il file CSD finale dalla sequenza di eventi."""
        # Rimosso il print iniziale che ora è gestito dal chiamante
        
        # --- 1. COSTRUZIONE DEGLI F-STATEMENTS PER I RITMI ---
        rhythm_tables_str = ""
        # ... (il resto di questa sezione è IDENTICO) ...
        for rhythm_tuple, table_ids in self.rhythm_table_map.items():
            ritmi_str = ' '.join(map(str, rhythm_tuple))
            posizioni = [i % r for i, r in enumerate(rhythm_tuple) if r > 0]
            posizioni_str = ' '.join(map(str, posizioni))
            rhythm_tables_str += f"f {table_ids['ritmi_tab_num']} 0 {len(rhythm_tuple)} -2 {ritmi_str}\n"
            rhythm_tables_str += f"f {table_ids['pos_tab_num']} 0 {len(posizioni)} -2 {posizioni_str}\n"

        # --- 2. COSTRUZIONE DINAMICA DEGLI F-STATEMENTS PER GLI INVILUPPI ---
        envelope_tables_str = "; --- TABELLE DEGLI INVILUPPI (generate da tables.yaml) ---\n"
        # ... (il resto di questa sezione è IDENTICO) ...
        all_envelope_configs = {**self.event_envelopes_config, **self.section_envelopes_config}
        for name, config in all_envelope_configs.items():
            params_str = ' '.join(map(str, config['parameters']))
            envelope_tables_str += f"; {name}\n"
            envelope_tables_str += f"f {config['number']} 0 {config['size']} {config['gen_routine']} {params_str}\n"

        # --- 3. COSTRUZIONE DELLE LINEE DI SCORE PER GLI EVENTI ---
        score_lines = ""
        last_event_time = 0
        current_section_name = None 
        # ... (tutta la logica di generazione delle linee di score è IDENTICA) ...
        for event in events:
            p = event['params']
            event_time = max(event['time'], 0.001)
            if event['type'] == 'voce':
                if p.get('section_name') != current_section_name:
                    current_section_name = p.get('section_name')
                    section_start = p.get('section_start_time', 0)
                    section_dur = p.get('section_duration', 0)
                    score_lines += f'\n; =============================================================================\n'
                    score_lines += f'; SEZIONE: "{current_section_name}"\n'
                    score_lines += f'; Inizio: {section_start:.3f}s, Durata: {section_dur:.3f}s\n'
                    score_lines += f'; =============================================================================\n\n'

                score_lines += ";\t\t\tat\t\t\tdur\t\ttab\t\tarmonica\tdinamica\tottava\tregistro\tnew_ottava\tnew_registro\tpos\t\tid_comp\tnonlinearMode\tmovimento\tifn_attacco\tenv_sezione\tsez_attacco\tsez_durata\tsez_leeway\t safety_buffer\n"
                score_lines += (f'i "Voce"\t{event_time:.4f}\t{p["durata_totale"]:.3f}\t'
                                f'{p["ritmi_tab_num"]}\t{p["durata_armonica"]:.3f}\t\t{p["dynamic_index"]:.6f}\t'
                                f'{p["ottava"]}\t\t{p["registro"]}\t\t\t'
                                f'{p["ottava_arrivo"]}\t\t{p["registro_arrivo"]}\t\t'
                                f'{p["pos_tab_num"]}\t{p["id_comp"]}\t\t{p["nonlinear_mode"]}'
                                f'\t\t\t\t{p["senso_movimento"]}\t\t\t{p["ifn_attacco"]}\t\t\t{p.get("section_env_table_num", 0)}'
                                f'\t\t\t{p.get("section_start_time", 0):.4f}\t\t{p.get("section_duration", 0):.3f}'
                                f'\t\t{p.get("layer_leeway", 0):.3f}\t\t{p.get("usa_safety_buffer", True):d}\n')
                last_event_time = max(last_event_time, event_time + p["durata_totale"])

        # --- 4. ASSEMBLAGGIO DEL FILE FINALE ---
        # <<< RIMOSSA LA COSTRUZIONE INTERNA DEI PERCORSI >>>
            
        template = self.get_csd_template()
        
        # Path relativo da csd_file_path a includes/ — repo portable
        import os
        csd_dir = Path(csd_file_path).parent.resolve()
        includes_abs = (self.base_path / "includes").resolve()
        includes_path = os.path.relpath(includes_abs, csd_dir)
        
        csd_content = template.format(
            wav_file_path=wav_file_path,
            includes_path=includes_path, # <-- NUOVO: Passa il percorso al template
            envelope_tables=envelope_tables_str,
            rhythm_tables=rhythm_tables_str,
            score_lines=score_lines,
            durata_totale=last_event_time + 10,
            ottave_macro = OTTAVE_RANGE[1],
            registri_macro = REGISTRI_RANGE[1],
            intervalli_macro = INTERVALLI_PER_OTTAVA
        )

        with open(csd_file_path, 'w') as f:
            f.write(csd_content)
            
    def get_csd_template(self):
        """Restituisce il template CSD master."""
        return """
<CsoundSynthesizer>
<CsOptions>
-o "{wav_file_path}" -W -d -m0
</CsOptions>
<CsInstruments>
sr = 96000
ksmps = 32
nchnls = 2
0dbfs = 1

#define SQRT2 #1.4142135623730951#
#define MAX_AMP #0.999#
#define FONDAMENTALE #32#
#define OTTAVE #{ottave_macro}#
#define INTERVALLI #{intervalli_macro}#
#define REGISTRI #{registri_macro}#
#define M_PI #3.141592653589793#
gSdirSco = "./sco/"
gi_Index init 2
gi_eve_attacco ftgen 0, 0, 2^20, -2, 0
gi_Intonazione ftgen 0, 0, $OTTAVE*$INTERVALLI+1, -2, 0

gi_debug init 1

#include "{includes_path}/gamma_utils.udo"
#include "{includes_path}/pfield_comp.udo"
#include "{includes_path}/NonlinearFunc.udo"
#include "{includes_path}/GenPythagFreqs.udo"
#include "{includes_path}/initIsoAmp.orc"
#include "{includes_path}/eventoSonoro.orc"
#include "{includes_path}/voce.orc"

instr time
    ktime times
    if gi_debug > 1 then
    printk 1,ktime
    endif
endin

instr Init
    i_Res GenPythagFreqs $FONDAMENTALE, $INTERVALLI, $OTTAVE, gi_Intonazione
    if i_Res == 0 then
        prints "ERRORE: Inizializzazione del sistema pitagorico fallita!\\n"
    endif
    ires system_i 1, sprintf("mkdir %s", gSdirSco)
    turnoff
endin
</CsInstruments>
<CsScore>
f 0 {durata_totale} ; Evento f fittizio per definire la durata totale
f1 0 4096 10 1


; ==============================================================================
; TABELLE DEFINITE DINAMICAMENTE
; ==============================================================================

{envelope_tables}

{rhythm_tables}

i "time" 0 {durata_totale}
i "Init" 0 0.1

; --- EVENTI GENERATI ---
{score_lines}
; ---------------------

e
</CsScore>
</CsoundSynthesizer>
"""


class CompositionDebugger:
    """Utility per visualizzare la composizione generata."""
    def __init__(self, output_dir):
        self.output_path = Path(output_dir)
        self._labels_added = set()

    def _calculate_plot_data_for_layer(self, layer, start_mask, end_mask, layer_onsets, time_ratio, composer, page_duration_s):
        """
        Calcola i dati numerici per plottare le maschere di un layer.
        """
        if not layer_onsets:
            return None

        first_onset_time = min(layer_onsets)
        last_onset_time = max(layer_onsets)
        plot_duration = last_onset_time - first_onset_time
        min_plot_duration = page_duration_s / 12.0 
        if plot_duration < min_plot_duration:
            plot_duration = min_plot_duration

        num_samples = 100
        times = np.linspace(first_onset_time, first_onset_time + plot_duration, num_samples)
        
        plot_data = {'times': times, 'ottava': None, 'durata': None, 'dinamica': None}
        ottava_lower, ottava_upper = [], []
        durata_lower, durata_upper = [], []
        dynamics_line_trend, dynamics_prob_weights = [], []
        
        has_ottava = 'ottava' in start_mask
        has_durata = 'durata_armonica' in start_mask
        has_dinamica = 'dinamica' in start_mask
        is_dynamic_choices = has_dinamica and 'choices' in start_mask.get('dinamica', {})

        for p in np.linspace(0, 1, num_samples):
            interp_mask = composer._interpolate_mask(start_mask, end_mask, p)
            
            if has_ottava:
                mask = interp_mask.get('ottava', {})
                lower, upper = OTTAVE_RANGE
                if 'range' in mask: lower, upper = mask['range']
                elif 'mean' in mask: lower, upper = mask['mean'] - mask['std'], mask['mean'] + mask['std']
                ottava_lower.append(lower)
                ottava_upper.append(upper)

            if has_durata:
                mask = interp_mask.get('durata_armonica', {})
                lower, upper = (1, 1)
                if 'range' in mask: lower, upper = [d * time_ratio for d in mask['range']]
                elif 'mean' in mask: lower, upper = mask['mean'] - mask['std'], mask['mean'] + mask['std']
                durata_lower.append(lower)
                durata_upper.append(upper)
            
            if has_dinamica:
                if is_dynamic_choices:
                    weights = interp_mask.get('dinamica', {}).get('weights', [1 / len(start_mask['dinamica']['choices'])] * len(start_mask['dinamica']['choices']))
                    dynamics_prob_weights.append(weights)
                else:
                    if 'dynamic_index' in interp_mask:
                        dynamics_line_trend.append(interp_mask['dynamic_index'])
                    elif 'value' in interp_mask.get('dinamica', {}):
                        dyn_str = interp_mask['dinamica']['value']
                        dynamics_line_trend.append(composer.dynamic_to_index.get(dyn_str, 3))
                    else:
                        dynamics_line_trend.append(np.nan)

        if has_ottava:
            plot_data['ottava'] = {'lower': ottava_lower, 'upper': ottava_upper}
        if has_durata:
            plot_data['durata'] = {'lower': durata_lower, 'upper': durata_upper}
        if has_dinamica:
            plot_data['dinamica'] = {
                'is_probabilistic': is_dynamic_choices,
                'line_trend': dynamics_line_trend,
                'prob_weights': dynamics_prob_weights,
                'choices': start_mask['dinamica'].get('choices', []) if is_dynamic_choices else []
            }
            
        return plot_data

    def _plot_parameter_envelope(self, ax, times, data, color, label_key, label_text):
        """
        Disegna una singola "busta" di tendenza (un fill_between).
        """
        if not data:
            return
            
        label = label_text if label_key not in self._labels_added else ""
        ax.fill_between(times, data['lower'], data['upper'], color=color, alpha=0.2, zorder=1, label=label)
        self._labels_added.add(label_key)

    def _plot_dynamics(self, ax_linear, ax_prob, times, dynamics_data, layer_color, layer_name):
        """
        Gestisce il plotting per la 'dinamica', scegliendo l'asse corretto.
        """
        if not dynamics_data:
            return

        if dynamics_data['is_probabilistic']:
            # Logica per lo stack plot (dinamica probabilistica) sull'asse `ax_prob`
            if dynamics_data['prob_weights']:
                weights_per_dynamic = np.array(dynamics_data['prob_weights']).T
                dynamic_labels = dynamics_data['choices']
                
                stackplot_labels = [f"Prob. {label}" for label in dynamic_labels] if 'prob_stack' not in self._labels_added else ["" for _ in dynamic_labels]
                cmap = plt.get_cmap('viridis')
                stackplot_colors = cmap(np.linspace(0.1, 0.9, len(dynamic_labels)))
                
                # Applica le etichette all'asse `ax_prob`
                if 'prob_axis' not in self._labels_added:
                    ax_prob.set_ylabel("Prob. Dinamica")
                    ax_prob.set_ylim(0, 1)
                    ax_prob.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
                    ax_prob.set_yticklabels(['0%', '25%', '50%', '75%', '100%'])
                    self._labels_added.add('prob_axis')
                
                ax_prob.stackplot(times, weights_per_dynamic, 
                                 labels=stackplot_labels, colors=stackplot_colors,
                                 alpha=0.6, zorder=2)
                self._labels_added.add('prob_stack')
        else:
            # Logica per il grafico a linea (dinamica lineare) sull'asse `ax_linear`
            if dynamics_data['line_trend']:
                valid_times = [t for t, d in zip(times, dynamics_data['line_trend']) if not np.isnan(d)]
                valid_dynamics = [d for d in dynamics_data['line_trend'] if not np.isnan(d)]
                if valid_times:
                    ax_linear.plot(valid_times, valid_dynamics, color=layer_color, linewidth=2.5, 
                                label=f"Dinamica: {layer_name}", zorder=3, alpha=0.8)

    def _plot_tendency_masks(self, ax_pitch, ax_dur, ax_dyn_linear, ax_dyn_prob, composition_structure, composer, onsets_by_section, page_duration_s):
        """
        RIFATTORIZZATA: Ora agisce come un orchestratore.
        """
        print("  > Visualizzo le maschere di tendenza...")
        
        layer_colors = {}
        color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
        
        for section_idx, section in enumerate(composition_structure):
            time_ratio = section.get('ratio_temporale', 1.0)
            layers_to_process = section.get('layers', [])
            section_onsets_data = onsets_by_section[section_idx]['layers']

            for layer_idx, layer in enumerate(layers_to_process):
                layer_onsets_info = section_onsets_data[layer_idx]
                layer_onsets = layer_onsets_info['onsets']
                layer_name = layer.get('nome_layer', f"Layer {layer_idx+1}")
                
                if layer_name not in layer_colors:
                    layer_colors[layer_name] = color_cycle[len(layer_colors) % len(color_cycle)]
                layer_color = layer_colors[layer_name]

                if 'stato_unico' in layer:
                    start_mask = composer._normalize_mask(layer['stato_unico'])
                    end_mask = start_mask
                elif 'stato_iniziale' in layer:
                    start_mask = composer._normalize_mask(layer['stato_iniziale'])
                    end_mask = composer._normalize_mask(layer.get('stato_finale', layer['stato_iniziale']))
                else: continue

                plot_data = self._calculate_plot_data_for_layer(layer, start_mask, end_mask, layer_onsets, time_ratio, composer, page_duration_s)

                if plot_data:
                    # --- QUI PUOI MODIFICARE I COLORI DELLE MASCHERE ---
                    colore_maschera_ottava = 'gray'
                    colore_maschera_durata = 'orange'
                    
                    self._plot_parameter_envelope(ax_pitch, plot_data['times'], plot_data['ottava'], 
                                                  colore_maschera_ottava, 'maschera_ottava', 'Maschera Ottava')
                                                  
                    self._plot_parameter_envelope(ax_dur, plot_data['times'], plot_data['durata'], 
                                                  colore_maschera_durata, 'maschera_durata', 'Maschera Durata Armonica')

                    # Passa entrambi gli assi alla funzione di plotting della dinamica
                    self._plot_dynamics(ax_dyn_linear, ax_dyn_prob, plot_data['times'], plot_data['dinamica'], 
                                        layer_color, layer_name)

    def _prepare_plot_data(self, events, composition_structure):
        """Prepara tutti i dati necessari per il plotting."""
        # Blocco 1: Calcolo metadati dei layer
        plot_metadata = []
        end_time_of_last_section_calc = 0.0
        for section in composition_structure:
            time_ratio = section.get('ratio_temporale', 1.0)
            scaled_duration = section.get('durata', 0) * time_ratio
            section_start_abs = max(0.0, end_time_of_last_section_calc + section.get('offset_inizio', 0.0))
            
            section_meta = {'layers': []}
            layers_in_section = section.get('layers', [])
            for layer_idx, layer in enumerate(layers_in_section):
                lifespan = layer.get('lifespan', [0.0, 1.0])
                start_ratio, end_ratio = lifespan
                layer_meta = {
                    'layer_name': layer.get('nome_layer', f'Layer {layer_idx+1}'),
                    'layer_start_abs': section_start_abs + (start_ratio * scaled_duration),
                    'layer_duration_abs': (end_ratio - start_ratio) * scaled_duration
                }
                section_meta['layers'].append(layer_meta)
            plot_metadata.append(section_meta)
            end_time_of_last_section_calc = section_start_abs + scaled_duration

        # Blocco 2: Calcolo dati degli eventi
        plot_data_list = []
        total_duration = 0
        max_durata_armonica = 0
        # NOTA: Dobbiamo passare composer a questa funzione per questo calcolo.
        # Per ora, lo omettiamo e lo gestiamo nella funzione principale.
        # Questa parte è più difficile da isolare, la lasciamo dov'è per ora.

        # Determiniamo i colori dei layer una sola volta
        layer_colors = {}
        color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
        all_layers_names = [layer['layer_name'] for section in plot_metadata for layer in section['layers']]
        for name in sorted(list(set(all_layers_names))):
            if name not in layer_colors:
                layer_colors[name] = color_cycle[len(layer_colors) % len(color_cycle)]

        return plot_metadata, layer_colors

    def _setup_plot_page(self, fig, composer, max_durata_armonica, page_start_time, page_end_time):
        """Configura gli assi e le etichette per una singola pagina del grafico."""
        ax_pitch, ax_dyn_linear, ax_dyn_prob = fig.get_axes()
        ax_dur = ax_pitch.twinx()

        ax_pitch.set_ylim(OTTAVE_RANGE[0] - 1, OTTAVE_RANGE[1] + 1)
        ax_pitch.set_ylabel("Ottava.Registro")
        ax_pitch.set_yticks(range(OTTAVE_RANGE[0], OTTAVE_RANGE[1] + 2))
        ax_pitch.tick_params(axis='x', labelbottom=False)

        ax_dur.set_ylabel("Durata Armonica (s)", color='darkcyan')
        ax_dur.set_ylim(0, max_durata_armonica * 1.5 if max_durata_armonica > 0 else 10)
        ax_dur.tick_params(axis='y', labelcolor='darkcyan')

        ax_dyn_linear.set_ylabel("Dinamica (Lineare)")
        dyn_labels = list(composer.dynamic_to_index.keys())
        dyn_ticks = list(composer.dynamic_to_index.values())
        ax_dyn_linear.set_yticks(dyn_ticks)
        ax_dyn_linear.set_yticklabels(dyn_labels)
        ax_dyn_linear.set_ylim(min(dyn_ticks) - 0.5, max(dyn_ticks) + 0.5)
        ax_dyn_linear.grid(True, axis='y', linestyle='--', alpha=0.6)
        ax_dyn_linear.tick_params(axis='x', labelbottom=False)

        ax_dyn_prob.set_ylabel("Prob. Dinamica")
        ax_dyn_prob.set_xlabel(f"Tempo (secondi, da {int(page_start_time)}s a {int(page_end_time)}s)")
        ax_dyn_prob.grid(True, axis='y', linestyle='--', alpha=0.6)

        ax_pitch.set_xlim(page_start_time, page_end_time)
        
        return ax_pitch, ax_dur, ax_dyn_linear, ax_dyn_prob

    def _draw_layer_areas(self, ax_pitch, plot_metadata, layer_colors, page_start_time, page_end_time):
        """Disegna le linee verticali di inizio e fine per ogni layer."""
                
        for section_meta in plot_metadata:
            for layer_info in section_meta['layers']:
                start = layer_info['layer_start_abs']
                duration = layer_info['layer_duration_abs']
                end = start + duration
                
                # Disegna solo se il layer è in qualche modo visibile in questa pagina
                if start < page_end_time and end > page_start_time and duration > 0:
                    layer_color = layer_colors.get(layer_info['layer_name'], 'grey')
                                        
                    if page_start_time <= start < page_end_time:
                        ax_pitch.axvline(x=start, color=layer_color, linestyle=':', linewidth=1.5, zorder=1, alpha=0.7)

                    if page_start_time <= end < page_end_time:
                        ax_pitch.axvline(x=end, color=layer_color, linestyle=':', linewidth=1.5, zorder=1, alpha=0.7)

                    label_key = f"layer_label_{layer_info['layer_name']}"

                    if start >= page_start_time and label_key not in self._labels_added:
                        _, y_max = ax_pitch.get_ylim() 
                        ax_pitch.text(
                            start + 0.5, # Un po' a destra della linea di inizio
                            y_max - 0.2, # In cima al grafico
                            layer_info['layer_name'],
                            ha='left', va='top', fontsize='x-small',
                            color=layer_color, alpha=0.9, weight='bold'
                        )
                        self._labels_added.add(label_key)
                        
    def _draw_events(self, ax_pitch, plot_data_list, page_start_time, page_end_time):
        """Disegna gli eventi sonori (rettangoli delle note)."""
        for item in plot_data_list:
            if item['start'] < page_end_time and (item['start'] + item['duration']) > page_start_time:
                ax_pitch.add_patch(plt.Rectangle((item['start'], item['pitch'] - 0.04), item['duration'], 0.08, color=plt.cm.viridis(item['amp_norm']), alpha=0.6, zorder=3))

    def _draw_section_markers(self, axes, composition_structure, page_start_time, page_end_time):
        """Disegna i marcatori di inizio e fine sezione."""
        ax_pitch, ax_dyn_linear, ax_dyn_prob = axes
        end_time_of_last_section = 0.0
        for section in composition_structure:
            offset = section.get('offset_inizio', 0.0)
            section_start = max(0.0, end_time_of_last_section + offset)
            scaled_duration = section.get('durata', 0) * section.get('ratio_temporale', 1.0)
            section_end = section_start + scaled_duration
            
            if page_start_time <= section_start < page_end_time:
                label_text = f"Inizio: {section['nome_sezione']}" if f"inizio_{section['nome_sezione']}" not in self._labels_added else ""
                for ax in axes:
                    ax.axvline(x=section_start, color='green', linestyle='--', linewidth=1.2, label=label_text if ax is ax_pitch else "")
                self._labels_added.add(f"inizio_{section['nome_sezione']}")
                
            if page_start_time <= section_end < page_end_time:
                label_text = f"Fine: {section['nome_sezione']}" if f"fine_{section['nome_sezione']}" not in self._labels_added else ""
                for ax in axes:
                    ax.axvline(x=section_end, color='r', linestyle='--', linewidth=1.2, label=label_text if ax is ax_pitch else "")
                self._labels_added.add(f"fine_{section['nome_sezione']}")
                
            end_time_of_last_section = section_end

    def _collect_and_draw_legend(self, fig, axes):
        """Raccoglie le etichette da tutti gli assi e disegna la legenda."""
        handles, labels = [], []
        for ax in axes:
            h, l = ax.get_legend_handles_labels()
            handles.extend(h)
            labels.extend(l)
        
        # Aggiungiamo anche gli assi "twin"
        for ax in fig.get_axes():
            if isinstance(ax, plt.Axes) and ax not in axes:
                h, l = ax.get_legend_handles_labels()
                handles.extend(h)
                labels.extend(l)
                
        fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, -0.08), ncol=8, fontsize='x-small')

    def plot_piano_roll(self, events, all_onsets, composition_name, composition_structure, composer, onsets_by_section, title=None, 
                        partitura_mode=False, page_duration_s=60):
        """
        Crea un grafico multi-pagina della composizione, orchestrando la preparazione e il disegno.
        """
        print(f"\n--- Generazione Grafico {'(Modalità Partitura)' if partitura_mode else '(Pagina Singola)'}: '{composition_name}' ---")
        if not events:
            print("Nessun evento da visualizzare."); return

        # --- FASE 1: Preparazione Dati ---
        plot_data_list = []
        total_duration = 0
        max_durata_armonica = 0
        for event in events:
            if event.get('type') == 'voce':
                p = event['params']
                start, duration = event['time'], p['durata_totale']
                plot_data_list.append({'start': start, 'duration': duration, 'pitch': p['ottava'] + (p['registro'] / (REGISTRI_RANGE[1] + 1.0)), 'amp_norm': p.get('dynamic_index', 3) / len(composer.dynamic_to_index)})
                if (start + duration) > total_duration: total_duration = start + duration
                if p['durata_armonica'] > max_durata_armonica: max_durata_armonica = p['durata_armonica']

        # Estraiamo la preparazione dei metadati che è stata isolata
        plot_metadata, layer_colors = self._prepare_plot_data(events, composition_structure)
        
        # --- FASE 2: Setup PDF e Loop Pagine ---
        file_suffix = "_partitura.pdf" if partitura_mode else "_visual_A3.pdf"
        plot_filename = self.output_path / f"{composition_name}{file_suffix}"
        
        with PdfPages(plot_filename) as pdf:
            num_pages = int(np.ceil(total_duration / page_duration_s)) if partitura_mode else 1
            if num_pages == 0: num_pages = 1

            for i in range(num_pages):
                self._labels_added = set() 
                page_start_time = i * page_duration_s if partitura_mode else 0
                page_end_time = (i + 1) * page_duration_s if partitura_mode else total_duration

                # --- FASE 3: Setup della Pagina ---
                A3_LANDSCAPE_WIDTH_INCHES = 420 / 25.4
                A3_LANDSCAPE_HEIGHT_INCHES = 297 / 25.4
                fig, axes_tuple = plt.subplots(
                    nrows=3, ncols=1, figsize=(A3_LANDSCAPE_WIDTH_INCHES, A3_LANDSCAPE_HEIGHT_INCHES), 
                    sharex=True, gridspec_kw={'height_ratios': [3, 1, 1]}
                )
                ax_pitch, ax_dyn_linear, ax_dyn_prob = axes_tuple
                
                fig.suptitle(f"{title} (Pagina {i+1}/{num_pages})" if partitura_mode else title, fontsize=14)
                
                ax_pitch, ax_dur, ax_dyn_linear, ax_dyn_prob = self._setup_plot_page(
                    fig, composer, max_durata_armonica, page_start_time, page_end_time
                )

                # --- FASE 4: Disegno degli Elementi ---
                self._draw_layer_areas(ax_pitch, plot_metadata, layer_colors, page_start_time, page_end_time)
                self._draw_events(ax_pitch, plot_data_list, page_start_time, page_end_time)
                
                page_onsets = [o for o in all_onsets if page_start_time <= o < page_end_time]
                if page_onsets:
                    ax_pitch.vlines(page_onsets, ymin=OTTAVE_RANGE[0] - 1, ymax=OTTAVE_RANGE[1] + 1, color='dodgerblue', linestyle=':', linewidth=0.9, alpha=0.6, label='Attivazione')
                
                self._plot_tendency_masks(ax_pitch, ax_dur, ax_dyn_linear, ax_dyn_prob, composition_structure, composer, onsets_by_section, page_end_time - page_start_time)
                
                self._draw_section_markers((ax_pitch, ax_dyn_linear, ax_dyn_prob), composition_structure, page_start_time, page_end_time)
                
                # --- FASE 5: Finalizzazione e Salvataggio ---
                self._collect_and_draw_legend(fig, [ax_pitch, ax_dyn_linear, ax_dyn_prob])

                fig.tight_layout(rect=[0, 0.07, 1, 0.95])
                pdf.savefig(fig)
                plt.close(fig)

        print(f"✓ Grafico salvato in: {plot_filename}")

def generate_silent_wav(output_wav_path, duration):
    """
    Genera un file WAV di silenzio digitale della durata specificata usando Csound.
    """
    # Assicurati che la directory di output esista
    output_wav_path.parent.mkdir(exist_ok=True, parents=True)

    # Il CSD più semplice possibile per creare un file di una certa durata
    csd_content = f"""
<CsoundSynthesizer>
<CsOptions>
-o "{output_wav_path}" -W -d
</CsOptions>
<CsInstruments>
sr = 96000
ksmps = 32
nchnls = 2
0dbfs = 1
</CsInstruments>
<CsScore>
f 0 {duration} ; Imposta la durata totale del file
e
</CsScore>
</CsoundSynthesizer>
"""
    # Usa un percorso temporaneo per il file CSD
    temp_csd_path = output_wav_path.parent / f"__{output_wav_path.stem}_silent_gen.csd"
    try:
        with open(temp_csd_path, 'w') as f:
            f.write(csd_content)        
        # Dentro generate_silent_wav
        subprocess.run(['csound', '--format=float', str(temp_csd_path)], check=True, capture_output=True)
        print(f"   ✓ Generato WAV silenzioso di {duration:.2f}s: {output_wav_path.name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ✗ ERRORE: Creazione del WAV silenzioso per '{output_wav_path.name}' fallita.")
        print(e.stderr)
        return False
    except Exception as e:
        print(f"   ✗ ERRORE INATTESO durante la generazione del WAV silenzioso: {e}")
        return False
    finally:
        # Pulisci il file CSD temporaneo
        if temp_csd_path.exists():
            temp_csd_path.unlink()

def sanitize_filename(name):
    """Converte una stringa in un nome di file sicuro."""
    name = name.lower()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^a-z0-9_-]', '', name)
    return name

def run_csound_process(csd_path, process_name, log_dir):
    """Lancia un singolo processo Csound e restituisce l'oggetto Popen."""
    log_file_path = log_dir / f"csound_render_{process_name}.log"
    print(f"    - Avvio rendering per '{process_name}' (Log: {log_file_path.name})")
    try:
        log_file = open(log_file_path, 'w')
        process = subprocess.Popen(['csound', '--format=float', str(csd_path)], stdout=log_file, stderr=log_file)
        return (process, process_name, log_file)
    except Exception as e:
        print(f"    - ERRORE CRITICO nel lanciare Csound per {process_name}: {e}")
        return None

def generate_assembler_csd(csd_path, output_wav_path, input_files_with_onsets, title="Assembler"):
    score_lines = ""
    for file_path, onset in input_files_with_onsets:
        try:
            relative_path = Path(file_path)
        except ValueError:
            relative_path = file_path

        score_lines += f'i "orchestrator" {onset:.4f} [60*8-{onset:.4f}] "{relative_path}"\n'
    template = f"""<CsoundSynthesizer>
<CsOptions>
-o "{output_wav_path}" -W -d -m0
</CsOptions>
<CsInstruments>
; --- {title} ---
sr=96000
ksmps=32
nchnls=2
0dbfs=1
instr orchestrator
    S_file strget p4
    i_dur filelen S_file
    if i_dur > 0 then
        prints "Scheduling '%s' (dur: %.2fs) at time %.2fs\\n", S_file, i_dur, p2
        schedule "playFile", 0, i_dur, S_file
    else
        prints "WARNING: Could not play file '%s'.\\n", S_file
    endif
endin
instr playFile
    a_L, a_R diskin2 p4, 1
    outs a_L, a_R
endin
</CsInstruments>
<CsScore>
{score_lines}
e
</CsScore>
</CsoundSynthesizer>"""
    with open(csd_path, 'w') as f: f.write(template)
    return csd_path

def run_csound_process(csd_path, process_name, log_dir):
    """
    Lancia un singolo processo Csound e restituisce l'oggetto Popen e il file di log.
    """
    log_file_path = log_dir / f"csound_render_{process_name}.log"
    print(f"    - Avvio rendering per '{process_name}' (Log: {log_file_path.name})")
    try:
        log_file = open(log_file_path, 'w')
        process = subprocess.Popen(['csound', '--format=float', str(csd_path)], stdout=log_file, stderr=log_file)
        return (process, process_name, log_file)
    except Exception as e:
        print(f"    - ERRORE CRITICO nel lanciare Csound per {process_name}: {e}")
        return None

def plan_render_jobs(all_composition_structures, base_composition_name, dirs, veteran_mode_active):
    """
    FASE 1: Analizza la partitura e pianifica tutti i lavori.
    Supporta 'offset_inizio' per ogni sezione e mantiene la struttura a Parti.
    """
    print("\n--- FASE 1: Analisi della Partitura e Pianificazione dei Job ---")
    
    layer_render_jobs = []
    section_assembly_jobs = []
    final_assembly_parts = []
    full_composition_structure_for_plot = [sec for part in all_composition_structures for sec in part]
    
    end_time_of_last_section = 0.0

    for i, part_structure in enumerate(all_composition_structures):
        part_name_base = f"{base_composition_name}_part_{i+1}"
        print(f"\n--- Analisi Part {i+1}: '{part_name_base}' ---")
        
        for sec_idx, section in enumerate(part_structure):
            section_name = section['nome_sezione']
            
            # 1. Calcola il nuovo tempo di inizio usando il contatore globale
            offset = section.get('offset_inizio', 0.0)
            absolute_section_onset = max(0.0, end_time_of_last_section + offset)
            
            # 2. Calcola la durata e il punto finale di questa sezione
            scaled_duration = section.get('durata', 0) * section.get('ratio_temporale', 1.0)
            section_end_time = absolute_section_onset + scaled_duration
            
            print(f"  > Sezione: '{section_name}' (Offset: {offset}s, Inizio: {absolute_section_onset:.2f}s, Dur: {scaled_duration:.2f}s)")

            # 3. Aggiorna il contatore globale per la prossima iterazione
            end_time_of_last_section = section_end_time

            # 4. Logica di pianificazione (usa la struttura di naming a Parti)
            section_name_base = f"{part_name_base}_sec_{sec_idx+1}_{sanitize_filename(section_name)}"
            section_wav_path = dirs['sections_wav'] / f"{section_name_base}.wav"
            
            final_assembly_parts.append({'wav_path': section_wav_path, 'onset': absolute_section_onset})

            layers_in_section = section.get('layers', [])
            if not layers_in_section:
                if scaled_duration > 0:
                    generate_silent_wav(section_wav_path, scaled_duration)
                continue

            section_needs_reassembly = False
            layer_files_for_this_section = []

            for j, layer in enumerate(layers_in_section):
                layer_name = layer.get('nome_layer', f'layer_{j+1}')
                layer_render_name = f"{section_name_base}_layer_{j+1}_{sanitize_filename(layer_name)}"
                
                should_render_layer = not veteran_mode_active or layer.get('veteranMode', False)
                if should_render_layer:
                    section_needs_reassembly = True
                    layer_render_jobs.append({
                        'layer': layer, 'section': section, 'layer_idx': j,
                        'csd_path': dirs['layers_csd'] / f"{layer_render_name}.csd",
                        'wav_path': dirs['layers_wav'] / f"{layer_render_name}.wav",
                        'name': layer_render_name,
                        'absolute_section_onset': absolute_section_onset
                    })
                
                layer_files_for_this_section.append((dirs['layers_wav'] / f"{layer_render_name}.wav", 0.0))
            
            if not veteran_mode_active or section_needs_reassembly:
                 section_assembly_jobs.append({
                     'name': section_name_base,
                     'csd_path': dirs['sections_csd'] / f"{section_name_base}_assembler.csd",
                     'output_wav': section_wav_path, 'input_layers': layer_files_for_this_section
                 })
                 
    return layer_render_jobs, section_assembly_jobs, final_assembly_parts, full_composition_structure_for_plot

def _sanitize_data_for_json(data):
    """
    NUOVA HELPER: Converte ricorsivamente un oggetto di dati per renderlo
    compatibile con JSON, trasformando array NumPy in liste, float NumPy in float Python,
    e oggetti Path in stringhe.
    """
    if isinstance(data, dict):
        # Per i dizionari, sanitizza ogni valore
        return {k: _sanitize_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        # Per le liste, sanitizza ogni elemento
        return [_sanitize_data_for_json(v) for v in data]
    
    # --- NUOVA REGOLA DI CONVERSIONE ---
    elif isinstance(data, Path):
        # Converte un oggetto Path in una semplice stringa
        return str(data)
    # --- FINE NUOVA REGOLA ---

    elif isinstance(data, np.ndarray):
        # Converte un array NumPy in una lista
        return data.tolist()
    elif isinstance(data, (np.float64, np.int64)):
        # Converte tipi numerici di NumPy in tipi standard Python
        return float(data)
    
    # Per tutti gli altri tipi (stringhe, int, float, bool, None), restituisci il valore così com'è
    return data

def execute_layer_rendering_and_collect_data(render_jobs, dirs, veteran_mode_active): # <-- Aggiunto veteran_mode_active
    """
    FASE 2: Esegue il rendering dei layer e raccoglie i dati per il plot.
    MODIFICATA: Se non in veteranMode, salva i dati raccolti in una cache JSON.
    """
    print("\n--- FASE 2: Esecuzione Rendering dei Layer e Raccolta Dati ---")

    if not render_jobs:
        print("Nessun layer da renderizzare. Fase saltata.")
        return None

    plot_data = {
        'events': [],
        'onsets_flat': [],
        'render_jobs_info': []
    }
    
    csound_procs = []
    composer = GenerativeComposer()

    for job in render_jobs:
        print(f"  > Processando Layer: '{job['name']}'")
        
        scaled_sec_dur = job['section'].get('durata', 0) * job['section'].get('ratio_temporale', 1.0)
        sec_env_num = composer.section_envelope_map.get(job['section'].get('inviluppo_sezione', composer.default_section_envelope), 0)
        
        layer_events, layer_onsets = composer._process_layer(job['layer'], job['layer_idx'], 0.0, scaled_sec_dur, job['section'].get('ratio_temporale', 1.0), sec_env_num, job['section']['nome_sezione'])

        if not layer_events:
            generate_silent_wav(job['wav_path'], scaled_sec_dur)
        else:
            composer.generate_csd(job['name'], layer_events, job['csd_path'], job['wav_path'])
            proc_data = run_csound_process(job['csd_path'], job['name'], dirs['logs'])
            if proc_data: csound_procs.append(proc_data)
        
        absolute_onset = job['absolute_section_onset']
        # Creiamo una copia per non modificare la lista originale che potrebbe essere riutilizzata
        processed_events = [event.copy() for event in layer_events]
        for event in processed_events:
            event['time'] += absolute_onset
            plot_data['events'].append(event)
        
        adjusted_onsets = [onset + absolute_onset for onset in layer_onsets]
        plot_data['onsets_flat'].extend(adjusted_onsets)

        job_info = job.copy()
        job_info['adjusted_onsets'] = adjusted_onsets
        plot_data['render_jobs_info'].append(job_info)

    if csound_procs:
        print("\n   Attendendo il completamento del rendering dei layer...")
        for process, name, log_file in csound_procs:
            process.wait()
            log_file.close()
            if process.returncode != 0: print(f"   ✗ ERRORE: Rendering del layer '{name}' fallito!")
            else: print(f"   ✓ Rendering del layer '{name}' completato.")
            
    plot_data['composer'] = composer 
    
    # --- NUOVA LOGICA: SALVATAGGIO DELLA CACHE ---
    if not veteran_mode_active:
        cache_path = dirs['base'] / "visual_cache.json"
        print(f"\nModalità non-veteran: salvo i dati di visualizzazione in '{cache_path}'...")
        try:
            # Rimuoviamo l'oggetto composer che non è serializzabile
            data_to_save = plot_data.copy()
            data_to_save.pop('composer', None) 
            
            # Pulisci i dati da tipi non serializzabili
            sanitized_data = _sanitize_data_for_json(data_to_save)
            
            with open(cache_path, 'w') as f:
                json.dump(sanitized_data, f, indent=2)
            print("✓ Cache di visualizzazione salvata con successo.")
        except TypeError as e:
            print(f"✗ ERRORE: Impossibile salvare la cache di visualizzazione. Dati non serializzabili: {e}")
        except Exception as e:
            print(f"✗ ERRORE inaspettato durante il salvataggio della cache: {e}")
    # --- FINE NUOVA LOGICA ---

    return plot_data

def generate_composition_plot(plot_data, composition_structure, base_composition_name, output_dir,
                              veteran_mode_active,
                              partitura_mode=False, page_duration_s=60):
    """
    FASE 3: Gestisce la cache di visualizzazione (legge, unisce, scrive)
    e poi chiama il plotter vero e proprio.
    """
    print("\n--- FASE 3: Gestione Cache e Generazione Visualizzazione ---")
    
    cache_path = output_dir / "visual_cache.json"
    fresh_data = plot_data if plot_data else {} # Dati appena generati (potrebbero essere vuoti)

    # 1. Carica la cache esistente, se c'è. Altrimenti, parti da una struttura vuota.
    cached_data = {}
    if cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
            print(f"  ✓ Cache di visualizzazione caricata da '{cache_path}'.")
        except Exception as e:
            print(f"  ✗ ATTENZIONE: Impossibile caricare o leggere la cache ({e}). Verrà creata una nuova cache.")
    
    # 2. Esegui il Merge: Sostituisci i dati nella cache con i dati freschi.
    # Inizializza la struttura dati finale partendo da una copia della cache.
    import copy
    final_data = copy.deepcopy(cached_data)

    if fresh_data.get('render_jobs_info'):
        fresh_jobs_info = fresh_data.get('render_jobs_info', [])
        fresh_job_keys = set(
            (job['section']['nome_sezione'], job['layer_idx']) for job in fresh_jobs_info
        )
        print(f"  > Trovati {len(fresh_job_keys)} layer freschi da unire/aggiornare.")

        # Inizializza le chiavi se non esistono nella struttura dati finale (primo avvio)
        if 'events' not in final_data: final_data['events'] = []
        if 'render_jobs_info' not in final_data: final_data['render_jobs_info'] = []

        # Rimuovi i dati vecchi per i layer che stiamo aggiornando
        final_data['events'] = [
            e for e in final_data['events']
            if (e['params']['section_name'], e['params'].get('layer_idx_ref')) not in fresh_job_keys
        ]
        final_data['render_jobs_info'] = [
            j for j in final_data['render_jobs_info']
            if (j['section']['nome_sezione'], j['layer_idx']) not in fresh_job_keys
        ]
        
        # Aggiungi i dati freschi
        final_data['events'].extend(fresh_data.get('events', []))
        final_data['render_jobs_info'].extend(fresh_jobs_info)
        print("  ✓ Merge completato.")
    
    # 3. Se sono stati processati dati, procedi col plotting
    if not final_data or not final_data.get('events'):
        print("Nessun dato di visualizzazione disponibile. Plot saltato.")
        # Anche se non c'è nulla da plottare, potremmo voler salvare una cache vuota
        # per la coerenza, ma per ora lo saltiamo.
    else:
        # Assicuriamoci che l'oggetto 'composer' sia disponibile per il plotter
        final_data['composer'] = fresh_data.get('composer', GenerativeComposer())
        final_data['onsets_flat'] = [e['time'] for e in final_data['events']]

        # Allinea la struttura 'onsets_by_section' per il plotter
        onsets_by_section_aligned = []
        onsets_map = {}
        for job in final_data.get('render_jobs_info', []):
            key = (job['section']['nome_sezione'], job['layer_idx'])
            onsets_map[key] = job.get('adjusted_onsets', [])

        for section_yaml in composition_structure:
            section_data = {'section_name': section_yaml['nome_sezione'], 'layers': []}
            layers_in_yaml = section_yaml.get('layers', [])
            for layer_idx_yaml, layer_yaml in enumerate(layers_in_yaml):
                key = (section_yaml['nome_sezione'], layer_idx_yaml)
                onsets_for_this_layer = onsets_map.get(key, [])
                section_data['layers'].append({
                    'layer_name': layer_yaml.get('nome_layer', f'Layer {layer_idx_yaml+1}'),
                    'onsets': onsets_for_this_layer
                })
            onsets_by_section_aligned.append(section_data)

        # Chiamata al plotter con i dati finali
        debugger = CompositionDebugger(output_dir)
        plot_name = f"{base_composition_name}"
        plot_title = f"Visualizzazione Composizione: {base_composition_name}"
        
        final_data['events'].sort(key=lambda x: x['time'])

        debugger.plot_piano_roll(
            events=final_data['events'],
            all_onsets=final_data['onsets_flat'],
            composition_name=plot_name,
            composition_structure=composition_structure,
            composer=final_data['composer'],
            onsets_by_section=onsets_by_section_aligned,
            title=plot_title,
            partitura_mode=partitura_mode,
            page_duration_s=page_duration_s
        )

    # 4. Salva SEMPRE lo stato aggiornato nella cache, se abbiamo dei dati
    if final_data:
        print(f"  > Aggiornando la cache di visualizzazione in '{cache_path}'...")
        try:
            data_to_save = final_data.copy()
            data_to_save.pop('composer', None)
            
            sanitized_data = _sanitize_data_for_json(data_to_save)
            
            with open(cache_path, 'w') as f:
                json.dump(sanitized_data, f, indent=2)
            print("  ✓ Cache di visualizzazione aggiornata con successo.")
        except Exception as e:
            print(f"  ✗ ERRORE: Impossibile salvare la cache di visualizzazione aggiornata: {e}")

def execute_section_assembly(assembly_jobs, dirs):
    """
    FASE 4: Esegue l'assemblaggio parallelo delle sezioni.
    """
    if not assembly_jobs:
        print("\n--- FASE 4: Nessun assemblaggio di sezione richiesto. ---")
        return
        
    print("\n--- FASE 4: Esecuzione Assemblaggio delle Sezioni in Parallelo ---")
    csound_procs = []
    for job in assembly_jobs:
        generate_assembler_csd(job['csd_path'], job['output_wav'], job['input_layers'], title=f"Section Assembler: {job['name']}")
        proc_data = run_csound_process(job['csd_path'], job['name'], dirs['logs'])
        if proc_data: csound_procs.append(proc_data)
    
    if csound_procs:
        print("\n   Attendendo il completamento dell'assemblaggio delle sezioni...")
        for process, name, log_file in csound_procs:
            process.wait()
            log_file.close()
            if process.returncode != 0: print(f"   ✗ ERRORE: Assemblaggio della sezione '{name}' fallito!")
            else: print(f"   ✓ Assemblaggio della sezione '{name}' completato.")

def execute_final_assembly(final_parts, base_composition_name, dirs, open_after_render):
    """
    FASE 5: Esegue l'assemblaggio finale e apre il file risultante.
    """
    if not final_parts:
        print("\n--- FASE 5: Nessuna parte da assemblare. Processo terminato. ---")
        return

    print("\n--- FASE 5: Esecuzione Assemblaggio Finale ---")
    final_csd_path = dirs['base'] / "csd" / f"{base_composition_name}_final_assembler.csd"
    final_wav_path = dirs['base'] / "wav" / f"{base_composition_name}_complete.wav"

    unique_final_parts = {str(part['wav_path']): part for part in reversed(final_parts)}.values()
    
    generate_assembler_csd(final_csd_path, final_wav_path, [(p['wav_path'], p['onset']) for p in unique_final_parts], title="Final Composition Assembler")
    
    final_proc_data = run_csound_process(final_csd_path, f"{base_composition_name}_final", dirs['logs'])
    if final_proc_data:
        process, name, log_file = final_proc_data
        process.wait()
        log_file.close()
        if process.returncode == 0:
            print(f"\n✓✓✓ COMPOSIZIONE FINALE COMPLETATA: {final_wav_path} ✓✓✓")
            if open_after_render:
                print("Apertura del file audio completo...")
                try:
                    open_command = 'open' if sys.platform == 'darwin' else 'xdg-open' if sys.platform.startswith('linux') else 'start'
                    subprocess.run([open_command, str(final_wav_path)], check=True)
                except Exception as e:
                    print(f"ATTENZIONE: Impossibile aprire automaticamente il file audio: {e}")
        else:
             print(f"\n✗ ERRORE CRITICO durante l'assemblaggio finale. Controlla il log: {log_file.name}")

if __name__ == "__main__":
    RENDER_AUTOMATICAMENTE = True
    APRI_FILE_DOPO_RENDER = True
    MODALITA_PARTITURA_ASCOLTO = True 
    DURATA_PAGINA_S = 60

    if len(sys.argv) < 2:
        print("ERRORE: Devi specificare il percorso del file YAML della composizione.")
        sys.exit(1)

    # --- SETUP INIZIALE ---
    yaml_file_path = sys.argv[1]
    all_composition_structures = load_all_compositions_from_yaml(yaml_file_path)
    base_composition_name = Path(yaml_file_path).stem

    base_output_dir = Path("composizioni_generate")
    dirs = {
        'base': base_output_dir,
        'layers_wav': base_output_dir / "wav" / "layers",
        'sections_wav': base_output_dir / "wav" / "sections",
        'layers_csd': base_output_dir / "csd" / "layers",
        'sections_csd': base_output_dir / "csd" / "sections",
        'logs': base_output_dir / "logs"
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    veteran_mode_active = any(
        layer.get('veteranMode', False)
        for part in all_composition_structures
        for section in part
        for layer in section.get('layers', [])
    )
    if veteran_mode_active:
        print("\n" + "="*30 + " M O D A L I T À   V E T E R A N   A T T I V A " + "="*30)

    # --- ORCHESTRAZIONE DELLE FASI ---
    
    # FASE 1: Pianifica tutti i lavori
    layer_jobs, section_jobs, final_parts, plot_structure = plan_render_jobs(
        all_composition_structures, base_composition_name, dirs, veteran_mode_active
    )

    # FASE 2: Esegui il rendering e raccogli i dati per il plot
    plot_data = execute_layer_rendering_and_collect_data(
        render_jobs=layer_jobs, 
        dirs=dirs, 
        veteran_mode_active=veteran_mode_active
    )

    # FASE 3: Genera il grafico coerente con i dati del rendering
    generate_composition_plot(plot_data, plot_structure, base_composition_name, dirs['base'],veteran_mode_active,
                              partitura_mode=MODALITA_PARTITURA_ASCOLTO,
                              page_duration_s=DURATA_PAGINA_S)

    # FASE 4: Assembla le sezioni dai layer renderizzati
    execute_section_assembly(section_jobs, dirs)

    # FASE 5: Assembla la composizione finale dalle sezioni
    execute_final_assembly(final_parts, base_composition_name, dirs, APRI_FILE_DOPO_RENDER)