# Run from the repository root: make -f scripts/ai.mk ai-check
PYTHON ?= python3
.PHONY: ai-check ai-budget ai-bridge ai-project
ai-check:
	$(PYTHON) scripts/sync_rules.py
	$(PYTHON) -m unittest discover -s tests -p 'test_research_config.py' -v
ai-budget:
	$(PYTHON) scripts/ai_tools.py budget
ai-bridge:
	@test -n "$(OUTPUT)" || { echo "Set OUTPUT to a new directory outside the repository" >&2; exit 2; }
	$(PYTHON) scripts/ai_tools.py export --profile bridge --output "$(OUTPUT)"
ai-project:
	@test -n "$(OUTPUT)" || { echo "Set OUTPUT to a new directory outside the repository" >&2; exit 2; }
	$(PYTHON) scripts/ai_tools.py export --output "$(OUTPUT)"
