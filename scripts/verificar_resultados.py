"""Valida el notebook y las respuestas calculadas; no necesita los CSV originales."""
from pathlib import Path
import json
import nbformat

root = Path(__file__).resolve().parents[1]
nb = nbformat.read(root / 'Monitoreo_fraude.ipynb', as_version=4)
nbformat.validate(nb)
cells = [c for c in nb.cells if c.cell_type == 'code']
assert cells and all(c.execution_count is not None for c in cells)
assert not [o for c in cells for o in c.outputs if o.output_type == 'error']
a = json.loads((root / 'output/final/answers.json').read_text(encoding='utf8'))
assert a['months_with_performance_alerts'] == ['april_2019','may_2019','june_2019']
assert a['highest_correlation_feature'] == 'time_since_login_min'
assert abs(a['alert_avg_transaction_amount'] - 3069.8184) < 1e-8
assert a['ranking_scope'] == 'analysis'
print(f'OK: {len(cells)} celdas ejecutadas sin errores y respuestas verificadas.')
