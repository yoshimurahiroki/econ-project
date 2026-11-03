#!/usr/bin/env python3
"""Prepare a reproducible synthetic Python and R research example."""
import argparse
import hashlib
import html
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

DEFAULT_CASE_ID = 'independent019'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_files():
    """Find the installed canonical tree or flat resource siblings."""
    script = Path(__file__).resolve()
    base = script.parent
    if (base / 'research_estimator.py').is_file():
        checks = next((base / n for n in ('local_checks.py', 'LOCAL_CHECKS.py') if (base / n).is_file()), base / 'local_checks.py')
        files = {'research_case.py': script, 'research.py': base / 'research_estimator.py',
                 'requirements-research.txt': base / 'requirements-research.txt',
                 'runner.py': base / 'research.py', 'state.py': base / 'state.py', 'local_checks.py': checks}
    else:
        files = None
        for root in script.parents:
            scientific, runner = root / 'skills/econ-data/scripts/research.py', root / 'harness/research.py'
            if scientific.is_file() and runner.is_file():
                files = {'research_case.py': script, 'research.py': scientific,
                         'requirements-research.txt': scientific.with_name('requirements-research.txt'),
                         'runner.py': runner, 'state.py': runner.with_name('state.py'),
                         'local_checks.py': runner.with_name('local_checks.py')}
                break
        if files is None:
            checks = next((base / n for n in ('local_checks.py', 'LOCAL_CHECKS.py') if (base / n).is_file()), base / 'local_checks.py')
            files = {'research_case.py': script, 'research.py': base / 'research.py',
                     'requirements-research.txt': base / 'requirements-research.txt',
                     'runner.py': base / 'runner.py', 'state.py': base / 'state.py', 'local_checks.py': checks}
    if not all(p.is_file() for p in files.values()):
        raise ValueError('The case, estimator, runner, state, local checks and requirements must be present together')
    return files


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def case_path(root, case_id):
    if not case_id or not all(c.isascii() and (c.isalnum() or c in '-_') for c in case_id):
        raise ValueError('case-id must contain only ASCII letters, digits, hyphens and underscores')
    return Path(root).resolve() / '.agents' / 'state' / case_id


def executable(value):
    path = shutil.which(value)
    if not path:
        raise ValueError(f'Executable not found: {value}')
    return str(Path(path).absolute())


def prepare(root, python, rscript, source_dirs, case_id):
    case = case_path(root, case_id)
    if case.exists():
        raise ValueError(f'Case already exists: {case}; preserve it and select another --case-id')
    python, rscript = executable(python), executable(rscript)
    args = [python, str(Path(__file__).resolve()), '_prepare', '--root', str(Path(root).resolve()),
            '--python', python, '--rscript', rscript, '--case-id', case_id]
    for directory in source_dirs:
        args += ['--source-record-dir', str(Path(directory).resolve())]
    subprocess.run(args, check=True)


def materialize(root, python, rscript, source_dirs, case_id):
    import numpy as np
    import pandas as pd

    selected, names = [], set()
    for directory in map(Path, source_dirs):
        name = directory.name
        if not name or not all(c.isalnum() or c in '-_' for c in name) or name in names:
            raise ValueError('Source record directory names must be unique simple names')
        names.add(name)
        record = directory / 'source_record.json'
        metadata = json.loads(record.read_text())
        raw = directory / Path(metadata['response']['raw_path']).name
        if sha(raw) != metadata['response']['raw_sha256']:
            raise ValueError(f'{name} source bytes do not match their recorded hash')
        selected.append((name, record, raw))
    case = case_path(root, case_id)
    case.mkdir(parents=True, exist_ok=False)
    code = case / 'code'
    code.mkdir()
    originals = source_files()
    for name, source in originals.items():
        shutil.copyfile(source, code / name)
    rng = np.random.default_rng(19019)
    n = 1200
    z, x, u, v, e = (rng.normal(size=n) for _ in range(5))
    treatment = .8*z + .5*x + .9*u + v
    outcome = 1.5*treatment + .7*x + u + e
    frame = pd.DataFrame({'id': np.arange(1, n + 1), 'instrument': z, 'control': x,
                          'treatment': treatment, 'outcome': outcome})
    frame.to_csv(case / 'synthetic-raw.csv', index=False)
    (code / 'preprocess.R').write_text('''args <- commandArgs(trailingOnly = TRUE)
d <- utils::read.csv(args[1])
d$control_centered <- d$control - mean(d$control)
utils::write.csv(d, args[2], row.names = FALSE)
s <- data.frame(observations = nrow(d), treatment_mean = mean(d$treatment),
                outcome_mean = mean(d$outcome), treatment_sd = stats::sd(d$treatment))
utils::write.csv(s, args[3], row.names = FALSE)
''', encoding='utf-8')
    requirements = dict(line.split('==') for line in (code / 'requirements-research.txt').read_text().splitlines() if line and not line.startswith('#'))
    versions = {name: importlib.metadata.version(name) for name in requirements}
    if versions != requirements:
        raise ValueError('Installed packages do not match requirements-research.txt')
    versions['packaging'] = importlib.metadata.version('packaging')
    r_version = subprocess.check_output([rscript, '-e', 'cat(as.character(getRversion()), as.character(packageVersion("stats")), as.character(packageVersion("utils")), sep="\\n")'], text=True).splitlines()
    environment = {'python': sys.version.split()[0], 'python_packages': versions,
                   'r': r_version[0], 'r_packages': dict(zip(('stats', 'utils'), r_version[1:])),
                   'invoked_python': python, 'invoked_rscript': rscript,
                   'requirements_sha256': sha(code / 'requirements-research.txt')}
    write_json(case / 'environment.json', environment)
    source_records = []
    for name, record, raw in selected:
        record_target, raw_target = case / f'{name}-source-record.json', case / f'{name}-source-raw{raw.suffix}'
        shutil.copyfile(record, record_target)
        shutil.copyfile(raw, raw_target)
        source_records += [record_target.name, raw_target.name]
    write_json(case / 'source.json', {
        'kind': 'independently authored synthetic simulation', 'seed': 19019, 'rows': n,
        'dgp': 'z, x, u, v, e independently standard normal; treatment = 0.8*z + 0.5*x + 0.9*u + v; outcome = 1.5*treatment + 0.7*x + u + e',
        'true_treatment_coefficient': 1.5, 'raw_sha256': sha(case / 'synthetic-raw.csv'),
        'code_sha256': {name: sha(source) for name, source in originals.items()},
        'source_records': {name: sha(case / name) for name in source_records}})
    (case / 'figure-label.txt').write_text('Synthetic treatment coefficients and one standard error\n', encoding='utf-8')
    (case / 'paper-template.qmd').write_text('''# A synthetic instrumental-variable example

The simulation generates {{stat:observations}} observations with a true treatment coefficient of 1.5. The instrument and control are independent standard normal draws. Treatment combines the instrument, the control and an unobserved factor; the same unobserved factor enters the outcome, making treatment endogenous. The saved source metadata records the generating equations and seed. R centers the control and summarizes the generated data; the Python estimators use the same rows.

The OLS treatment coefficient is {{stat:ols}} (robust standard error {{stat:ols_se}}), and the IV coefficient is {{stat:iv}} (robust standard error {{stat:iv_se}}). The excluded-instrument first-stage Wald F statistic is {{stat:first_f}}. These are simulated results in outcome units per treatment unit.
''', encoding='utf-8')
    make_manifest(case, case_id, python, rscript, environment)
    relative = f'.agents/state/{case_id}'
    (case / 'README.txt').write_text('Prepared synthetic Python and R case. Run from the project root:\n'
        f'{python} {relative}/code/runner.py --root . {relative}/manifest.json\n'
        'Add --parent TASK_ID to inherit an existing task context, scope and holds.\n', encoding='utf-8')
    print(json.dumps({'case': str(case), 'source': sha(case / 'synthetic-raw.csv'), 'environment': environment}, indent=2))


def make_manifest(case, case_id, python, rscript, environment):
    p = f'.agents/state/{case_id}/'
    helper = '{root}/' + p + 'code/research_case.py'
    scientific = '{root}/' + p + 'code/research.py'
    lock = p + 'code/requirements-research.txt'
    sources = [p + 'environment.json', lock]
    source_records = [p + name for name in json.loads((case / 'source.json').read_text())['source_records']]
    env = {'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'}
    py_runtime = {'language': 'python', 'probe_argv': [python], 'version': environment['python'],
                  'packages': environment['python_packages'], 'files': [lock]}
    r_runtime = {'language': 'r', 'probe_argv': [rscript], 'version': environment['r'],
                 'packages': environment['r_packages'], 'files': [p+'code/preprocess.R']}
    stages = [{'id': 'preprocess', 'inputs': [p+'synthetic-raw.csv', p+'source.json', p+'code/preprocess.R', *source_records],
               'depends': {}, 'outputs': {'data': 'prepared.csv', 'summary': 'r-summary.csv'},
               'argv': [rscript, '{root}/'+p+'code/preprocess.R', '{root}/'+p+'synthetic-raw.csv', '{out:data}', '{out:summary}'],
               'runtime': r_runtime, 'env': env},
              {'id': 'specs', 'inputs': [p+'code/research_case.py', *sources], 'depends': {'preprocess': ['data']},
               'outputs': {'ols': 'ols.json', 'iv': 'iv.json'},
               'argv': [python, helper, 'specs', '{dep:preprocess:data}', '{out:ols}', '{out:iv}'], 'runtime': py_runtime, 'env': env}]
    for model in ('ols', 'iv'):
        stages.append({'id': model, 'inputs': [p+'code/research.py', p+'source.json', *source_records, *sources],
                       'depends': {'preprocess': ['data'], 'specs': [model]}, 'outputs': {'result': 'result.json'},
                       'argv': [python, scientific, 'estimate', '{dep:specs:'+model+'}', '-o', '{out:result}'],
                       'runtime': py_runtime, 'env': env})
    stages.append({'id': 'summary', 'inputs': [p+'code/research_case.py', *sources],
                   'depends': {'ols': ['result'], 'iv': ['result'], 'preprocess': ['summary']}, 'outputs': {'summary': 'summary.json'},
                   'argv': [python, helper, 'summary', '{dep:ols:result}', '{dep:iv:result}', '{dep:preprocess:summary}', '{out:summary}'],
                   'runtime': py_runtime, 'env': env})
    for stage, filename, extra in [('table', 'table.html', []), ('figure', 'figure.svg', ['{root}/'+p+'figure-label.txt'])]:
        stages.append({'id': stage, 'inputs': [p+'code/research_case.py', *sources] + ([p+'figure-label.txt'] if stage == 'figure' else []),
                       'depends': {'summary': ['summary']}, 'outputs': {stage: filename},
                       'argv': [python, helper, stage, '{dep:summary:summary}', *extra, '{out:'+stage+'}'], 'runtime': py_runtime, 'env': env})
    stats = {k: {'stage': 'summary', 'output': 'summary', 'key': [k], 'unit': u, 'format': f}
             for k, u, f in [('ols','outcome_per_treatment','.4f'), ('ols_se','outcome_per_treatment','.4f'),
                             ('iv','outcome_per_treatment','.4f'), ('iv_se','outcome_per_treatment','.4f'),
                             ('observations','synthetic_observations','.0f'), ('first_f','F_statistic','.2f')]}
    stages.append({'id': 'paper', 'inputs': [p+'paper-template.qmd'], 'depends': {'summary': ['summary']},
                   'outputs': {'paper': 'paper.qmd'}, 'render': {'template': p+'paper-template.qmd', 'output': 'paper', 'statistics': stats}})
    stages.append({'id': 'html', 'inputs': [p+'code/research_case.py', *sources],
                   'depends': {'paper': ['paper'], 'figure': ['figure'], 'table': ['table']}, 'outputs': {'html': 'paper.html'},
                   'argv': [python, helper, 'html', '{dep:paper:paper}', '{dep:figure:figure}', '{dep:table:table}', '{out:html}'],
                   'runtime': py_runtime, 'env': env})
    write_json(case / 'manifest.json', {'pipeline': case_id, 'stages': stages})


def specs(data, ols, iv):
    common = {'data': str(Path(data).resolve()), 'id': 'id', 'outcome': 'outcome',
              'population': 'independently generated synthetic observations', 'period': 'simulation',
              'unit': 'synthetic outcome and treatment units',
              'sources': [{'description': 'Seeded synthetic data; equations are in source.json'}],
              'sample_columns': ['instrument'], 'question': 'Compare OLS and IV in a known synthetic data-generating process.',
              'identification': 'The generated instrument is independent of the outcome error and shifts treatment.'}
    write_json(ols, {**common, 'method': 'ols', 'exog': ['treatment', 'control_centered']})
    write_json(iv, {**common, 'method': 'iv2sls', 'exog': ['control_centered'], 'endog': ['treatment'], 'instruments': ['instrument']})


def summary(ols_path, iv_path, r_summary, output):
    import csv
    ols, iv = (json.loads(Path(p).read_text()) for p in (ols_path, iv_path))
    if ols['sample']['included_ids'] != iv['sample']['included_ids']:
        raise ValueError('OLS and IV fitted samples differ')
    with Path(r_summary).open(newline='', encoding='utf-8') as stream:
        r = next(csv.DictReader(stream))
    if int(r['observations']) != ols['observations']:
        raise ValueError('R and Python observation counts differ')
    unit = 'outcome_per_treatment'
    result = {key: {'value': float(value), 'unit': u} for key, value, u in [
        ('ols', ols['coefficients']['treatment'], unit), ('ols_se', ols['standard_errors']['treatment'], unit),
        ('iv', iv['coefficients']['treatment'], unit), ('iv_se', iv['standard_errors']['treatment'], unit),
        ('observations', ols['observations'], 'synthetic_observations'),
        ('first_f', iv['first_stage']['treatment']['excluded_instrument_wald_f']['statistic'], 'F_statistic'),
        ('r_treatment_mean', r['treatment_mean'], 'treatment_units'),
        ('r_outcome_mean', r['outcome_mean'], 'outcome_units'),
        ('r_treatment_sd', r['treatment_sd'], 'treatment_units')]}
    write_json(output, result)


def table(summary_path, output):
    s = json.loads(Path(summary_path).read_text())
    text = '<table><caption>Synthetic treatment coefficients and robust standard errors</caption><thead><tr><th>Model</th><th>Coefficient</th><th>Standard error</th><th>Observations</th></tr></thead><tbody>'
    for model in ('ols', 'iv'):
        text += f"<tr><th>{model.upper()}</th><td>{s[model]['value']:.4f}</td><td>{s[model+'_se']['value']:.4f}</td><td>{s['observations']['value']:.0f}</td></tr>"
    Path(output).write_text(text + '</tbody></table>\n', encoding='utf-8')


def figure(summary_path, label_path, output):
    s = json.loads(Path(summary_path).read_text())
    title = html.escape(Path(label_path).read_text().strip())
    intervals = [(name.upper(), s[name]['value'], s[name+'_se']['value']) for name in ('ols','iv')]
    low = min(0.0, *(b - se for _, b, se in intervals))
    high = max(b + se for _, b, se in intervals)
    margin = (high-low)*0.1
    low, high = low-margin, high+margin
    def px(value):
        return 170 + 500*(value-low)/(high-low)
    items = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 750 260" role="img" aria-label="{title}">',
             f'<rect width="750" height="260" fill="white"/><text x="30" y="32" font-size="18">{title}</text>',
             '<line x1="170" y1="205" x2="670" y2="205" stroke="black"/>']
    for idx, (name, b, se) in enumerate(intervals):
        y = 90 + idx*65
        items += [f'<text x="65" y="{y+5}" font-size="16">{name}</text>',
                  f'<line x1="{px(b-se):.2f}" y1="{y}" x2="{px(b+se):.2f}" y2="{y}" stroke="#236b8e" stroke-width="3"/>',
                  f'<circle cx="{px(b):.2f}" cy="{y}" r="5" fill="#174764"/>',
                  f'<text x="{px(b):.2f}" y="{y-12}" text-anchor="middle" font-size="13">{b:.4f}</text>']
    items += [f'<text x="170" y="225" font-size="12">{low:.3f}</text>',
              f'<text x="640" y="225" font-size="12">{high:.3f}</text>',
              '<text x="420" y="250" text-anchor="middle" font-size="14">Outcome per treatment unit</text></svg>\n']
    Path(output).write_text(''.join(items), encoding='utf-8')


def assemble(paper, svg, table_path, output):
    paragraphs = Path(paper).read_text().strip().split('\n\n')
    body = ['<h1>' + html.escape(p[2:]) + '</h1>' if p.startswith('# ') else '<p>' + html.escape(p) + '</p>' for p in paragraphs]
    out = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Synthetic instrumental-variable example</title><style>body{font:17px/1.6 system-ui;max-width:900px;margin:3em auto;padding:0 1em;color:#222}svg{width:100%}table{border-collapse:collapse}td,th{padding:.4em 1em;border-bottom:1px solid #aaa;text-align:right}caption{text-align:left;font-weight:bold}</style><main>' + ''.join(body) + Path(table_path).read_text() + Path(svg).read_text() + '</main></html>\n'
    Path(output).write_text(out, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', '_prepare'):
        p = sub.add_parser(name)
        p.add_argument('--root', required=True)
        p.add_argument('--python', required=True)
        p.add_argument('--rscript', default='Rscript')
        p.add_argument('--case-id', default=DEFAULT_CASE_ID)
        p.add_argument('--source-record-dir', action='append', default=[])
    for name, args in [('specs',['data','ols','iv']), ('summary',['ols','iv','r_summary','output']),
                       ('table',['summary','output']), ('figure',['summary','label','output']),
                       ('html',['paper','figure','table','output'])]:
        p = sub.add_parser(name)
        for arg in args:
            p.add_argument(arg)
    args = parser.parse_args()
    if args.command == 'prepare': prepare(args.root, args.python, args.rscript, args.source_record_dir, args.case_id)
    elif args.command == '_prepare': materialize(args.root, args.python, args.rscript, args.source_record_dir, args.case_id)
    elif args.command == 'specs': specs(args.data, args.ols, args.iv)
    elif args.command == 'summary': summary(args.ols, args.iv, args.r_summary, args.output)
    elif args.command == 'table': table(args.summary, args.output)
    elif args.command == 'figure': figure(args.summary, args.label, args.output)
    elif args.command == 'html': assemble(args.paper, args.figure, args.table, args.output)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
