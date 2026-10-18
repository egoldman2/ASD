set -eu
python3 - <<'PY'
import datetime,json,subprocess,time
container='asd-cloud-customer-support-backend-1'
source="import resource,urllib.request; response=urllib.request.urlopen('http://127.0.0.1:6005/health',timeout=2); usage=resource.getrusage(resource.RUSAGE_SELF); print(__import__('json').dumps({'status':response.status,'cpu_seconds':usage.ru_utime+usage.ru_stime,'max_rss_kib':usage.ru_maxrss}))"
rows=[]
for skip_site in [False,True,True,False,False,True]:
 args=['docker','exec',container,'python']+(['-S'] if skip_site else [])+['-c',source];start=time.monotonic();r=subprocess.run(args,capture_output=True,text=True,timeout=35);row={'skip_site':skip_site,'wall_seconds':time.monotonic()-start,'exit_code':r.returncode}
 if r.returncode==0:row.update(json.loads(r.stdout))
 else:row['error_type']='probe failed; private stderr retained only in invocation'
 rows.append(row)
print(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'read_only':True,'service':'customer-support-backend','url':'http://127.0.0.1:6005/health','measurements':rows,'limits':['Six extra read-only localhost health requests; no container config or source changed','Process CPU/max RSS include Python startup; wall time includes docker exec and throttling','Single service sample; final clean main deployment and representative-load window remain required']},indent=2))
PY
