# CDR-SB worsening durability: analysis code

Code for **Durability of Meaningful CDR-SB Worsening in Early Cognitive Impairment**.

This is a code-only deposit. It includes the original analysis scripts, portable entry points, software dependencies, code provenance and instructions. Participant-level data, study result files, tables, figures, the full analysis plan, manuscript drafts and reference collections are not distributed in this repository. This software release does not imply journal acceptance or publication.

## Files

| File | Purpose |
|---|---|
| `03_code/02_analysis.py` | Cohort harmonization and final analysis pipeline |
| `03_code/04_verify_numeric.py` | Separate NACC reconstruction and numerical/coding checks using local inputs |
| `03_code/06_figures.py` | Figure generation from locally generated aggregate results |
| `03_code/repro_paths.py` | Input and output path configuration |
| `03_code/verify_source.py` | Standard-library checks of code integrity and documented changes |
| `original_code/` | Byte-preserved scripts from the original analysis, including original local path settings |
| `CODE_PROVENANCE.json` | Exact substitutions from original to portable scripts and their hashes |

Use the portable scripts under `03_code/`. The archival copies document the executed source and are not the recommended entry points on another computer.

## Installation

Python 3.12 is recommended. The analysis records Python 3.12.14, pandas 3.0.5 and numpy 2.5.1. Other dependency pins were read from the local analysis environment during release preparation; they were not recorded as a complete original-time environment lock.

```text
python -m venv .venv
```

Activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` on POSIX. Then run:

```text
python -m pip install -r requirements.txt
python 03_code/verify_source.py
```

The source check uses only the Python standard library and can also run before installing dependencies. It does not access participant data or verify unpublished study estimates.

## Authorized local inputs

Investigators must obtain their own approved data access from [NACC](https://www.naccdata.org/requesting-data/data-request-process/) and [ADNI](https://adni.loni.usc.edu/data-samples/adni-data/), following the applicable data-use agreements. The scripts do not download data. Keep inputs outside the Git checkout and outside public CI or external AI services.

Configure these paths, using your own approved locations. PowerShell example:

```powershell
$env:CDRSB_NACC_FILE = 'D:/private/NACC/investigator_nacc74.csv'
$env:CDRSB_ADNI_ROOT = 'D:/private/ADNI'
python 03_code/02_analysis.py
python 03_code/04_verify_numeric.py
python 03_code/06_figures.py
```

For POSIX, set `export CDRSB_NACC_FILE=/private/NACC/investigator_nacc74.csv` and `export CDRSB_ADNI_ROOT=/private/ADNI`, then run the same Python commands.

The ADNI input directory is expected to contain the originally used file names and hierarchy:

```text
03_clinical_outcomes/neuropsychological/CDR_30Aug2026.csv
03_clinical_outcomes/neuropsychological/FAQ_30Aug2026.csv
01_core_cohort/diagnosis/DXSUM_30Aug2026.csv
01_core_cohort/demographics/PTDEMOG_30Aug2026.csv
04_imaging_derived/pet/UCBERKELEY_AMY_6MM_30Aug2026.csv
```

The scripts expect the corresponding source schemas. Different approved releases may need explicit harmonization and may produce different results. No source files are bundled.

## Outputs and optional local provenance

Analysis outputs default to `generated_results/`; figures default to `generated_figures/`. Both directories are ignored by Git. The plotting script requires the locally generated `analysis_results_v2.json`. It exports PDF, SVG, PNG and TIFF figures. Arial was used locally; font substitutions can change layout.

| Environment variable | Purpose |
|---|---|
| `CDRSB_OUTPUT_DIR` | Override the analysis/numerical-check output directory |
| `CDRSB_RESULTS_DIR` | Override the result directory read by the numerical checker and plotting script; defaults to the analysis output directory |
| `CDRSB_FIGURES_DIR` | Override the generated-figure directory |
| `CDRSB_PROTOCOL_FILE` | Optional local protocol file whose SHA-256 is recorded in newly generated result metadata; null when not supplied |
| `CDRSB_BASELINE_RESULTS` | Optional local earlier result JSON used only for implementation-correction comparisons |

The earlier v1 result and full protocol are not distributed. If the optional earlier result file is absent, the two historical comparison checks are omitted and the numerical-QA report explicitly records `baseline_comparison_included: false`. Cohort reconstruction, coding and other numerical checks still run. The optional protocol fingerprint affects metadata only, not statistical calculations.

## Attribution and assistance

Authors: Peng Cheng, Suqin Jin, Fan Li, Lixin Luan, Yunfei Cui and Wenwen Ma. See `CITATION.cff` for software citation metadata. The source analyzes NACC and ADNI data; their data-generating investigators are not represented as authors of this analysis code. Investigators using either cohort remain responsible for its attribution and data-use requirements.

OpenAI Codex assisted with code drafting, debugging and packaging. The authors reviewed the code and retain responsibility for the study and its content. The code deposit grants no access to, or redistribution rights for, NACC or ADNI participant data.

See `CODE_CHANGES.md` for the limited portability changes. Original statistical definitions and computations are retained. This deposit is not a public preregistration.
