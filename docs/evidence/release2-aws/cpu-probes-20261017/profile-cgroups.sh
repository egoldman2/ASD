set -eu
python3 - <<'PY'
import collections,datetime,json,pathlib,subprocess,time
ids=subprocess.check_output(['docker','ps','-aq'],text=True,timeout=15).split();items=[]
for x in json.loads(subprocess.check_output(['docker','inspect',*ids],text=True,timeout=15)):
 pid=x['State']['Pid'];cg=pathlib.Path('/proc')/str(pid)/'cgroup';relative=cg.read_text().strip().split(':',2)[2];stats=pathlib.Path('/sys/fs/cgroup')/relative.lstrip('/')/'cpu.stat';assert stats.is_file();items.append((x['Id'],(x['Config'].get('Labels') or {}).get('com.docker.compose.service'),stats))
def sample():return {cid:{k:int(v) for k,v in (line.split() for line in path.read_text().splitlines())} for cid,_,path in items}
start_at=datetime.datetime.now(datetime.timezone.utc);a=sample();start=time.monotonic();time.sleep(30);b=sample();elapsed=time.monotonic()-start;end_at=datetime.datetime.now(datetime.timezone.utc)
args=['docker','events','--since',start_at.isoformat(),'--until',end_at.isoformat(),'--filter','type=container','--format','{{json .}}'];p=subprocess.run(args,capture_output=True,text=True,timeout=15);assert not p.returncode;events=[json.loads(line) for line in p.stdout.splitlines()];counts=collections.Counter()
for x in events:
 if x.get('Action','').startswith('exec_'):counts[(x['Actor']['ID'],x['Action'].split(':',1)[0])]+=1
rows=[]
for cid,service,_ in items:
 rows.append({'service':service,'cpu_seconds':(b[cid]['usage_usec']-a[cid]['usage_usec'])/1e6,'user_cpu_seconds':(b[cid]['user_usec']-a[cid]['user_usec'])/1e6,'system_cpu_seconds':(b[cid]['system_usec']-a[cid]['system_usec'])/1e6,'exec_start_count':counts[(cid,'exec_start')],'exec_die_count':counts[(cid,'exec_die')]})
print(json.dumps({'captured_at':end_at.isoformat(),'window_start':start_at.isoformat(),'elapsed_seconds':elapsed,'read_only':True,'container_cpu_and_exec':rows,'limits':['Old manual release; observation only, no health settings changed','Container CPU includes healthcheck children and API requests; no per-command CPU attribution','Full event attributes/commands/identities excluded','No representative CRUD load or final resource-fix acceptance']},indent=2))
PY
