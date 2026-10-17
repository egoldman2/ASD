set -eu
python3 - <<'PY'
import ast,datetime,json,os,pathlib,subprocess,time

def snapshot():
 procs={}
 for p in pathlib.Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   raw=(p/'stat').read_text();comm=raw[raw.index('(')+1:raw.rindex(')')];fields=raw[raw.rindex(')')+2:].split();procs[int(p.name)]={'name':comm,'ticks':int(fields[11])+int(fields[12]),'start':fields[19]}
  except (OSError,ValueError,IndexError):continue
 return procs,list(map(int,pathlib.Path('/proc/stat').read_text().splitlines()[0].split()[1:]))
a,cpu_a=snapshot();start=time.monotonic();time.sleep(15);b,cpu_b=snapshot();elapsed=time.monotonic()-start;hz=os.sysconf('SC_CLK_TCK');processes=[]
for pid,x in b.items():
 if pid in a and a[pid]['start']==x['start']:
  delta=x['ticks']-a[pid]['ticks']
  if delta:processes.append({'pid':pid,'name':x['name'],'cpu_seconds':delta/hz,'percent_of_one_cpu':round(delta/hz/elapsed*100,2)})
processes.sort(key=lambda x:x['cpu_seconds'],reverse=True)
ids=subprocess.check_output(['docker','ps','-aq'],text=True,timeout=15).split();containers=[]
for x in json.loads(subprocess.check_output(['docker','inspect',*ids],text=True,timeout=15)):
 test=x['Config'].get('Healthcheck',{}).get('Test',[]);safe_test=test if all(not any(k in v.lower() for k in ['password','secret','token','authorization']) for v in test) else '[omitted]'
 containers.append({'service':(x['Config'].get('Labels') or {}).get('com.docker.compose.service'),'pid':x['State']['Pid'],'health_interval_ns':x['Config'].get('Healthcheck',{}).get('Interval'),'health_test':safe_test})
current=pathlib.Path('/srv/asd/current').resolve();functions=[]
for relative in ['student-Ethan Ting/backend/app.py','student-Ethan Ting/database/app.py']:
 p=current/relative
 if not p.is_file():continue
 tree=ast.parse(p.read_text());selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['health','ready']]
 functions.extend({'path':relative,'function':n.name,'source':ast.unparse(n)} for n in selected)
delta=[y-x for x,y in zip(cpu_a,cpu_b)]
print(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed_seconds':elapsed,'process_ticks_per_second':hz,'cpu_delta_ticks':delta,'largest_persistent_process_cpu':processes[:20],'containers':containers,'actual_health_function_sources':functions,'limits':['Read-only 15-second sample on older manual release','Exited short-lived processes are excluded from persistent process list','No representative CRUD load or final stability result']},indent=2))
PY
