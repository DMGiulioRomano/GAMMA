# =============================================================================
# Makefile per il Generatore di Gamma di Comportamenti
# =============================================================================
# Questo Makefile automatizza la generazione e il rendering dei comportamenti.
#
# Comandi principali:
#   make all        - (Default) Genera i CSD e poi lancia il rendering.
#   make generate   - Genera solo i file CSD e gli script, senza renderizzare.
#   make render     - Lancia solo il rendering (presuppone che i CSD esistano).
#   make clean      - Rimuove tutti i file generati (csd, wav, script, csv).
# =============================================================================

# --- Variabili Configurabili ---
# Puoi cambiare l'interprete Python qui se necessario
PYTHON = python3.11

# Nomi degli script e delle cartelle
PYTHON_SCRIPT = generative_composerYaml2.py
OUT_DIR = composizioni_generate
CSD_DIR = $(OUT_DIR)/csd
WAV_DIR = $(OUT_DIR)/wav
LOG_DIR = $(OUT_DIR)/logs
YAML_DIR = yaml
YAML ?= Gamma
# --- Definizione dei Target ---
all: py

py:
	$(PYTHON) $(PYTHON_SCRIPT) $(YAML_DIR)/$(YAML).yaml


clean:
	@echo "--- Pulizia delle cartelle csd/ e wav/ e dei file generati... ---"
	rm -rf $(OUT_DIR) sco
	@echo "Pulizia completata."


.PHONY: all py clean

