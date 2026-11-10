"""Local research workspace over saved result displays.

Run with the project's Python environment:
python -m marimo run harness/research_gallery.py -- --root . --registry analysis/results.json
"""
import marimo

__generated_with = '0.23.4'
app = marimo.App(width='full', app_title='Research workspace')


@app.cell
def _():
    import argparse
    import copy
    import json
    from pathlib import Path
    import sys as _sys
    import subprocess
    import uuid
    import datetime
    import marimo as mo

    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import research_artifacts as artifacts
    import research_meetings as meetings
    python_executable = _sys.executable
    state_script = str(Path(__file__).resolve().with_name('state.py'))
    return Path, argparse, artifacts, copy, datetime, json, meetings, mo, python_executable, state_script, subprocess, uuid


@app.cell
def _(Path, argparse, mo):
    _parser = argparse.ArgumentParser(description='Saved research result workspace')
    _parser.add_argument('--root', type=Path, default=Path.cwd())
    _parser.add_argument('--registry', default='analysis/results.json')
    _parser.add_argument('--project', default='', help='Existing project task ID')
    _parser.add_argument('--store', default='.agents/state/team.json')
    _parser.add_argument('--github', action='append', default=[], help='Connector GitHub read snapshot')
    _parser.add_argument('--project-summary', default='', help='Saved project-view JSON')
    _parser.add_argument('--meeting', default='meetings/current', help='Saved meeting bundle')
    _parser.add_argument('--quarto', default='quarto', help='Quarto executable for saved-document rendering')
    options = _parser.parse_args()
    root = options.root.resolve(strict=True)
    registry_form = mo.ui.text(value=options.registry, label='保存レジストリ', full_width=True).form(submit_button_label='開く')
    refresh_button = mo.ui.run_button(label='再読み込み')
    refresh_get, refresh_set = mo.state(0)
    return options, refresh_button, refresh_get, refresh_set, registry_form, root


@app.cell
def _(artifacts, options, refresh_button, refresh_get, registry_form, root):
    refresh_button.value
    refresh_get()
    registry_path = registry_form.value or options.registry
    try:
        _path, registry_data = artifacts.gallery_registry(root, registry_path)
        catalogue = artifacts._gallery_items(root, _path, registry_data)
        load_error = ''
    except (ValueError, OSError) as _error:
        registry_data = {'items': {}}
        catalogue = []
        load_error = str(_error)
    return catalogue, load_error, registry_data, registry_path


@app.cell
def _(artifacts, catalogue, mo):
    kind_names = {
        'descriptive': '記述統計', 'sample_composition': '標本構成', 'distribution': '分布',
        'time_series': '時系列', 'group_comparison': '群間比較', 'coefficient': '係数',
        'event_study': 'イベントスタディ', 'robustness': '頑健性',
        'alternative_specification': '別仕様', 'table': '表', 'figure': '図',
        'att_gt': 'ATT(g,t)', 'cohort_event': '導入群別イベント', 'parallel_trends': '群別平均の推移',
        'rdd': '回帰不連続', 'iv_first_stage': 'IV 第一段階', 'iv_reduced_form': 'IV 誘導形',
        'iv_confidence_set': 'IV 信頼集合', 'scm': '実測・合成対照', 'scm_gap': '合成対照の差',
        'scm_placebo': '合成対照のプラセボ', 'binned_scatter': '階級別散布図', 'smd': '標準化平均差',
        'structural': '構造モデル', 'geo': '地理分布',
    }
    query = mo.ui.text(label='結果・変数・標本・解釈を検索', full_width=True)
    kinds = mo.ui.multiselect(options={kind_names[_key]: _key for _key in artifacts.GALLERY_KINDS}, label='種類')
    statuses = mo.ui.multiselect(options=sorted({_item['status'] for _item in catalogue}), label='採用状況')
    search_filters = mo.ui.dictionary({
        _key: mo.ui.text(label=_label, full_width=True) for _key, _label in {
            'result_id': '結果 ID', 'sample': 'サンプル', 'comparison': '比較',
            'outcome': 'アウトカム', 'specification': '仕様', 'period': '期間', 'adoption': '採用状況',
        }.items()
    })
    return kind_names, kinds, query, search_filters, statuses


@app.cell
def _(artifacts, catalogue, kind_names, kinds, mo, query, registry_data, registry_path, root, search_filters, statuses):
    _items = artifacts._gallery_items(root, root / registry_path, registry_data, query.value, search_filters.value) if catalogue else []
    matching_items = [_item for _item in _items
                      if (not kinds.value or _item['kind'] in kinds.value)
                      and (not statuses.value or _item['status'] in statuses.value)]
    result_table = mo.ui.table(
        [{'id': _item['id'], '表題': _item['title'], '種類': kind_names[_item['kind']],
          '採用状況': _item['status'], '結果 ID': ', '.join(_item['result_ids'])}
         for _item in matching_items],
        selection='multi', page_size=8, show_column_summaries=False,
        show_data_types=False, label='比較・会議資料に使う結果を選択',
    )
    return matching_items, result_table


@app.cell
def _(artifacts, catalogue, json, mo, registry_data, registry_path, result_table, root):
    selected_ids = [_row['id'] for _row in result_table.value]
    _by_id = {_item['id']: _item for _item in catalogue}
    selected_entries = [_by_id[_id] for _id in selected_ids]
    selection_download = mo.download(
        json.dumps(selected_entries, ensure_ascii=False, indent=2).encode('utf8'),
        filename='selected-results.json', mimetype='application/json',
        label='選択した表示データを保存', disabled=not selected_entries,
    )
    _previews = [mo.Html(artifacts.gallery_preview(registry_data['items'][_id])) for _id in selected_ids]
    comparison_panel = mo.vstack(_previews) if _previews else mo.md('表の行を選ぶと、保存済みの図表を表示します。')
    if selected_ids:
        _comparison = artifacts._compare_gallery_items(selected_entries)
        _regression = _comparison['regression_table']
        if len(selected_ids) > 1 and _regression['rows']:
            comparison_panel = mo.vstack([
                mo.md('### 保存済み推定結果の比較'),
                mo.Html('<section class="research-display">' + artifacts.gallery_presentation(_regression['presentation']) + '</section>'),
                mo.accordion({'比較表の説明': mo.md('\n\n'.join(_regression['presentation']['notes']))}), comparison_panel,
            ])
        _definitions = [{'定義': _key, **{_id: json.dumps(_value, ensure_ascii=False) for _id, _value in _values.items()}}
                        for _key, _values in _comparison['result_definition_differences'].items()]
        if _definitions:
            comparison_panel = mo.vstack([
                mo.md('### 結果ごとの研究定義'),
                mo.ui.table(_definitions, selection=None, show_column_summaries=False, show_data_types=False),
                comparison_panel,
            ])
        _unrecorded = _comparison['comparison_contract']['unrecorded_fields']
        if _unrecorded:
            comparison_panel = mo.vstack([
                mo.accordion({'保存定義の項目': mo.ui.table([
                    {'結果': _key, '未保存の項目': ', '.join(_values)} for _key, _values in _unrecorded.items()
                ], selection=None, show_column_summaries=False, show_data_types=False)}), comparison_panel,
            ])
    return comparison_panel, selected_entries, selected_ids, selection_download


@app.cell
def _(catalogue, mo):
    _choices = {_item['title'] + ' · ' + _item['id']: _item['id'] for _item in catalogue}
    item_picker = mo.ui.dropdown(_choices, value=next(iter(_choices), None), label='編集する図表',
                                 full_width=True)
    return (item_picker,)


@app.cell
def _(artifacts, copy, item_picker, json, mo, registry_data):
    editing_item = copy.deepcopy(registry_data['items'].get(item_picker.value))
    _display = editing_item.get('display', {}) if editing_item else {}
    _columns = editing_item['columns'] if editing_item else []
    _keys = [_column['key'] for _column in _columns]
    _available = {'選択なし': None, **{_key: _key for _key in _keys}}
    _plot_names = {'表': 'table', '棒': 'bar', '折れ線': 'line', '散布図': 'scatter',
                   '階段': 'step', '面': 'area', '係数': 'coefficient', 'イベントスタディ': 'event_study',
                   '密度': 'density', '累積分布': 'ecdf', '箱ひげ': 'box',
                   'ATT(g,t)': 'att_gt', '導入群別イベント': 'cohort_event', '群別平均の推移': 'parallel_trends',
                   '回帰不連続': 'rdd', 'IV 第一段階': 'iv_first_stage', 'IV 誘導形': 'iv_reduced_form',
                   'IV 信頼集合': 'iv_confidence_set', '実測・合成対照': 'scm', '合成対照の差': 'scm_gap',
                   '合成対照のプラセボ': 'scm_placebo', '階級別散布図': 'binned_scatter',
                   '標準化平均差': 'smd', '構造モデルの保存結果': 'structural', '地理分布': 'geo'}
    _numeric_keys = [_key for _key in _keys if editing_item and
                     any(type(_row.get(_key)) in (int, float) for _row in editing_item['rows'])]
    title_input = mo.ui.text(value=_display.get('title', editing_item['title'] if editing_item else ''), label='表題', full_width=True)
    plot_type = mo.ui.dropdown(_plot_names, value=next(_name for _name, _key in _plot_names.items()
                                                     if _key == _display.get('plot_type', 'table')), label='表示形式')
    x_column = mo.ui.dropdown(_available, value=_display.get('x') or (_keys[0] if _keys else '選択なし'), label='横軸の列')
    y_column = mo.ui.dropdown(_available, value=_display.get('y') or (_numeric_keys[0] if _numeric_keys else '選択なし'), label='値の列')
    lower_column = mo.ui.dropdown(_available, value=_display.get('lower') or '選択なし', label='保存区間の下限列')
    upper_column = mo.ui.dropdown(_available, value=_display.get('upper') or '選択なし', label='保存区間の上限列')
    series_column = mo.ui.dropdown(_available, value=_display.get('series') or '選択なし', label='系列の列')
    selected_specs = mo.ui.multiselect(options=editing_item['result_ids'] if editing_item else [],
                                       value=_display.get('selected_result_ids', editing_item['result_ids'] if editing_item else []),
                                       label='表示する保存仕様')
    columns_order = mo.ui.text_area(value='\n'.join(_display.get('column_order', _keys)),
                                    label='表示する列の順序（1 行 1 列キー）', full_width=True)
    column_labels = mo.ui.dictionary({_column['key']: mo.ui.text(
        value=_display.get('column_labels', {}).get(_column['key'], _column['label']), label=_column['key'])
        for _column in _columns}, label='列見出し')
    column_formats = mo.ui.dictionary({_key: mo.ui.text(value=_display.get('formats', {}).get(_key, ''), label=_key)
                                       for _key in _numeric_keys}, label='数値形式（例 .3f）')
    row_order = mo.ui.text_area(value=','.join(str(_index) for _index in _display.get('row_order') or []),
                               label='行の順序（0 から始まる番号、空欄は保存順）', full_width=True)
    sort_column = mo.ui.dropdown(_available, value=_display.get('sort_by') or '選択なし', label='並べ替える列')
    ascending = mo.ui.switch(value=_display.get('ascending', True), label='昇順')
    notes_input = mo.ui.text_area(value='\n'.join(_display.get('notes', [])), label='図表の説明（1 行 1 項目）', full_width=True)
    x_label = mo.ui.text(value=_display.get('x_label', ''), label='横軸名')
    y_label = mo.ui.text(value=_display.get('y_label', ''), label='縦軸名')
    x_limits = mo.ui.text(value=json.dumps(_display['x_limits']) if _display.get('x_limits') else '', label='横軸範囲 [下限, 上限]')
    y_limits = mo.ui.text(value=json.dumps(_display['y_limits']) if _display.get('y_limits') else '', label='縦軸範囲 [下限, 上限]')
    x_scale = mo.ui.dropdown(['linear', 'log', 'symlog'], value=_display.get('x_scale', 'linear'), label='横軸尺度')
    y_scale = mo.ui.dropdown(['linear', 'log', 'symlog'], value=_display.get('y_scale', 'linear'), label='縦軸尺度')
    orientation = mo.ui.dropdown({'縦': 'vertical', '横': 'horizontal'},
                                 value='横' if _display.get('orientation') == 'horizontal' else '縦', label='方向')
    legend = mo.ui.switch(value=_display.get('legend', True), label='凡例')
    legend_location = mo.ui.dropdown(['best', 'upper right', 'upper left', 'lower right', 'lower left'],
                                    value=_display.get('legend_location', 'best'), label='凡例位置')
    width = mo.ui.number(start=240, stop=4000, value=_display.get('width', 960), label='幅 px')
    height = mo.ui.number(start=240, stop=4000, value=_display.get('height', 540), label='高さ px')
    presentation_style = mo.ui.dropdown({'論文': 'paper', '発表': 'presentation'},
                                        value='発表' if _display.get('style') == 'presentation' else '論文', label='用途')
    font_size = mo.ui.number(start=6, stop=40, value=_display.get('font_size', 11), label='文字サイズ pt')
    save_display = mo.ui.run_button(label='表示を保存', disabled=editing_item is None, kind='success')
    item_revision = artifacts.state.content_hash(editing_item) if editing_item else None
    return (
        ascending, column_formats, column_labels, columns_order, editing_item, height, item_revision,
        legend, legend_location, lower_column, notes_input, orientation, plot_type, row_order,
        save_display, selected_specs, series_column, sort_column, title_input, upper_column,
        width, x_column, x_label, x_limits, x_scale, y_column, y_label, y_limits, y_scale,
        presentation_style, font_size,
    )


@app.cell
def _(editing_item, mo):
    _display = editing_item.get('display', {}) if editing_item else {}
    _keys = [_column['key'] for _column in editing_item['columns']] if editing_item else []
    _available = {'選択なし': None, **{_key: _key for _key in _keys}}
    regression_controls = mo.ui.dictionary({
        'digits': mo.ui.number(start=0, stop=10, value=_display.get('digits', 3), label='小数桁数'),
        'show_se': mo.ui.switch(value=_display.get('show_se', True), label='標準誤差を次の行に表示'),
        'show_ci': mo.ui.switch(value=_display.get('show_ci', False), label='保存区間を表示'),
        'show_p': mo.ui.switch(value=_display.get('show_p', False), label='保存 p 値を表示'),
        'table_number': mo.ui.text(value=str(_display.get('table_number', '')), label='表番号'),
        'latex_label': mo.ui.text(value=_display.get('latex_label', ''), label='LaTeX 参照名'),
        'model_column': mo.ui.dropdown(_available, value=_display.get('model_column') or '選択なし', label='モデルを区別する保存列'),
        'outcome_column': mo.ui.dropdown(_available, value=_display.get('outcome_column') or '選択なし', label='アウトカムの保存列'),
        'model_order': mo.ui.text_area(value='\n'.join(_display.get('model_order', [])), label='モデルの順序（1 行 1 ID）', full_width=True),
        'term_order': mo.ui.text_area(value='\n'.join(_display.get('term_order', [])), label='係数の順序（1 行 1 term）', full_width=True),
        'model_labels': mo.ui.text_area(value='\n'.join(key + ' = ' + value for key, value in _display.get('model_labels', {}).items()), label='モデル名（ID = 表示名）', full_width=True),
        'term_labels': mo.ui.text_area(value='\n'.join(key + ' = ' + value for key, value in _display.get('term_labels', {}).items()), label='係数名（term = 表示名）', full_width=True),
        'column_groups': mo.ui.text_area(value='\n'.join(row['label'] + ' = ' + ' | '.join(row['models']) for row in _display.get('column_groups', [])), label='列グループ（見出し = ID | ID）', full_width=True),
        'panels': mo.ui.text_area(value='\n'.join(row['label'] + ' = ' + ' | '.join(row['terms']) for row in _display.get('panels', [])), label='パネル（見出し = term | term）', full_width=True),
    })
    chart_controls = mo.ui.dictionary({
        _key: mo.ui.dropdown(_available, value=_display.get(_key) or '選択なし', label=_label)
        for _key, _label in {'component': '点・曲線の種類を示す列', 'cohort': '導入群の列', 'time': '暦時点の列',
                            'value': 'ヒートマップ・地図の値', 'geometry': '保存 GeoJSON の列',
                            'x_lower': '横方向区間の下端', 'x_upper': '横方向区間の上端', 'facet': 'パネルを分ける列'}.items()
    })
    return chart_controls, regression_controls


@app.cell
def _(editing_item, mo, series_column):
    _display = editing_item.get('display', {}) if editing_item else {}
    _series = list(dict.fromkeys(str(_row.get(series_column.value)) for _row in editing_item['rows'])) if editing_item and series_column.value else []
    _visible = [_value for _value in _display.get('visible_series', _series) if _value in _series]
    visible_series = mo.ui.multiselect(options=_series, value=_visible, label='表示する系列')
    colors = mo.ui.dictionary({_value: mo.ui.text(value=_display.get('colors', {}).get(_value, ['#245b8a', '#b4513b', '#31836b', '#8a5b9e'][_index % 4]),
                                                  label=_value) for _index, _value in enumerate(_series or [''])}, label='色（色名・HEX）')
    series_order = mo.ui.text_area(value='\n'.join(_display.get('series_order', _series)),
                                   label='系列の順序（1 行 1 系列キー）', full_width=True)
    series_labels = mo.ui.dictionary({_value: mo.ui.text(value=_display.get('series_labels', {}).get(_value, _value),
                                                        label=_value) for _value in _series}, label='系列名')
    return colors, series_labels, series_order, visible_series


@app.cell
def _(
    ascending, artifacts, colors, column_formats, column_labels, columns_order, copy,
    editing_item, height, json, legend, legend_location, lower_column, mo, notes_input,
    orientation, plot_type, row_order, selected_specs, series_column, sort_column,
    title_input, upper_column, visible_series, width, x_column, x_label, x_limits,
    x_scale, y_column, y_label, y_limits, y_scale, presentation_style, font_size, series_labels, series_order,
    chart_controls, regression_controls,
):
    candidate_item = copy.deepcopy(editing_item)
    display_changes = None
    preview_error = ''
    preview_panel = mo.md('保存済みの結果を開いてください。')
    if editing_item:
        try:
            display_changes = {
                'title': title_input.value, 'plot_type': plot_type.value, 'x': x_column.value, 'y': y_column.value,
                'lower': lower_column.value, 'upper': upper_column.value, 'series': series_column.value,
                'visible_series': visible_series.value, 'selected_result_ids': selected_specs.value,
                'column_order': [value.strip() for value in columns_order.value.splitlines() if value.strip()],
                'column_labels': column_labels.value,
                'formats': {key: value for key, value in column_formats.value.items() if value},
                'row_order': [int(value) for value in row_order.value.split(',')] if row_order.value.strip() else None,
                'sort_by': sort_column.value, 'ascending': ascending.value,
                'notes': [value for value in notes_input.value.splitlines() if value],
                'x_label': x_label.value, 'y_label': y_label.value,
                'x_limits': json.loads(x_limits.value) if x_limits.value.strip() else None,
                'y_limits': json.loads(y_limits.value) if y_limits.value.strip() else None,
                'x_scale': x_scale.value, 'y_scale': y_scale.value, 'orientation': orientation.value,
                'colors': colors.value, 'legend': legend.value, 'legend_location': legend_location.value,
                'width': int(width.value), 'height': int(height.value),
                'style': presentation_style.value, 'font_size': font_size.value,
                'preset': 'meeting' if presentation_style.value == 'presentation' else 'paper',
                'series_order': [value.strip() for value in series_order.value.splitlines() if value.strip()],
                'series_labels': series_labels.value,
            }
            display_changes.update(chart_controls.value)
            _table_settings = regression_controls.value
            display_changes.update({key: _table_settings[key] for key in
                                    ('show_se', 'show_ci', 'show_p', 'table_number', 'latex_label', 'model_column', 'outcome_column')})
            display_changes['digits'] = int(_table_settings['digits'])
            for _key in ('model_order', 'term_order'):
                display_changes[_key] = [value.strip() for value in _table_settings[_key].splitlines() if value.strip()]
            for _key in ('model_labels', 'term_labels', 'column_groups', 'panels'):
                _pairs = []
                for _line in _table_settings[_key].splitlines():
                    if not _line.strip():
                        continue
                    if '=' not in _line:
                        raise ValueError('見出しの設定は「キー = 表示名」で入力してください。')
                    _left, _right = _line.split('=', 1)
                    _pairs.append((_left.strip(), _right.strip()))
                if _key in ('column_groups', 'panels'):
                    _member = 'models' if _key == 'column_groups' else 'terms'
                    display_changes[_key] = [{'label': label, _member: [value.strip() for value in values.split('|') if value.strip()]} for label, values in _pairs]
                else:
                    display_changes[_key] = dict(_pairs)
            candidate_item['display'].update(display_changes)
            preview_panel = mo.Html(artifacts.gallery_preview(candidate_item))
        except (ValueError, TypeError, KeyError) as _error:
            preview_error = str(_error)
            preview_panel = mo.callout(preview_error, kind='danger')
    return candidate_item, display_changes, preview_error, preview_panel


@app.cell
def _(
    artifacts, display_changes, editing_item, item_revision, mo, preview_error,
    refresh_set, registry_path, root, save_display,
):
    display_save_message = mo.md('')
    if save_display.value and editing_item:
        if preview_error:
            display_save_message = mo.callout(preview_error, kind='danger')
        else:
            try:
                artifacts.edit_gallery_item(root, registry_path, editing_item['id'],
                                             {'display': display_changes}, expected_revision=item_revision)
                display_save_message = mo.callout('表示を保存しました。', kind='success')
                refresh_set(lambda value: value + 1)
            except (ValueError, OSError) as _error:
                display_save_message = mo.callout(str(_error), kind='danger')
    return (display_save_message,)


@app.cell
def _(editing_item, mo):
    interpretation_input = mo.ui.text_area(value=editing_item['interpretation'] if editing_item else '',
                                          label='結果の解釈', full_width=True, rows=5)
    status_input = mo.ui.text(value=editing_item['status'] if editing_item else '', label='採用状況')
    findings_input = mo.ui.text_area(value=editing_item.get('findings', '') if editing_item else '', label='所見', full_width=True)
    issues_input = mo.ui.text_area(value=editing_item.get('issues', '') if editing_item else '', label='残る課題', full_width=True)
    adoption_input = mo.ui.text_area(value=editing_item.get('adoption_decision', '') if editing_item else '', label='採用判断と根拠', full_width=True)
    task_links = mo.ui.text_area(value='\n'.join(editing_item['links'].get('tasks', [])) if editing_item else '',
                                 label='関連タスク（1 行 1 参照）', full_width=True)
    document_links = mo.ui.text_area(value='\n'.join(editing_item['links'].get('documents', [])) if editing_item else '',
                                     label='関連文書（1 行 1 参照）', full_width=True)
    save_interpretation = mo.ui.run_button(label='解釈・採用状況・参照を保存', disabled=editing_item is None)
    return document_links, interpretation_input, save_interpretation, status_input, task_links, findings_input, issues_input, adoption_input


@app.cell
def _(
    artifacts, document_links, editing_item, interpretation_input, item_revision, mo,
    refresh_set, registry_path, root, save_interpretation, status_input, task_links, findings_input, issues_input, adoption_input,
):
    interpretation_save_message = mo.md('')
    if save_interpretation.value and editing_item:
        try:
            _links = {**editing_item['links'],
                      'tasks': [value for value in task_links.value.splitlines() if value],
                      'documents': [value for value in document_links.value.splitlines() if value]}
            artifacts.edit_gallery_item(root, registry_path, editing_item['id'],
                                         {'interpretation': interpretation_input.value, 'status': status_input.value, 'links': _links,
                                          'findings': findings_input.value, 'issues': issues_input.value,
                                          'adoption_decision': adoption_input.value},
                                         expected_revision=item_revision)
            interpretation_save_message = mo.callout('解釈と参照を保存しました。', kind='success')
            refresh_set(lambda value: value + 1)
        except (ValueError, OSError) as _error:
            interpretation_save_message = mo.callout(str(_error), kind='danger')
    return (interpretation_save_message,)


@app.cell
def _(
    ascending, catalogue, colors, column_formats, column_labels, columns_order,
    comparison_panel, display_save_message, document_links, editing_item, height,
    interpretation_input, interpretation_save_message, item_picker, json, kinds,
    legend, legend_location, load_error, lower_column, mo, notes_input, orientation,
    plot_type, preview_panel, query, refresh_button, registry_form, result_table,
    row_order, save_display, save_interpretation, selected_specs, selection_download,
    series_column, sort_column, status_input, statuses, task_links, title_input,
    upper_column, visible_series, width, x_column, x_label, x_limits, x_scale,
    y_column, y_label, y_limits, y_scale, search_filters, presentation_style, font_size,
    series_labels, series_order, findings_input, issues_input, adoption_input, chart_controls, regression_controls,
):
    header = mo.vstack([
        mo.md('# Research workspace\n保存済みの結果を選び、比較・表示編集・会議資料に使います。'),
        mo.hstack([registry_form, refresh_button], align='end'),
        mo.callout(load_error, kind='danger') if load_error else mo.md(f'**{len(catalogue)} 件の保存済み図表**'),
    ])
    gallery_panel = mo.vstack([
        query, mo.hstack([kinds, statuses]), mo.accordion({'定義で絞り込む': search_filters}),
        result_table, selection_download, comparison_panel,
    ])
    editor_panel = mo.vstack([
        item_picker, title_input, mo.hstack([plot_type, orientation, selected_specs]),
        mo.hstack([mo.vstack([
            mo.accordion({
                '列・行・説明': mo.vstack([columns_order, column_labels, column_formats, row_order,
                                          mo.hstack([sort_column, ascending]), notes_input]),
                '経済学の回帰表': regression_controls,
                '系列と区間': mo.vstack([mo.hstack([x_column, y_column]), series_column, visible_series,
                                         series_order, series_labels, mo.hstack([lower_column, upper_column]), colors]),
                '専門図の保存列': chart_controls,
                '軸・凡例・サイズ': mo.vstack([mo.hstack([x_label, y_label]), mo.hstack([x_limits, y_limits]),
                                              mo.hstack([x_scale, y_scale]), mo.hstack([legend, legend_location]),
                                              mo.hstack([width, height]), mo.hstack([presentation_style, font_size])]),
            }), save_display, display_save_message,
        ]), preview_panel], widths=[1, 2], align='start'),
    ]) if editing_item else mo.md('保存済みの結果を開いてください。')
    interpretation_panel = mo.vstack([
        mo.md('### 選択中の結果\n' + (editing_item['title'] if editing_item else '')),
        interpretation_input, findings_input, issues_input, status_input, adoption_input,
        mo.hstack([task_links, document_links]),
        save_interpretation, interpretation_save_message,
        mo.md('### 保存された研究定義と来歴\n```json\n' + json.dumps(editing_item['metadata'] if editing_item else {},
                                                                     ensure_ascii=False, indent=2) + '\n```'),
    ])
    return editor_panel, gallery_panel, header, interpretation_panel


@app.cell
def _(artifacts, json, mo, options, root):
    _state = artifacts.state
    _store_path = root / _state.relative(root, options.store, exists=False)
    _tasks = json.loads(_store_path.read_text())['tasks'] if _store_path.is_file() else {}
    _choices = {_key: _key for _key, _task in _tasks.items() if not _task.get('parent') or _task.get('project_binding')}
    if options.project:
        _choices.setdefault(options.project, options.project)
    _selected = options.project or ('' if options.project_summary else next(iter(_choices), ''))
    project_defaults = {'project': _selected, 'github': '\n'.join(options.github), 'summary': options.project_summary}
    project_source_form = mo.ui.dictionary({
        'project': mo.ui.dropdown(_choices, value=_selected or None, label='研究プロジェクト'),
        'github': mo.ui.text_area(value=project_defaults['github'], label='取得済みの GitHub JSON（1 行 1 パス）', full_width=True),
        'summary': mo.ui.text(value=options.project_summary, label='保存済みのプロジェクト表示', full_width=True),
    }).form(submit_button_label='プロジェクトを開く')
    return project_defaults, project_source_form


@app.cell
def _(artifacts, json, options, project_defaults, project_source_form, refresh_get, root):
    refresh_get()
    project_source = project_source_form.value or project_defaults
    project_id = project_source['project'] or ''
    project_github_paths = [_value.strip() for _value in project_source['github'].splitlines() if _value.strip()]
    project_view_data, project_graph, project_task, project_history_data = None, None, None, []
    project_tasks, project_error = {}, ''
    try:
        if project_id:
            _store = json.loads((root / artifacts.state.relative(root, options.store)).read_text())
            artifacts.state.migrate(_store)
            project_tasks = _store['tasks']
            project_task = project_tasks[project_id]
            if project_task.get('project_binding'):
                try:
                    project_view_data = artifacts.state._project_view(root, project_tasks, project_id, 'manage', 'summary', None, [], github=project_github_paths)
                except (ValueError, OSError) as _error:
                    project_error = str(_error)
                    project_view_data = artifacts.state._project_view(root, project_tasks, project_id, 'manage', 'story', None, [])
                project_graph = json.loads((root / project_view_data['binding']['argument']['path']).read_text())
                project_history_data = artifacts.state._project_history(root, project_tasks, project_id)['revisions']
        elif project_source['summary'].strip():
            project_view_data = json.loads((root / artifacts.state.relative(root, project_source['summary'].strip())).read_text())
            if project_view_data.get('artifact_kind') != 'project-view':
                raise ValueError('project-view で保存した JSON を指定してください。')
    except (ValueError, OSError, KeyError) as _error:
        project_error = str(_error)
    return (
        project_error, project_github_paths, project_graph, project_history_data, project_id,
        project_source, project_task, project_tasks, project_view_data,
    )


@app.cell
def _(mo, project_graph, project_history_data, project_task, project_view_data):
    _plan = project_view_data.get('plan', {}) if project_view_data else {}
    _root_node = next((_node for _node in project_graph['nodes'] if _node['node_id'] == project_graph['root_ids'][0]), {}) if project_graph else {}
    _spec_paths = [_ref['path'] for _ref in _root_node.get('references', [])
                   if _ref['kind'] == 'file' and _ref['relation'] == 'adopted_specification']
    project_register = mo.ui.text(label='登録する計画ファイル', full_width=True).form(
        submit_button_label='計画を登録', submit_button_disabled=project_task is None or bool(project_task.get('project_binding')))
    plan_edit_form = mo.ui.dictionary({
        'question': mo.ui.text_area(value=project_view_data.get('central_question', '') if project_view_data else '', label='研究質問', full_width=True),
        'answer': mo.ui.text_area(value=project_view_data.get('central_answer', '') if project_view_data else '', label='現在の答え', full_width=True),
        'reasoning': mo.ui.text_area(value=_root_node.get('reasoning', ''), label='答えを支える根拠', full_width=True),
        'specifications': mo.ui.text_area(value='\n'.join(_spec_paths), label='採用仕様ファイル（1 行 1 パス）', full_width=True),
        'target': mo.ui.number(start=0, value=_plan.get('target_finish_hour', 0), label='目標完了時点（計画の時間単位）'),
        'approved': mo.ui.number(start=0, value=_plan.get('approved_finish_hour', 0), label='採用済みの完了時点'),
        'reason': mo.ui.text_area(label='この変更を採用する理由', full_width=True),
    }).form(submit_button_label='変更案と影響を表示', submit_button_disabled=project_graph is None)
    _revisions = {str(_row['revision']): _row['revision'] for _row in project_history_data}
    history_from = mo.ui.dropdown(_revisions, value=str(max(1, len(_revisions) - 1)) if _revisions else None,
                                   label='比較元の版')
    history_to = mo.ui.dropdown(_revisions, value=str(len(_revisions)) if _revisions else None,
                                 label='比較先の版')
    return history_from, history_to, plan_edit_form, project_register


@app.cell
def _(options, project_id, project_register, python_executable, refresh_set, root, state_script, subprocess, mo):
    project_registration_message = mo.md('')
    if project_register.value:
        _result = subprocess.run([python_executable, state_script, '--root', str(root), '--store', options.store,
                                  'project-bind', project_id, '--definition', project_register.value], capture_output=True, text=True)
        if _result.returncode:
            project_registration_message = mo.callout(_result.stderr.strip(), kind='danger')
        else:
            project_registration_message = mo.callout('計画を登録しました。', kind='success')
            refresh_set(lambda value: value + 1)
    return (project_registration_message,)


@app.cell
def _(Path, artifacts, copy, json, mo, options, plan_edit_form, project_graph, project_id, project_view_data, root, uuid):
    plan_proposal, plan_proposal_message = None, mo.md('')
    if plan_edit_form.value and project_graph:
        try:
            _value = plan_edit_form.value
            if any(not _value[_key].strip() for _key in ('question', 'answer', 'reasoning', 'reason')):
                raise ValueError('研究質問、答え、根拠、変更理由を入力してください。')
            _tasks = json.loads((root / artifacts.state.relative(root, options.store)).read_text())['tasks']
            _current = artifacts.state._project_current(root, _tasks, project_id)
            if _current[2] != project_view_data['binding']:
                raise ValueError('計画が更新されています。再読み込みして変更を作成してください。')
            _graph = copy.deepcopy(project_graph)
            _plan = copy.deepcopy(project_view_data['plan'])
            _node = next(_row for _row in _graph['nodes'] if _row['node_id'] == _graph['root_ids'][0])
            _graph['central_question'] = _node['question'] = _value['question']
            _graph['central_answer'] = _node['claim'] = _value['answer']
            _node['reasoning'] = _value['reasoning']
            if 'integration' in _node:
                _node['integration'].update(conclusion=_value['answer'], meaning=_value['reasoning'])
            if _node.get('inference', {}).get('steps'):
                _node['inference']['steps'][-1]['claim'] = _value['answer']
            if _graph.get('introduction'):
                _graph['introduction'].update(question=_value['question'], answer=_value['answer'])
            _old_refs = {_ref['path']: _ref for _ref in _node.get('references', [])
                         if _ref['kind'] == 'file' and _ref['relation'] == 'adopted_specification'}
            _references = [_ref for _ref in _node.get('references', [])
                           if not (_ref['kind'] == 'file' and _ref['relation'] == 'adopted_specification')]
            for _path in dict.fromkeys(_line.strip() for _line in _value['specifications'].splitlines() if _line.strip()):
                _path = artifacts.state.relative(root, _path)
                _references.append({**_old_refs.get(_path, {'kind': 'file', 'id': _path, 'path': _path,
                                                           'relation': 'adopted_specification', 'basis': _value['reason']}),
                                    'version': artifacts.state.digest(root / _path)})
            if _references or 'references' in _node:
                _node['references'] = _references
            _plan.update(target_finish_hour=_value['target'], approved_finish_hour=_value['approved'])
            _token = uuid.uuid4().hex
            _directory = Path(_tasks[project_id]['project_baseline']['definition']['path']).parent / 'versions'
            _argument_path = (_directory / ('argument-' + _token + '.json')).as_posix()
            _definition_path = (_directory / ('plan-' + _token + '.json')).as_posix()
            artifacts.state.relative(root, _argument_path, exists=False)
            artifacts.state.relative(root, _definition_path, exists=False)
            (root / _directory).mkdir(parents=True, exist_ok=True)
            _graph['version'] = _token
            _plan['argument']['path'] = _argument_path
            artifacts.state.save(root / _argument_path, _graph)
            artifacts.state.save(root / _definition_path, _plan)
            _difference = artifacts.state._project_diff(root, _tasks, project_id, definition_path=_definition_path)
            plan_proposal = {'definition': _definition_path, 'difference': _difference, 'instruction': _value}
            plan_proposal_message = mo.callout('変更案を保存しました。差分と影響を確認して採用できます。', kind='success')
        except (ValueError, OSError, KeyError) as _error:
            plan_proposal_message = mo.callout(str(_error), kind='danger')
    return plan_proposal, plan_proposal_message


@app.cell
def _(mo, plan_proposal, project_task):
    plan_adopt = mo.ui.run_button(label='表示中の変更案を採用', kind='success',
                                 disabled=plan_proposal is None or project_task is None or project_task['status'] == 'running')
    return (plan_adopt,)


@app.cell
def _(Path, artifacts, json, mo, options, plan_adopt, plan_proposal, project_id, python_executable, refresh_set, root, state_script, subprocess, uuid):
    plan_adoption_message = mo.md('')
    if plan_adopt.value and plan_proposal:
        try:
            _difference = plan_proposal['difference']
            _evidence_path = Path(plan_proposal['definition']).with_suffix('.adoption.json').as_posix()
            _evidence = {'source': 'user', 'message_id': 'workspace-adoption:' + uuid.uuid4().hex,
                         'text': json.dumps(plan_proposal['instruction'], ensure_ascii=False),
                         'previous_project_sha256': artifacts.state.content_hash(_difference['from_binding']),
                         'replacement_project_sha256': artifacts.state.content_hash(_difference['to_binding'])}
            artifacts.state.save(root / _evidence_path, _evidence)
            _result = subprocess.run([python_executable, state_script, '--root', str(root), '--store', options.store,
                'project-bind', project_id, '--definition', plan_proposal['definition'], '--user-change', _evidence_path], capture_output=True, text=True)
            if _result.returncode:
                raise ValueError(_result.stderr.strip())
            plan_adoption_message = mo.callout('変更案を採用し、計画の履歴へ保存しました。', kind='success')
            refresh_set(lambda value: value + 1)
        except (ValueError, OSError) as _error:
            plan_adoption_message = mo.callout(str(_error), kind='danger')
    return (plan_adoption_message,)


@app.cell
def _(artifacts, history_from, history_to, json, mo, plan_proposal, project_history_data, project_id, project_tasks, root):
    plan_difference_panel = mo.md('計画を登録すると、版の比較と変更の影響を表示します。')
    if project_history_data:
        try:
            _difference = plan_proposal['difference'] if plan_proposal else artifacts.state._project_diff(
                root, project_tasks, project_id, history_from.value, history_to.value)
            _impact = _difference['impact']
            _changes = [{'対象': _row['path'], '変更前': json.dumps(_row.get('before'), ensure_ascii=False),
                         '変更後': json.dumps(_row.get('after'), ensure_ascii=False)} for _row in _difference['changes']]
            plan_difference_panel = mo.vstack([
                mo.md('### 変更案の差分と影響' if _difference['proposed'] else '### 保存された版の差分と影響'),
                mo.ui.table(_changes, selection=None, show_column_summaries=False, show_data_types=False),
                mo.md('**影響する実行タスク:** ' + ', '.join(_impact['affected_task_ids']) + '\n\n'
                      + '**日程を再評価するタスク:** ' + ', '.join(_impact['schedule_task_ids'])),
                mo.ui.table(_impact['affected_outputs'], selection=None, label='変更の影響を受ける成果',
                            show_column_summaries=False, show_data_types=False),
                mo.ui.table(_impact['reusable_outputs'], selection=None, label='再利用する保存済み成果',
                            show_column_summaries=False, show_data_types=False),
                mo.md('\n\n'.join('[' + _row['task_id'] + '](' + _row['url'] + ')' for _row in _impact['affected_issues'])),
            ])
        except (ValueError, OSError, KeyError) as _error:
            plan_difference_panel = mo.callout(str(_error), kind='danger')
    return (plan_difference_panel,)


@app.cell
def _(json, mo, project_view_data):
    project_record_roles = {'発見': 'project_finding', '解釈': 'project_interpretation', '未決事項': 'project_open_decision'}
    project_records = [_row for _row in (project_view_data or {}).get('observations', []) if _row['role'] in project_record_roles.values()]
    _choices = {'新しい記録': None, **{
        _row['output_id'] + ' · ' + _row['value']['text'][:70]: json.dumps([_row['record_task_id'], _row['output_id']])
        for _row in project_records}}
    project_record_picker = mo.ui.dropdown(_choices, value='新しい記録', label='編集する研究記録', full_width=True)
    return project_record_picker, project_record_roles, project_records


@app.cell
def _(artifacts, json, mo, project_graph, project_id, project_record_picker, project_record_roles, project_records, project_tasks):
    project_editing_record = next((_row for _row in project_records
                                  if json.dumps([_row['record_task_id'], _row['output_id']]) == project_record_picker.value), None)
    _role = project_editing_record['role'] if project_editing_record else 'project_finding'
    project_record_kind = mo.ui.dropdown(
        {_label: _value for _label, _value in project_record_roles.items()
         if project_editing_record is None or _value == _role},
        value=next(_label for _label, _value in project_record_roles.items() if _value == _role),
        label='記録の種類')
    project_record_targets = {}
    if project_graph:
        project_record_targets.update({_node['node_id'] + ' · ' + _node['claim'][:65]: json.dumps({
            'node_id': _node['node_id'], 'argument_sha256': artifacts.state._project_argument().argument_sha256(project_graph)})
            for _node in project_graph['nodes']})
        project_record_targets.update({_key + ' / ' + _output_id: json.dumps({
            'task_id': _key, 'output_id': _output_id, 'content_version': _output['version']})
            for _key, _task in project_tasks.items() if artifacts.state._project_descendant(project_tasks, _key, project_id)
            for _output_id, _output in _task['outputs'].items() if _output.get('role') not in project_record_roles.values()})
    return project_editing_record, project_record_kind, project_record_targets


@app.cell
def _(artifacts, json, mo, project_editing_record, project_graph, project_record_kind, project_record_targets):
    _value = project_editing_record['value'] if project_editing_record else {}
    _statuses = {'project_finding': {'観察済み': 'observed'},
                 'project_interpretation': {'記録済み': 'recorded', '提案': 'proposed'},
                 'project_open_decision': {'未決': 'open', '解決済み': 'resolved'}}[project_record_kind.value]
    _target = next((_label for _label, _target in project_record_targets.items()
                    if json.loads(_target) == _value.get('target')), next(iter(project_record_targets), None))
    _fields = {
        'text': mo.ui.text_area(value=_value.get('text', ''), label='内容', rows=5, full_width=True),
        'actor': mo.ui.text(value=_value.get('actor', ''), label='記録者'),
        'date': mo.ui.text(value=_value.get('date', artifacts.state.now()), label='記録日時'),
        'status': mo.ui.dropdown(_statuses, value=next((_label for _label, _status in _statuses.items()
                                                       if _status == _value.get('status')), next(iter(_statuses))), label='記録の状態'),
        'target': mo.ui.dropdown(project_record_targets, value=_target, label='対応する主張・保存済み成果', full_width=True),
        'evidence': mo.ui.text_area(value='\n'.join(_row['path'] for _row in _value.get('evidence', [])),
                                    label='根拠となる保存ファイル（1 行 1 パス）', full_width=True),
    }
    if project_record_kind.value == 'project_open_decision':
        _fields['decision_id'] = mo.ui.text(value=_value.get('decision_id', ''), label='判断 ID')
    project_record_form = mo.ui.dictionary(_fields).form(submit_button_label='研究記録を保存', submit_button_disabled=project_graph is None)
    return (project_record_form,)


@app.cell
def _(
    artifacts, copy, json, mo, options, project_editing_record, project_id, project_record_form,
    project_record_kind, python_executable, refresh_set, root, state_script, subprocess, uuid,
):
    project_record_message = mo.md('')
    if project_record_form.value:
        try:
            _form = project_record_form.value
            if any(not _form[_key].strip() for _key in ('text', 'actor', 'date', 'evidence')) or not _form['target']:
                raise ValueError('内容、記録者、日時、対応先、根拠ファイルを入力してください。')
            if project_record_kind.value == 'project_open_decision' and not _form.get('decision_id', '').strip():
                raise ValueError('未決事項の判断 ID を入力してください。')
            _value = copy.deepcopy(project_editing_record['value']) if project_editing_record else {}
            _value.update({key: _form[key] for key in ('text', 'actor', 'date', 'status')})
            _value['target'] = json.loads(_form['target'])
            _value['evidence'] = [{'path': artifacts.state.relative(root, _path.strip()),
                                   'sha256': artifacts.state.digest(root / artifacts.state.relative(root, _path.strip()))}
                                  for _path in _form['evidence'].splitlines() if _path.strip()]
            if 'decision_id' in _form:
                _value['decision_id'] = _form['decision_id']
            _prefix = [python_executable, state_script, '--root', str(root), '--store', options.store]
            _commands = []
            _complete = True
            _extra = []
            if project_editing_record:
                _record_task = project_editing_record['record_task_id']
                _output_id = project_editing_record['output_id']
                _latest = json.loads((root / options.store).read_text())['tasks'][_record_task]
                _output = _latest['outputs'][_output_id]
                if _output['version'] != project_editing_record['version']:
                    raise ValueError('記録が更新されています。再読み込みして編集してください。')
                if _latest['status'] == 'running':
                    _complete = False
                else:
                    if _latest['status'] != 'queued':
                        _commands.append(['requeue', _record_task, '--output', _output_id])
                    _commands.append(['start', _record_task])
                _extra = ['--definition-versions', json.dumps(_output.get('definition_versions', {})),
                          '--producer-id', _output.get('producer_id', _record_task)]
                if _output.get('publication_group_id'):
                    _extra += ['--publication-group-id', _output['publication_group_id']]
                for _dependency in _output.get('dependency_ids', []):
                    _extra += ['--dependency', _dependency]
                if not _output.get('dependency_ids'):
                    _extra.append('--no-dependencies')
            else:
                _record_task = project_id + '-note-' + uuid.uuid4().hex[:12]
                _output_id = 'observation:' + uuid.uuid4().hex
                _requirement = {'role': project_record_kind.value, 'kind': 'object', 'target': _output_id}
                _commands = [['add', _record_task, '--parent', project_id, '--owner', _form['actor'],
                              '--operation-kind', 'answer', '--required-output', json.dumps(_requirement),
                              '--next', 'Save the research observation'], ['start', _record_task]]
            _commands.append(['output', _record_task, _output_id, '--kind', 'object', '--role', project_record_kind.value,
                              '--value', json.dumps(_value, ensure_ascii=False), *_extra])
            if _complete:
                _commands.append(['transition', _record_task, 'completed'])
            for _command in _commands:
                _result = subprocess.run([*_prefix, *_command], capture_output=True, text=True)
                if _result.returncode:
                    raise ValueError(_result.stderr.strip())
            project_record_message = mo.callout('研究記録を保存しました。', kind='success')
            refresh_set(lambda value: value + 1)
        except (ValueError, OSError, KeyError) as _error:
            project_record_message = mo.callout(str(_error), kind='danger')
    return (project_record_message,)


@app.cell
def _(mo, project_task):
    _decisions = ((project_task or {}).get('task_context') or {}).get('adopted_decisions', [])
    decision_picker = mo.ui.dropdown({'新しい採用判断': None, **{_row['decision_id']: _row['decision_id'] for _row in _decisions}},
                                     value='新しい採用判断', label='編集する採用判断')
    return (decision_picker,)


@app.cell
def _(decision_picker, mo, project_task):
    project_context_value = (project_task or {}).get('task_context') or {
        'request_refs': [], 'active_instruction_refs': [], 'adopted_decisions': [], 'goal_and_constraints': ''}
    editing_decision = next((_row for _row in project_context_value['adopted_decisions'] if _row['decision_id'] == decision_picker.value), None)
    _row = editing_decision or {}
    decision_form = mo.ui.dictionary({
        'goal': mo.ui.text_area(value=project_context_value['goal_and_constraints'], label='研究目的と固定条件', full_width=True),
        'decision_id': mo.ui.text(value=_row.get('decision_id', ''), label='判断 ID', disabled=editing_decision is not None),
        'choice': mo.ui.text_area(value=_row.get('choice', ''), label='採用する判断', full_width=True),
        'reason': mo.ui.text_area(value=_row.get('reason', ''), label='判断の根拠', full_width=True),
        'switch_condition': mo.ui.text_area(value=_row.get('switch_condition', ''), label='判断を変更する条件', full_width=True),
        'change_authority': mo.ui.dropdown({'ユーザーが変更する': 'fixed', '定めた条件で担当者が変更する': 'delegated'},
            value='定めた条件で担当者が変更する' if _row.get('change_authority') == 'delegated' else 'ユーザーが変更する', label='変更権限'),
    }).form(submit_button_label='判断を採用して保存', submit_button_disabled=project_task is None or project_task['status'] == 'running')
    return decision_form, editing_decision, project_context_value


@app.cell
def _(
    Path, artifacts, copy, decision_form, editing_decision, json, mo, options, project_context_value,
    project_id, project_task, python_executable, refresh_set, root, state_script, subprocess, uuid,
):
    decision_save_message = mo.md('')
    if decision_form.value and project_task:
        try:
            _form = decision_form.value
            if any(not _form[_key].strip() for _key in ('goal', 'decision_id', 'choice', 'reason', 'switch_condition')):
                raise ValueError('目的、判断 ID、判断、根拠、変更条件を入力してください。')
            _latest = json.loads((root / options.store).read_text())['tasks'][project_id]
            _previous = _latest.get('task_context')
            if _previous != project_task.get('task_context'):
                raise ValueError('採用判断が更新されています。再読み込みして編集してください。')
            _context = copy.deepcopy(project_context_value)
            _context['goal_and_constraints'] = _form['goal']
            _version = (editing_decision['version'] + 1 if type(editing_decision['version']) is int
                        else str(editing_decision['version']) + '.' + uuid.uuid4().hex[:8]) if editing_decision else 1
            _decision = {key: _form[key] for key in ('decision_id', 'choice', 'reason', 'switch_condition', 'change_authority')}
            _decision['version'] = _version
            _context['adopted_decisions'] = [_row for _row in _context['adopted_decisions'] if _row['decision_id'] != _form['decision_id']] + [_decision]
            _directory = Path((_latest.get('project_baseline') or {}).get('definition', {}).get('path', 'analysis/plan.json')).parent / 'versions'
            _token = uuid.uuid4().hex
            _context_path = (_directory / ('context-' + _token + '.json')).as_posix()
            _evidence_path = (_directory / ('context-' + _token + '.adoption.json')).as_posix()
            artifacts.state.relative(root, _context_path, exists=False)
            (root / _directory).mkdir(parents=True, exist_ok=True)
            artifacts.state.save(root / _context_path, _context)
            artifacts.state.load_task_context(root, _context_path)
            _evidence = {'source': 'user', 'message_id': 'workspace-decision:' + _token, 'text': json.dumps(_form, ensure_ascii=False),
                         'previous_context_sha256': artifacts.state.content_hash(_previous),
                         'replacement_context_sha256': artifacts.state.content_hash(_context)}
            artifacts.state.save(root / _evidence_path, _evidence)
            _result = subprocess.run([python_executable, state_script, '--root', str(root), '--store', options.store,
                'set-context', project_id, '--task-context', _context_path, '--user-change', _evidence_path], capture_output=True, text=True)
            if _result.returncode:
                raise ValueError(_result.stderr.strip())
            decision_save_message = mo.callout('採用判断を保存しました。', kind='success')
            refresh_set(lambda value: value + 1)
        except (ValueError, OSError, KeyError) as _error:
            decision_save_message = mo.callout(str(_error), kind='danger')
    return (decision_save_message,)


@app.cell
def _(mo, project_source, project_task):
    project_summary_target = mo.ui.text(value=project_source['summary'] or 'analysis/project-summary.json',
                                        label='会議で使うプロジェクト表示の保存先', full_width=True)
    project_save_summary = mo.ui.run_button(label='現在のプロジェクト表示を保存',
        disabled=project_task is None or not project_task.get('project_binding'))
    return project_save_summary, project_summary_target


@app.cell
def _(
    mo, options, project_github_paths, project_id, project_save_summary, project_source, project_summary_target,
    python_executable, root, state_script, subprocess,
):
    project_saved_summary = project_source['summary'] or None
    project_summary_message = mo.md('')
    if project_save_summary.value:
        _arguments = [python_executable, state_script, '--root', str(root), '--store', options.store,
                      'project-view', project_id, '--role', 'manage', '--view', 'summary', '--save', project_summary_target.value]
        for _path in project_github_paths:
            _arguments += ['--github', _path]
        _result = subprocess.run(_arguments, capture_output=True, text=True)
        if _result.returncode:
            project_summary_message = mo.callout(_result.stderr.strip(), kind='danger')
        else:
            project_saved_summary = project_summary_target.value
            project_summary_message = mo.callout('プロジェクト表示を保存しました: ' + project_saved_summary, kind='success')
    return project_saved_summary, project_summary_message


@app.cell
def _(
    decision_form, decision_picker, decision_save_message, history_from, history_to, mo,
    plan_adopt, plan_adoption_message, plan_difference_panel, plan_edit_form, plan_proposal_message,
    project_error, project_graph, project_history_data, project_record_form, project_record_kind,
    project_record_message, project_record_picker, project_register, project_registration_message,
    project_save_summary, project_source_form, project_summary_message, project_summary_target, project_view_data,
):
    _view = project_view_data or {}
    _github = _view.get('github', {})
    _management = _github.get('management', {})
    _links = [('Issues', _management.get('issues_url')), ('新しいタスク', _management.get('new_issue_url')),
              ('GitHub Project', _management.get('project_url'))]
    _groups = {}
    for _key, _label in [('completed', '完了'), ('active', '進行中'), ('next', '次の作業'), ('blocked', '依存先の完了待ち')]:
        _rows = [{'タスク': _task.get('title', ''), '担当者': ', '.join(_task.get('assignees', [])),
                  '優先順位': _task.get('priority'), '期限': _task.get('due_date'), '分類': _task.get('classification'),
                  '進捗': _task.get('progress'), 'Issue': _task.get('url'),
                  '依存先': '\n'.join(_dependency['url'] for _dependency in (_task.get('dependencies') or {}).get('blocked_by', [])),
                  '研究資料': ', '.join(_id for _ids in (_task.get('links') or {}).get('artifact_ids', {}).values() for _id in _ids)}
                 for _task in _view.get(_key, [])]
        _groups[_label + ' · ' + str(len(_rows))] = mo.ui.table(_rows, selection=None, show_column_summaries=False,
                                                              show_data_types=False, page_size=8)
    _task_panel = mo.vstack([
        mo.md('### GitHub の作業\n' + ' · '.join('[' + _label + '](' + _url + ')' for _label, _url in _links if _url)),
        mo.md('取得日時: ' + _github.get('fetched_at', '')),
        mo.ui.tabs(_groups),
        mo.md('タスクの内容・担当者・進捗・優先順位・期限・依存関係は、上の GitHub リンクで編集します。'),
        project_summary_target, project_save_summary, project_summary_message,
    ]) if _github else mo.md('計画の GitHub 接続を開くと、完了・進行中・次の作業を表示します。')
    _history = [{'版': _row['revision'], '採用日時': _row['at'], '計画ファイル': _row['binding']['definition']['path']}
                for _row in project_history_data]
    _references = [{'主張': _node['node_id'], '参照': _reference['path'], '関係': _reference['relation'], '根拠': _reference['basis']}
                   for _node in (project_graph or {}).get('nodes', []) for _reference in _node.get('references', [])]
    _plan_panel = mo.vstack([
        mo.md('### 研究計画\n' + _view.get('central_question', '')),
        project_register, project_registration_message, plan_edit_form, plan_proposal_message,
        mo.accordion({'保存された計画の版': mo.vstack([
            mo.ui.table(_history, selection=None, show_column_summaries=False, show_data_types=False),
            mo.hstack([history_from, history_to])]),
            '採用仕様と研究資料の参照': mo.ui.table(_references, selection=None, show_column_summaries=False, show_data_types=False)}),
        plan_difference_panel, plan_adopt, plan_adoption_message,
    ])
    _records = [{'種類': _label, '内容': _record['value']['text'], '記録者': _record['value']['actor'], '日時': _record['value']['date']}
                for _key, _label in [('findings', '発見'), ('interpretations', '解釈'), ('open_decisions', '未決事項')]
                for _record in _view.get(_key, [])]
    _decisions = [{'判断 ID': _row['decision_id'], '採用した判断': _row['choice'], '根拠': _row['reason'],
                   '変更する条件': _row['switch_condition']} for _row in _view.get('adopted_decisions', [])]
    _record_panel = mo.vstack([
        mo.ui.table(_records, selection=None, label='現在の研究記録', show_column_summaries=False, show_data_types=False),
        mo.hstack([project_record_picker, project_record_kind]), project_record_form, project_record_message,
        mo.md('### 採用判断'),
        mo.ui.table(_decisions, selection=None, show_column_summaries=False, show_data_types=False),
        decision_picker, decision_form, decision_save_message,
    ])
    project_panel = mo.vstack([
        project_source_form, mo.callout(project_error, kind='danger') if project_error else mo.md(''),
        mo.ui.tabs({'研究計画': _plan_panel, 'GitHub の作業': _task_panel, '発見と判断': _record_panel}),
    ])
    return (project_panel,)


@app.cell
def _(mo, options):
    meeting_path_get, meeting_path_set = mo.state(options.meeting)
    meeting_refresh_get, meeting_refresh_set = mo.state(0)
    return meeting_path_get, meeting_path_set, meeting_refresh_get, meeting_refresh_set


@app.cell
def _(datetime, meetings, mo, project_saved_summary, root):
    _template_source = meetings.template_path(root, 'meeting_templates.json')
    if _template_source is None:
        raise ValueError('Missing tex/slides/meeting_templates.json')
    _templates = meetings.read_json(_template_source)
    _template_options = {definition['label']: key for key, definition in _templates.items()}
    meeting_create_form = mo.ui.dictionary({
        'title': mo.ui.text(value='研究ミーティング', label='資料の表題', full_width=True),
        'kind': mo.ui.dropdown(_template_options, value=_templates['meeting']['label'], label='テンプレート'),
        'date': mo.ui.text(value=datetime.date.today().isoformat(), label='日付'),
        'output': mo.ui.text(value='meetings/' + datetime.date.today().isoformat(), label='新しい資料の保存先', full_width=True),
        'previous': mo.ui.text(label='前回資料のディレクトリ', full_width=True),
        'summary': mo.ui.text(value=project_saved_summary or '', label='保存済みのプロジェクト表示（空欄は現在の表示）', full_width=True),
        'issue': mo.ui.text(label='関連 Issue の URL', full_width=True),
    }).form(submit_button_label='選択した図表で資料を作成')
    return (meeting_create_form,)


@app.cell
def _(meeting_create_form, meeting_path_set, meeting_refresh_set, meetings, mo, project_view_data, root, selected_entries):
    meeting_creation_message = mo.md('')
    if meeting_create_form.value:
        try:
            _value = meeting_create_form.value
            _view = meetings.read_json(root / _value['summary']) if _value['summary'].strip() else project_view_data
            _result = meetings.create_bundle(root, root / _value['output'], selected_entries,
                title=_value['title'], kind=_value['kind'], date=_value['date'], project_view=_view,
                previous=(root / _value['previous']) if _value['previous'].strip() else None, issue_url=_value['issue'])
            meeting_path_set(_value['output'])
            meeting_refresh_set(lambda value: value + 1)
            meeting_creation_message = mo.callout('資料を保存しました: ' + _value['output'], kind='success')
        except (ValueError, OSError, KeyError) as _error:
            meeting_creation_message = mo.callout(str(_error), kind='danger')
    return (meeting_creation_message,)


@app.cell
def _(meeting_path_get, mo):
    meeting_open_form = mo.ui.text(value=meeting_path_get(), label='編集する資料のディレクトリ',
                                   full_width=True).form(submit_button_label='資料を開く')
    return (meeting_open_form,)


@app.cell
def _(meeting_open_form, meeting_path_set):
    if meeting_open_form.value:
        meeting_path_set(meeting_open_form.value)
    return


@app.cell
def _(meeting_path_get, meeting_refresh_get, meetings, root):
    meeting_refresh_get()
    meeting_path = root / meeting_path_get()
    meeting_data, meeting_bodies, meeting_revision, meeting_error = None, {}, '', ''
    if (meeting_path / 'meeting.json').is_file():
        try:
            meeting_data, meeting_bodies, meeting_revision = meetings.load_meeting(meeting_path)
        except (ValueError, OSError, KeyError) as _error:
            meeting_error = str(_error)
    return meeting_bodies, meeting_data, meeting_error, meeting_path, meeting_revision


@app.cell
def _(meeting_data, mo):
    _sections = meeting_data['sections'] if meeting_data else []
    _choices = {_row['title'] + ' · ' + _row['id']: _row['id'] for _row in _sections}
    meeting_section_picker = mo.ui.dropdown(_choices, value=next(iter(_choices), None),
        label='編集するスライド', full_width=True)
    return (meeting_section_picker,)


@app.cell
def _(meeting_bodies, meeting_data, meeting_section_picker, mo):
    _section = next((_row for _row in meeting_data['sections'] if _row['id'] == meeting_section_picker.value), {}) if meeting_data else {}
    meeting_section_form = mo.ui.dictionary({
        'title': mo.ui.text(value=_section.get('title', ''), label='見出し', full_width=True),
        'body': mo.ui.text_area(value=meeting_bodies.get(_section.get('id'), ''), label='本文（Markdown）', full_width=True, rows=7),
        'visible': mo.ui.switch(value=_section.get('visible', True), label='このスライドを表示'),
        'layout': mo.ui.dropdown(['stack', 'figure-left', 'figure-right', 'figures'],
                                 value=_section.get('layout', 'stack'), label='図表と本文の配置'),
        'artifacts': mo.ui.multiselect(options=list(meeting_data['artifacts']) if meeting_data else [],
                                       value=_section.get('artifacts', []), label='保存済みの図表'),
        'caption': mo.ui.text_area(value=_section.get('caption', ''), label='注記', full_width=True),
        'speaker_notes': mo.ui.text_area(value=_section.get('speaker_notes', ''), label='発表者ノート', full_width=True),
    }).form(submit_button_label='スライドを保存', submit_button_disabled=not _section)
    return (meeting_section_form,)


@app.cell
def _(meeting_path, meeting_refresh_set, meeting_revision, meeting_section_form, meeting_section_picker, meetings, mo):
    meeting_edit_message = mo.md('')
    if meeting_section_form.value and meeting_section_picker.value:
        try:
            _value = dict(meeting_section_form.value)
            _body = _value.pop('body')
            meetings.edit_section(meeting_path, meeting_section_picker.value, _value,
                                  expected_revision=meeting_revision, body=_body)
            meeting_edit_message = mo.callout('本文と表示を保存しました。', kind='success')
            meeting_refresh_set(lambda value: value + 1)
        except (ValueError, OSError) as _error:
            meeting_edit_message = mo.callout(str(_error), kind='danger')
    return (meeting_edit_message,)


@app.cell
def _(meeting_data, meeting_section_picker, mo):
    _disabled = not meeting_data or not meeting_section_picker.value
    meeting_move_up = mo.ui.run_button(label='上へ移動', disabled=_disabled)
    meeting_move_down = mo.ui.run_button(label='下へ移動', disabled=_disabled)
    meeting_remove = mo.ui.run_button(label='このスライドを構成から削除', disabled=_disabled)
    return meeting_move_down, meeting_move_up, meeting_remove


@app.cell
def _(
    meeting_data, meeting_move_down, meeting_move_up, meeting_path, meeting_refresh_set,
    meeting_remove, meeting_revision, meeting_section_picker, meetings, mo,
):
    meeting_order_message = mo.md('')
    if meeting_data and (meeting_move_up.value or meeting_move_down.value or meeting_remove.value):
        try:
            _identity = meeting_section_picker.value
            if meeting_remove.value:
                meetings.change_sections(meeting_path, expected_revision=meeting_revision, remove=_identity)
            else:
                _order = [_row['id'] for _row in meeting_data['sections']]
                _index = _order.index(_identity)
                _target = max(0, min(len(_order) - 1, _index + (-1 if meeting_move_up.value else 1)))
                _order[_index], _order[_target] = _order[_target], _order[_index]
                meetings.change_sections(meeting_path, expected_revision=meeting_revision, order=_order)
            meeting_order_message = mo.callout('スライドの構成を保存しました。', kind='success')
            meeting_refresh_set(lambda value: value + 1)
        except (ValueError, OSError) as _error:
            meeting_order_message = mo.callout(str(_error), kind='danger')
    return (meeting_order_message,)


@app.cell
def _(meeting_data, mo):
    meeting_add_form = mo.ui.dictionary({
        'title': mo.ui.text(value='追加スライド', label='見出し', full_width=True),
        'body': mo.ui.text_area(label='本文', full_width=True),
    }).form(submit_button_label='スライドを追加', submit_button_disabled=meeting_data is None)
    return (meeting_add_form,)


@app.cell
def _(meeting_add_form, meeting_path, meeting_refresh_set, meeting_revision, meetings, mo, uuid):
    meeting_add_message = mo.md('')
    if meeting_add_form.value:
        try:
            meetings.change_sections(meeting_path, expected_revision=meeting_revision,
                add={'id': 'slide-' + uuid.uuid4().hex[:12], **meeting_add_form.value})
            meeting_add_message = mo.callout('スライドを追加しました。', kind='success')
            meeting_refresh_set(lambda value: value + 1)
        except (ValueError, OSError) as _error:
            meeting_add_message = mo.callout(str(_error), kind='danger')
    return (meeting_add_message,)


@app.cell
def _(meeting_data, mo):
    meeting_render_form = mo.ui.dictionary({
        'format': mo.ui.dropdown(['html', 'pdf', 'markdown', 'google-slides'], value='html', label='出力形式'),
        'output': mo.ui.text(value='outputs/meeting', label='出力先（完成版は新しいディレクトリ）', full_width=True),
    }).form(submit_button_label='保存済みの図表から出力', submit_button_disabled=meeting_data is None)
    return (meeting_render_form,)


@app.cell
def _(meeting_path, meeting_render_form, meetings, mo, options, root, subprocess):
    meeting_render_message = mo.md('')
    meeting_download = mo.md('')
    if meeting_render_form.value:
        try:
            _value = meeting_render_form.value
            _output = root / _value['output']
            if _value['format'] == 'google-slides':
                if _output.exists():
                    raise ValueError('新しいパケットの保存先を指定してください。')
                _packet = meetings.native_slides_requests(meeting_path)
                meetings.write_json(_output, _packet)
                _file, _mime = _output, 'application/json'
            else:
                _result = meetings.render_bundle(root, meeting_path, _output, quarto=options.quarto,
                                                 output_format=_value['format'])
                _suffix = {'html': 'html', 'pdf': 'pdf', 'markdown': 'md'}[_value['format']]
                _file = _output / ('index.' + _suffix)
                _mime = {'html': 'text/html', 'pdf': 'application/pdf', 'markdown': 'text/markdown'}[_value['format']]
            meeting_render_message = mo.callout('資料を出力しました: ' + str(_file), kind='success')
            meeting_download = mo.download(_file.read_bytes(), filename=_file.name, mimetype=_mime, label='資料をダウンロード')
        except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as _error:
            meeting_render_message = mo.callout(getattr(_error, 'stderr', '') or str(_error), kind='danger')
    return meeting_download, meeting_render_message


@app.cell
def _(
    meeting_add_form, meeting_add_message, meeting_bodies, meeting_create_form, meeting_creation_message,
    meeting_data, meeting_download, meeting_edit_message, meeting_error, meeting_move_down, meeting_move_up,
    meeting_open_form, meeting_order_message, meeting_path, meeting_remove, meeting_render_form,
    meeting_render_message, meeting_revision, meeting_section_form, meeting_section_picker, meetings, mo, selected_entries,
):
    _pages = []
    if meeting_data:
        for _section in meeting_data['sections']:
            if not _section.get('visible', True):
                continue
            _parts = [mo.md('## ' + _section['title']), mo.md(meeting_bodies[_section['id']])]
            for _key in _section.get('artifacts', []):
                _entry = meeting_data['artifacts'][_key]
                _picture = next((_path for _path in _entry['files'].values() if _path.endswith(('.png', '.jpg', '.jpeg'))), None)
                _table = _entry.get('display', {}).get('plot_type', 'table' if _entry.get('kind') in
                    {'table', 'descriptive', 'descriptive_table', 'sample_composition'} else 'figure') == 'table'
                _parts.append(mo.md(meetings.table_markdown(_entry)) if _table or not _picture
                              else mo.image(meetings.bundled_path(meeting_path, _picture), alt=_entry['title']))
                _parts.append(mo.md(meetings.artifact_notes(_entry)))
            if _section.get('caption'):
                _parts.append(mo.md(_section['caption']))
            _pages.append(mo.vstack(_parts))
    _preview = mo.vstack(_pages) if _pages else mo.md('資料を作成するか、保存済みの資料を開いてください。')
    _outline = [{'順番': _index + 1, '見出し': _row['title'], '表示': _row.get('visible', True),
                 '図表': ', '.join(_row.get('artifacts', []))} for _index, _row in enumerate(meeting_data['sections'])] if meeting_data else []
    _editions = '\n'.join('- [' + _row['kind'] + '](' + _row['url'] + ') · ' + _row.get('source_revision', '')[:12]
                         for _row in meeting_data.get('editions', [])) if meeting_data else ''
    meeting_panel = mo.vstack([
        mo.accordion({'資料の新規作成': mo.vstack([
            mo.md('ギャラリーで選択した図表: ' + ', '.join(_entry['title'] for _entry in selected_entries)),
            meeting_create_form, meeting_creation_message])}),
        meeting_open_form, mo.callout(meeting_error, kind='danger') if meeting_error else mo.md(''),
        mo.ui.table(_outline, selection=None, show_column_summaries=False, show_data_types=False),
        mo.hstack([mo.vstack([meeting_section_picker, meeting_section_form, meeting_edit_message,
            mo.hstack([meeting_move_up, meeting_move_down]), meeting_remove, meeting_order_message,
            mo.accordion({'スライドの追加': mo.vstack([meeting_add_form, meeting_add_message])})]), _preview], widths=[1, 2], align='start'),
        meeting_render_form, meeting_render_message, meeting_download,
        mo.md('### クラウドで編集\nGitHub の content.md で本文、meeting.json で順序・表示・図表配置を変更します。\n\n'
              '公開する資料は cloud_export を true にして GitHub に保存すると、変更された資料を Actions が描画します。\n\n' + _editions),
        mo.md('資料の版: `' + meeting_revision[:12] + '`') if meeting_data else mo.md(''),
    ])
    return (meeting_panel,)


@app.cell
def _(mo):
    artifact_search_form = mo.ui.dictionary({
        'query': mo.ui.text(label='ID・名称・研究課題・元の結果・仕様・期間', full_width=True),
        'kind': mo.ui.dropdown({'すべて': '', 'コード': 'code', 'データ': 'data', '結果': 'result',
                               'モデル': 'model', '文書・会議資料': 'document', '仕様': 'specification',
                               '図': 'figure', '表': 'table'}, value='すべて', label='種類'),
        'history': mo.ui.checkbox(label='過去の保存版を含める'),
    }).form(submit_button_label='成果物を検索')
    return (artifact_search_form,)


@app.cell
def _(artifact_search_form, artifacts, load_error, mo, options, refresh_button, refresh_get, registry_path, root):
    refresh_button.value
    refresh_get()
    _selection = artifact_search_form.value or {'query': '', 'kind': '', 'history': False}
    try:
        _meetings = [options.meeting] if (root / options.meeting / 'meeting.json').is_file() else []
        artifact_matches = artifacts.artifact_catalog(root, [] if load_error else [registry_path],
            store=options.store, query=_selection['query'], filters={'kind': _selection['kind']},
            include_history=_selection['history'], meeting_paths=_meetings)
        artifact_search_error = ''
    except (ValueError, TypeError, KeyError, OSError) as _error:
        artifact_matches = []
        artifact_search_error = str(_error)
    artifact_table = mo.ui.table([
        {'index': _index, '名称': _item['title'], '種類': _item['kind'], '保存先': _item['path'] or _item['id'],
         '版': (_item['content_version'] or '')[:12], '版の位置': ', '.join(_item['version_roles']),
         '結果 ID': ', '.join(_item['result_ids'])}
        for _index, _item in enumerate(artifact_matches)], selection='multi', page_size=12,
        show_column_summaries=False, show_data_types=False)
    return artifact_matches, artifact_search_error, artifact_table


@app.cell
def _(artifact_matches, artifact_search_error, artifact_search_form, artifact_table, json, mo):
    _selected = [artifact_matches[_row['index']] for _row in artifact_table.value]
    artifact_panel = mo.vstack([
        artifact_search_form,
        mo.callout(artifact_search_error, kind='danger') if artifact_search_error else mo.md(''),
        artifact_table,
        mo.md('```json\n' + json.dumps(_selected, ensure_ascii=False, indent=2) + '\n```') if _selected else mo.md(''),
    ])
    return (artifact_panel,)


@app.cell
def _(artifact_panel, editor_panel, gallery_panel, header, interpretation_panel, meeting_panel, mo, project_panel):
    mo.vstack([header, mo.ui.tabs({'結果ギャラリー': gallery_panel,
                                 '成果物を探す': artifact_panel,
                                 '表示編集': editor_panel,
                                 '解釈と来歴': interpretation_panel,
                                 '研究計画と作業': project_panel,
                                 '会議資料': meeting_panel})])
    return


if __name__ == '__main__':
    app.run()
