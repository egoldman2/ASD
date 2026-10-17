set -eu
python3 - <<'PY'
import datetime,json,pathlib,subprocess,os

def run(args,timeout=20):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout);assert p.returncode==0,(args[0],p.returncode);return p.stdout
mem={k:int(v.split()[0]) for k,v in (row.split(':',1) for row in pathlib.Path('/proc/meminfo').read_text().splitlines()) if k in ['MemTotal','MemAvailable','MemFree','Cached','Shmem','Slab','SReclaimable','SUnreclaim','KernelStack','PageTables','SwapTotal','SwapFree']}
processes=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  d={k:v.strip() for k,v in (line.split(':',1) for line in (p/'status').read_text().splitlines() if ':' in line)}
  if 'VmRSS' in d:processes.append({'pid':int(p.name),'name':d['Name'],'rss_kib':int(d['VmRSS'].split()[0]),'threads':int(d['Threads'])})
 except (OSError,KeyError,ValueError):continue
processes.sort(key=lambda x:x['rss_kib'],reverse=True)
ids=run(['docker','ps','-aq']).split();containers=[]
for x in json.loads(run(['docker','inspect',*ids])):
 state=x['State'];containers.append({'id':x['Id'],'service':(x['Config'].get('Labels') or {}).get('com.docker.compose.service'),'pid':state['Pid'],'status':state['Status'],'started_at':state['StartedAt'],'restart_count':x['RestartCount'],'oom_killed':state['OOMKilled']})
p= subprocess.run(['journalctl','--no-pager','-b','_TRANSPORT=kernel','--grep','Out of memory|oom-kill','--output','cat'],capture_output=True,text=True,timeout=20)
assert p.returncode in (0,1)
print(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'read_only':True,'uptime_seconds':float(pathlib.Path('/proc/uptime').read_text().split()[0]),'kernel':run(['uname','-r']).strip(),'docker_version':run(['docker','version','--format','{{json .Server.Version}}']).strip(),'containerd_version':run(['containerd','--version']).strip(),'memory_kib':mem,'largest_processes':processes[:30],'containers':containers,'current_boot_oom_message_count':len(p.stdout.splitlines()),'limitations':'Read-only observation of older manual release, no representative CRUD load, no proof of historic root cause or final stability'},indent=2))
PY
