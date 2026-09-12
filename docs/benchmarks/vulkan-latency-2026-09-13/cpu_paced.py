import json,subprocess
from pathlib import Path
rows=[]
for factor in (2,4):
 for pair in range(3):
  order=(4,8,12,16) if pair%2==0 else (16,12,8,4)
  for workers in order:
   cmd=['build-perf10/bench_vulkan_scale','build-perf10/vulkan_separable.spv','0',str(factor),'cpu','build/decision-review/clips/live-action-540.yuv','separable','build-perf10/vulkan_usm.spv','0','33333',str(workers),'32']
   r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
   rows.append(dict(command=cmd,pair=pair,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,measurements=[json.loads(line) for line in r.stdout.splitlines() if line.startswith('{')]))
   Path('build/decision-review/direct-vulkan/cpu-paced-workers.json').write_text(json.dumps(rows,indent=2)+'\n')
   print(factor,pair,workers,r.returncode,rows[-1]['measurements'][-1:],flush=True)
   if r.returncode:raise SystemExit(r.returncode)
