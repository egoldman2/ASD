set -eu
python3 - <<'PY'
import datetime,hashlib,json,os,pathlib,re,subprocess
args=['journalctl','--no-pager','_TRANSPORT=kernel','--since','2026-10-15 13:18:30 UTC','--until','2026-10-15 13:20:00 UTC','--output','json'];p=subprocess.run(args,capture_output=True,text=True,timeout=45);assert p.returncode==0
root=pathlib.Path('/srv/asd/recovery/release2-20261017T121611Z');assert root.is_dir();dest=root/'historical-oom-kernel-private.jsonl';dest.write_text(p.stdout);os.chmod(dest,0o600)
records=[json.loads(line) for line in p.stdout.splitlines() if line.strip()];messages=[x.get('MESSAGE','') for x in records];headers=[m for m in messages if 'total_vm' in m and 'rss' in m];tasks=[]
for m in messages:
 match=re.match(r'^\[\s*(\d+)\]\s+(.*)$',m)
 if not match:continue
 values=match.group(2).split()
 if len(values)>=7 and all(v.lstrip('-').isdigit() for v in values[:-1]):tasks.append({'pid':int(match.group(1)),'rss_field':int(values[3]),'native_row':m})
tasks.sort(key=lambda x:x['rss_field'],reverse=True)
selected=[m for m in messages if re.search(r'invoked oom|oom-kill|Out of memory|Mem-Info|free:|active_anon:|inactive_anon:',m)]
print(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'historical_window_utc':['2026-10-15T13:18:30Z','2026-10-15T13:20:00Z'],'native_journal_path':str(dest),'native_journal_sha256':hashlib.sha256(p.stdout.encode()).hexdigest(),'native_record_count':len(records),'task_header':headers,'largest_task_rows_by_native_rss_field':tasks[:15],'selected_memory_messages':selected[-20:],'page_size_bytes':os.sysconf('SC_PAGE_SIZE'),'limitations':['Historical process snapshot; the killed Gunicorn process is a victim and is not by itself proof of the root cause','Complete native kernel JSONL retained privately on encrypted data volume; no application log payloads collected']},indent=2))
PY
