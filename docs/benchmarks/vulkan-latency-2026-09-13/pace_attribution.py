import json,subprocess,hashlib
from pathlib import Path
rows=[]
for sequence in (1,32):
 for period in (0,33333):
  for variant in ('lookup-direct','lookup-fused-direct'):
   cmd=['build-perf10/bench_vulkan_scale','build-perf10/vulkan_separable.spv','0','2','gpu','build/decision-review/clips/live-action-540.yuv',variant,'build-perf10/vulkan_usm.spv','1',str(period),'12',str(sequence)]
   r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
   rows.append(dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,measurements=[json.loads(line) for line in r.stdout.splitlines() if line.startswith('{')]))
   print(sequence,period,variant,r.returncode,rows[-1]['measurements'][-1:],flush=True)
   if r.returncode:raise SystemExit(r.returncode)
Path('build/decision-review/direct-vulkan/pace-attribution.json').write_text(json.dumps(rows,indent=2)+'\n')
