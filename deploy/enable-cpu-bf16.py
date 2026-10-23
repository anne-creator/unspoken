"""Patch the pinned Decider engine to retain its checkpoint's BF16 CPU weights.

Upstream upcasts on all CPUs because Apple CPU BF16 was slower. Intel Sapphire
Rapids has native BF16/AMX; retaining BF16 halves the weight memory. The FP32
classification head and accumulation kernels are unchanged. This opt-in patch
fails on unexpected upstream source instead of silently patching another version.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1])
path = root / 'infer.py'
source = path.read_text()
before = '        if str(self.cfg.device) == "cpu":\n            self._upcast_torso_for_cpu()'
after = '        if str(self.cfg.device) == "cpu" and os.getenv("STRANDS_CPU_BF16") != "1":\n            self._upcast_torso_for_cpu()'
if after not in source:
    assert source.count(before) == 1, 'Unexpected engine source'
    source = source.replace('import copy\n', 'import copy\nimport os\n').replace(before, after)
    path.write_text(source)
print('CPU BF16 opt-in patch installed:', path)
