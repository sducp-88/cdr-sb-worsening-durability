# Portable code changes

The three files in `original_code/` are byte-identical to the original local scripts. The corresponding `03_code/` entry points make the following packaging changes:

1. Read approved data paths from environment variables instead of fixed local drive paths.
2. Write generated results and figures into ignored directories. Read plotting/checking inputs from a configurable local results directory.
3. Record an optional local protocol-file digest; record null if the private file is not supplied. The complete protocol is not redistributed.
4. Run the two historical v1/v2 comparison checks only when the optional private baseline JSON is supplied. Record whether this comparison was included.

`CODE_PROVENANCE.json` contains exact text substitutions and original/portable script hashes. `verify_source.py` reconstructs each portable file from the original substitutions and checks source equality. Named functions retain identical syntax trees except for the protocol-digest expression in the analysis entry point; that metadata-only change is normalized before comparison.

No threshold, selection rule, outcome definition, estimator, model formula, random seed or figure geometry was changed for this release. No study result values are included in the documentation or the source verifier. Numerical-code execution and statistical reproduction require approved local inputs; successful source validation alone does not establish reproduced study results.
