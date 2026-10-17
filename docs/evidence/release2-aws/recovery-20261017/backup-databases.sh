set -eu
python3 - <<'PY'
from contextlib import closing
import datetime,hashlib,hmac,json,os,pathlib,shutil,sqlite3,stat,subprocess,urllib.parse
mount=json.loads(subprocess.check_output(['findmnt','--json','--target','/srv/asd'],text=True))['filesystems'][0]
assert mount['target']=='/srv/asd' and mount['fstype']=='ext4'
serial=subprocess.check_output(['lsblk','-n','-o','SERIAL',mount['source']],text=True).strip();assert serial.replace('-','')=='vol02087b3eeb07eec99'
files=[pathlib.Path('/srv/asd/data')/p for p in ['accounts/users.db','products/products.db','orders/orders.db','support/support_tickets.db']]
assert all(p.is_file() and p.resolve().is_relative_to(pathlib.Path('/srv/asd/data')) for p in files)
assert shutil.disk_usage('/srv/asd').free>sum(p.stat().st_size for p in files)*2+128*1024*1024
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');directory=pathlib.Path('/srv/asd/recovery')/('release2-'+stamp);directory.mkdir(mode=0o700,parents=True,exist_ok=False);os.chmod(directory.parent,0o700)
record={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'backup_directory':str(directory),'data_volume_serial':serial,'mount_source':mount['source'],'read_only_sources':True,'current_release':os.path.realpath('/srv/asd/current'),'databases':[]}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for source in files:
 target=directory/(source.parent.name+'-'+source.name);before=digest(source)
 with closing(sqlite3.connect('file:'+urllib.parse.quote(str(source))+'?mode=ro',uri=True,timeout=30)) as original,closing(sqlite3.connect(target)) as backup:original.backup(backup,pages=64,sleep=0.05)
 os.chmod(target,0o600)
 with closing(sqlite3.connect('file:'+urllib.parse.quote(str(target))+'?mode=ro',uri=True)) as backup:
  integrity=[row[0] for row in backup.execute('PRAGMA integrity_check')];foreign_keys=list(backup.execute('PRAGMA foreign_key_check'));tables=[row[0] for row in backup.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")];counts={table:backup.execute('SELECT COUNT(*) FROM "'+table.replace('"','""')+'"').fetchone()[0] for table in tables}
  assert integrity==['ok'],source.name+' failed physical integrity check'
 record['databases'].append({'source':str(source),'backup':str(target),'backup_bytes':target.stat().st_size,'backup_sha256':digest(target),'integrity_check':integrity,'foreign_key_violation_count':len(foreign_keys),'table_counts':counts,'source_main_file_bytes_unchanged_during_backup':before==digest(source)})
secret=pathlib.Path('/srv/asd/session-secret');target=directory/'session-secret';assert secret.is_file() and stat.S_IMODE(secret.stat().st_mode)==0o600;shutil.copyfile(secret,target);os.chmod(target,0o600);assert hmac.compare_digest(secret.read_bytes(),target.read_bytes());record['session_secret_backup']={'copied_privately_on_encrypted_data_volume':True,'bytes_equal':True,'mode':'0o600','content_and_fingerprint_excluded':True}
manifest=directory/'manifest.json';manifest.write_text(json.dumps(record,indent=2)+'\n');os.chmod(manifest,0o600);print(json.dumps(record,indent=2))
PY
