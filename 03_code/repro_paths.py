"""Local-only input configuration; no data downloads or embedded study outputs."""
import os,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def required_path(name,is_file):
    value=os.environ.get(name)
    if not value:raise SystemExit(f"Set {name} to your approved local input path; study data are not supplied.")
    path=Path(value).expanduser().resolve()
    if not (path.is_file() if is_file else path.is_dir()):raise SystemExit(f"The configured {name} is not the expected file or directory.")
    return path
def nacc_file():return required_path('CDRSB_NACC_FILE',True)
def adni_root():return required_path('CDRSB_ADNI_ROOT',False)
def output_dir():
    p=Path(os.environ.get('CDRSB_OUTPUT_DIR',str(ROOT/'generated_results'))).resolve()
    p.mkdir(parents=True,exist_ok=True);return p
def results_dir():return Path(os.environ.get('CDRSB_RESULTS_DIR',os.environ.get('CDRSB_OUTPUT_DIR',str(ROOT/'generated_results')))).resolve()
def figures_dir():
    p=Path(os.environ.get('CDRSB_FIGURES_DIR',str(ROOT/'generated_figures'))).resolve()
    p.mkdir(parents=True,exist_ok=True);return p
def baseline_results_file():
    return required_path('CDRSB_BASELINE_RESULTS',True) if os.environ.get('CDRSB_BASELINE_RESULTS') else None
def protocol_sha256():
    if not os.environ.get('CDRSB_PROTOCOL_FILE'):return None
    return hashlib.sha256(required_path('CDRSB_PROTOCOL_FILE',True).read_bytes()).hexdigest()
