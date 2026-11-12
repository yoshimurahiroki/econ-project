# Julia fixed effects and IV environment

The full project owns this profile, its Julia Manifest and the `julia` environment in `pixi.lock`. Julia 1.12.7 uses the CHOLMOD 5 interface supplied by the selected conda libraries. The profile supplies FixedEffectModels 2.2.0 and the CSV, Arrow and Parquet readers used by the existing causal runner. Run the commands from the repository root.

1. **Pinned files → installed environment.** Restore the selected interpreter and Julia packages. The project-local depot stays under the existing ignored `.pixi` directory.

   ```sh
   pixi install --environment julia --locked
   JULIA_DEPOT_PATH="$PWD/.pixi/julia-depot" JULIA_LOAD_PATH="@:@stdlib" \
     pixi run --environment julia --locked julia --startup-file=no \
       --project=profiles/julia -e 'using Pkg; Pkg.instantiate()'
   ```

2. **Installed profile → adopted stage.** Print this runtime fragment, then merge its input files and environment into the existing research stage. For a Julia stage, use the exact `probe_argv` as its `argv` prefix, followed by the adopted program and arguments. For a Python stage calling `fixed_effects_julia`, place the fragment's runtime in `runtime.companions`; the existing runner supplies `ERS_JULIA_ARGV`. Absolute executable/project/depot paths carry the selected environment into the runner's generation directory.

   ```sh
   python - <<'PY'
   import json
   import os
   from pathlib import Path
   import subprocess
   import tomllib

   root = Path.cwd().resolve()
   project = root / "profiles/julia"
   julia = root / ".pixi/envs/julia/bin/julia"
   stdlib = subprocess.check_output(
       [str(julia), "--startup-file=no", "-e", "print(Sys.STDLIB)"], text=True)
   requested = tomllib.loads((project / "Project.toml").read_text())["deps"]
   manifest = tomllib.loads((project / "Manifest.toml").read_text())
   files = ["pyproject.toml", "pixi.lock", "profiles/julia/Project.toml",
            "profiles/julia/Manifest.toml"]
   print(json.dumps({
       "inputs": files,
       "env": {"JULIA_DEPOT_PATH": str(root / ".pixi/julia-depot"),
               "JULIA_LOAD_PATH": os.pathsep.join([str(project), stdlib])},
       "runtime": {
           "language": "julia",
           "probe_argv": [str(julia),
                          "--startup-file=no", "--project=" + str(project)],
           "version": "1.12.7",
           "packages": {name: manifest["deps"][name][0]["version"]
                        for name in requested},
           "files": files
       }
   }, indent=2))
   PY
   ```

3. **Scientific execution → saved result.** Run the adopted stage through `harness/research.py`. Preserve its sample, weights, fixed effects, covariance, demeaning tolerance and saved native fit. The runner captures the actual interpreter, package closure and project-file hashes; the result consumer receives the adopted estimates and inference. A profile update regenerates its locks and verifies the affected scientific outputs through the same producer.
