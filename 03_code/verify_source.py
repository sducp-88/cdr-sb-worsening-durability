"""Verify source integrity and documented portability edits without study data."""
from pathlib import Path
import ast,hashlib,json,re,sys
R=Path(__file__).resolve().parents[1]
checks=[]
def ck(label,ok):
    checks.append((label,bool(ok)))
    if not ok:print('FAIL:',label)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((R/'MANIFEST.json').read_text(encoding='utf8'))
for item in manifest['files']:
    file=R/item['path']
    ck('hash '+item['path'],file.is_file() and sha(file)==item['sha256'])
for item in json.loads((R/'CODE_PROVENANCE.json').read_text(encoding='utf8')):
    original=R/item['original'];portable=R/item['portable']
    ck('original script digest '+original.name,sha(original)==item['original_sha256'])
    ck('portable script digest '+portable.name,sha(portable)==item['portable_sha256'])
    expected=original.read_text(encoding='utf8')
    for n,change in enumerate(item['replacements']):
        ck(f'unique documented substitution {original.name}/{n}',expected.count(change['old'])==1)
        expected=expected.replace(change['old'],change['new'])
    actual=portable.read_text(encoding='utf8')
    ck('only documented changes '+portable.name,actual==expected)
    # Normalize the optional protocol fingerprint expression, which affects metadata only.
    normalized=actual.replace("result['protocol_sha256']=protocol_sha256()","result['protocol_sha256']=hashlib.sha256((ROOT/'02_protocol/SAP_v1_2026-09-17.md').read_bytes()).hexdigest()")
    def functions(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    ck('statistical function syntax retained '+portable.name,functions(original.read_text(encoding='utf8'))==functions(normalized))
for f in [*(R/'03_code').glob('*.py'),*(R/'original_code').glob('*.py')]:
    ast.parse(f.read_text(encoding='utf8'),filename=f.name)
    ck('Python syntax '+str(f.relative_to(R)),True)
for item in manifest['files']:
    name=item['path'];f=R/name
    ck('code/documentation extension '+name,f.suffix.lower() in ['.py','.md','.txt','.json','.cff'] or f.name in ['.gitignore','.gitattributes'])
    text=f.read_text(encoding='utf-8-sig')
    ck('no credential or participant identifier '+name,not re.search(r'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bNACC\d{4,}\b|\b\d{3}_S_\d{4,}\b',text))
summary={'passed':sum(ok for _,ok in checks),'total':len(checks),'scope':'Code/source integrity only; no participant data or unpublished study results accessed'}
print(json.dumps(summary,indent=2))
sys.exit(0 if all(ok for _,ok in checks) else 1)
