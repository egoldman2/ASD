set -eu
python3 - <<'PY'
import datetime,json,os,pathlib,shutil,stat,subprocess

def run(args,timeout=35):
 r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 return r.returncode,r.stdout
r={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'read_only':True,'current_release':os.path.realpath('/srv/asd/current')}
current=pathlib.Path(r['current_release']);meta=current/'source-metadata.json'
if meta.is_file():
 d=json.loads(meta.read_text());r['source_metadata']={k:d.get(k) for k in ['source_sha','source_ref','release_id','created_at']}
secret=pathlib.Path('/srv/asd/session-secret');r['session_secret']={'exists':secret.is_file()}
if secret.is_file():
 s=secret.stat();r['session_secret'].update(mode=oct(stat.S_IMODE(s.st_mode)),size=s.st_size,modified_at=datetime.datetime.fromtimestamp(s.st_mtime,datetime.timezone.utc).isoformat())
code,out=run(['findmnt','--json','--target','/srv/asd']);r['mount']=json.loads(out) if not code else {'exit_code':code}
code,out=run(['lsblk','--json','--output','NAME,SIZE,FSTYPE,MOUNTPOINTS,SERIAL']);r['block_devices']=json.loads(out) if not code else {'exit_code':code}
r['memory_kib']={line.split(':')[0]:int(line.split()[1]) for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.split(':')[0] in ['MemTotal','MemAvailable','SwapTotal','SwapFree']};r['uptime_seconds']=float(pathlib.Path('/proc/uptime').read_text().split()[0]);r['data_disk_bytes']=dict(zip(['total','used','free'],shutil.disk_usage('/srv/asd')))
code,out=run(['docker','ps','-aq']);ids=out.split() if not code else []
containers=[]
if ids:
 code,out=run(['docker','inspect',*ids]);assert code==0
 for x in json.loads(out):
  env=dict(v.split('=',1) for v in x['Config'].get('Env',[]) if '=' in v);state=x['State'];labels=x['Config'].get('Labels') or {};containers.append({'name':x['Name'].lstrip('/'),'service':labels.get('com.docker.compose.service'),'image':x['Config']['Image'],'status':state['Status'],'health':state.get('Health',{}).get('Status'),'oom_killed':state.get('OOMKilled'),'restart_count':x.get('RestartCount'),'memory_limit':x.get('HostConfig',{}).get('Memory'),'ai_flags':{k:env[k] for k in ['AI_MODE_ENABLED','MCP_ENABLED','RAG_ENABLED','MULTI_AGENT_ENABLED'] if k in env}})
r['containers']=containers
code,out=run(['docker','stats','--no-stream','--format','{{json .}}']);r['container_stats']=[{k:x.get(k) for k in ['Name','CPUPerc','MemPerc','MemUsage','PIDs']} for x in [json.loads(line) for line in out.splitlines()]] if not code else {'exit_code':code}
r['database_files']=[{'path':str(p),'bytes':p.stat().st_size} for p in pathlib.Path('/srv/asd/data').glob('*/*.db') if p.is_file()]
code,out=run(['journalctl','--no-pager','_TRANSPORT=kernel','--since','2026-10-15 00:00:00 UTC','--grep','Out of memory|Killed process|oom-kill|oom_reaper|Memory cgroup out of memory']);r['kernel_memory_events']={'command_exit_code':code,'lines':out.splitlines()[-60:],'limitations':'Available journal history only; no matching line is not proof that an earlier OOM never occurred'}
print(json.dumps(r,indent=2))
PY
