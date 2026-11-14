"""Audit a received table and check joins before any cleaning (data preparation steps P1-P2, P5).

Copy to work/<topic>_audit.py, set READ, KEY and CODEBOOK for the table, and run:

    python3 work/<topic>_audit.py data/raw/<file> outputs/qa/<name>_audit.json

The report records the input hash, shape, column types, missing and zero counts, ranges and
quantiles, codes outside the codebook, failed numeric conversions and key problems, and
assigns a status: PASS, FLAG (values to review; continue with non-destructive steps only) or
BLOCK (stop the dependent steps). Without a file argument it audits a small built-in table
with deliberate problems, so the checks can be seen working.

The helpers `strict_numeric`, `checked_merge` and `adjacent_lag` replace the unchecked
pandas calls that cause most silent data errors.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 1. READ: every column is read as text and only empty cells are missing, so parsing failures and missing
#    codes are counted here instead of being converted silently by the reader. Set encoding and separator.
READ = {'dtype': 'string', 'keep_default_na': False, 'na_values': [''], 'encoding': 'utf-8', 'sep': ','}
# 2. KEY: the columns that identify one row (the observation unit).
KEY = ['firm_id', 'year']
# 3. CODEBOOK: per column, allowed categories and the codes that mean missing (from the source documentation only).
CODEBOOK = {
    'industry': {'allowed': ['01', '02', '03']},
    'sales': {'missing_codes': [-99]},
}
NUMERIC = ['sales', 'employees']          # columns that must parse as numbers
QUANTILES = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strict_numeric(series, missing_codes=()):
    """Parse numbers; documented missing codes become NA, any other failure stops the run."""
    raw = series.astype('string').str.strip()
    coded = raw.isin([str(c) for c in missing_codes])
    parsed = pd.to_numeric(raw.where(~coded), errors='coerce')
    failed = raw.notna() & ~coded & parsed.isna()
    if failed.any():
        raise ValueError(f'{series.name}: {int(failed.sum())} values fail numeric parsing, '
                         f'e.g. {raw[failed].unique()[:5].tolist()}')
    return parsed, coded


def checked_merge(left, right, keys, validate, how='left'):
    """Merge with missing-key, cardinality and row-count checks; returns the merge and its match counts."""
    for name, frame in (('left', left), ('right', right)):
        missing = frame[keys].isna().any(axis=1)
        if missing.any():
            raise ValueError(f'{name} table has {int(missing.sum())} rows with missing keys {keys}')
    merged = left.merge(right, on=keys, how=how, validate=validate, indicator=True,
                        suffixes=('_left', '_right'))
    if how == 'left' and validate in ('one_to_one', '1:1', 'many_to_one', 'm:1') and len(merged) != len(left):
        raise ValueError(f'left merge changed the row count: {len(left)} -> {len(merged)}')
    counts = merged['_merge'].value_counts().to_dict()
    clashes = [c for c in merged.columns if c.endswith(('_left', '_right'))]
    return merged, {'rows_before': len(left), 'rows_after': len(merged),
                    'matches': {str(k): int(v) for k, v in counts.items()}, 'suffixed_columns': clashes}


def adjacent_lag(frame, unit, period, column):
    """Lag of `column` within `unit` that is NA unless the previous row is the immediately preceding period.

    `period` must be an integer index of consecutive periods (for months: year * 12 + month)."""
    ordered = frame.sort_values([unit, period])
    previous = ordered.groupby(unit)[period].shift(1)
    lag = ordered.groupby(unit)[column].shift(1).where(ordered[period].sub(previous).eq(1))
    return lag.reindex(frame.index)


def audit(frame, key, codebook, numeric):
    report = {'rows': len(frame), 'columns': len(frame.columns), 'blocks': [], 'flags': [], 'variables': {}}
    if not frame.columns.is_unique:
        report['blocks'].append('duplicate column names')
    if frame.empty:
        report['blocks'].append('empty table')
    key_missing = int(frame[key].isna().any(axis=1).sum())
    key_duplicates = int(frame.duplicated(key, keep=False).sum())
    report['key'] = {'columns': key, 'rows_with_missing_key': key_missing, 'rows_in_duplicate_keys': key_duplicates}
    if key_missing:
        report['blocks'].append(f'{key_missing} rows with a missing key')
    if key_duplicates:
        report['blocks'].append(f'{key_duplicates} rows share a key: resolve the observation unit before any join')
    for column in frame.columns:
        series = frame[column]
        entry = {'dtype': str(series.dtype), 'non_missing': int(series.notna().sum()), 'missing': int(series.isna().sum())}
        rules = codebook.get(column, {})
        if column in numeric:
            try:
                values, coded = strict_numeric(series, rules.get('missing_codes', ()))
            except ValueError as error:
                report['blocks'].append(str(error))
                report['variables'][column] = entry
                continue
            entry.update(missing_code_rows=int(coded.sum()), zero=int(values.eq(0).sum()),
                         negative=int(values.lt(0).sum()))
            if values.notna().any():
                entry.update(min=float(values.min()), max=float(values.max()),
                             quantiles={str(q): float(values.quantile(q)) for q in QUANTILES})
            if 'valid_min' in rules and values.lt(rules['valid_min']).any():
                report['flags'].append(f'{column}: {int(values.lt(rules["valid_min"]).sum())} values below {rules["valid_min"]}')
            if 'valid_max' in rules and values.gt(rules['valid_max']).any():
                report['flags'].append(f'{column}: {int(values.gt(rules["valid_max"]).sum())} values above {rules["valid_max"]}')
        elif 'allowed' in rules:
            observed = series.dropna().astype('string')
            unknown = sorted(set(observed) - set(map(str, rules['allowed'])))
            entry.update(levels=observed.value_counts().to_dict())
            if unknown:
                report['blocks'].append(f'{column}: codes outside the codebook {unknown[:10]}')
        report['variables'][column] = entry
    report['status'] = 'BLOCK' if report['blocks'] else 'FLAG' if report['flags'] else 'PASS'
    return report


def builtin_table():
    """A small firm-year table with a duplicate key, a missing key, an unknown code, a missing code and a text value."""
    return pd.DataFrame({
        'firm_id': pd.array(['001', '001', '002', '003', None], dtype='string'),
        'year': [2020, 2020, 2020, 2021, 2021],
        'industry': pd.array(['01', '01', '09', '02', '03'], dtype='string'),
        'sales': ['10', '12', '-99', 'n/a', '0'],
        'employees': ['5', '6', '3', '4', '2'],
    })


def main(path=None, out=None):
    if path:
        frame = pd.read_csv(path, **READ)
        source = {'path': str(path), 'sha256': sha256(path)}
    else:
        frame, source = builtin_table(), {'path': 'builtin', 'sha256': None}
    report = {'source': source, **audit(frame, KEY, CODEBOOK, NUMERIC)}
    text = json.dumps(report, indent=2, ensure_ascii=False, default=lambda v: v.item() if isinstance(v, np.generic) else str(v))
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text + '\n', encoding='utf-8')
    print(text)
    return report


if __name__ == '__main__':
    main(*sys.argv[1:3])
