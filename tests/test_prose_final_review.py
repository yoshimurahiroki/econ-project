import base64, importlib.util, json, os, shlex, shutil, subprocess, sys, tempfile
from contextlib import contextmanager
from pathlib import Path

root = Path(os.environ.get('ERS_TEST_PLUGIN_ROOT', Path(__file__).resolve().parent.parent)).resolve()
spec = importlib.util.spec_from_file_location('hooks', root / 'harness/codex_hooks.py')
hooks = importlib.util.module_from_spec(spec); spec.loader.exec_module(hooks)
gate = hooks.gate
@contextmanager
def hook_tempdir():
    path = Path(tempfile.mkdtemp())
    assert path.resolve().parent == Path(tempfile.gettempdir()).resolve()
    try:
        yield str(path)
    finally:
        shutil.rmtree(gate.windows_extended_path(path) if os.name == 'nt' else path)
text = 'First paragraph explains the data.\n\nSecond paragraph describes an observed condition.'
with hook_tempdir() as temp:
    directory = Path(temp)
    context = directory/'context.json'; context.write_text(json.dumps({'cwd':str(root)}),encoding='utf-8')
    membership = directory/'turns'/ (gate.sha(b'turn-a')+'.json')
    membership.parent.mkdir(); membership.write_text('{}')
    event = {'turn_id':'turn-a', 'last_assistant_message':text, 'stop_hook_active':False}
    missing = hooks._review_final_prose(event, root, directory)
    assert missing['decision'] == 'block' and 'semantic expression review' in missing['reason']
    parts = gate.prose_parts(text)
    rows = [{'text_sha256':gate.sha(p.encode()), 'meaning':'The observed data and condition',
             'rhetorical_role':'Direct explanation of the source',
             'expression_assessment':'States the actual condition with direct wording',
             'facts_preserved':'The observed data remain unchanged', 'verdict':'pass'} for p in parts]
    review = {'text_sha256':gate.sha(text.encode()), 'parts':rows}
    receipt = directory/'prose-reviews'/gate.sha(b'turn-a')/(gate.sha(text.encode())+'.json')
    payload = base64.b64encode(json.dumps({'text':text,'review':review}).encode()).decode()
    result = subprocess.run([sys.executable, str(root/'harness/codex_hooks.py'), '--root',str(root),
                             'record-prose-review','--hook-context',str(context),'--turn-id','turn-a',
                             '--payload-base64',payload],
                            capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert hooks._review_final_prose(event,root,directory) is None
    event['last_assistant_message'] += ' Revised.'
    assert hooks._review_final_prose(event,root,directory)['decision'] == 'block'
    incomplete = {'text_sha256':gate.sha(text.encode()),'parts':rows[:1]}
    try:
        gate.validate_semantic_review(text,incomplete)
    except ValueError:
        pass
    else:
        raise AssertionError('incomplete review passed')
    rows[0]['verdict'] = 'fail'
    try:
        gate.validate_semantic_review(text,review)
    except ValueError:
        pass
    else:
        raise AssertionError('failed review passed')
print('Required review, exact text binding, coverage and failed verdict checks passed.')

with hook_tempdir() as temp:
    env = {**os.environ, 'PLUGIN_ROOT':str(root), 'PLUGIN_DATA':temp}
    base = {'session_id':'semantic-hook-test', 'turn_id':'turn-b', 'cwd':str(root)}
    config = json.loads((root/'hooks/hooks.json').read_text(encoding='utf-8'))
    def invoke(name, **kw):
        event = {**base, 'hook_event_name':name, **kw}
        command = (config['hooks'][name][0]['hooks'][0]['commandWindows'] if os.name == 'nt'
                   else [sys.executable, str(root/'hooks/check.py'), name])
        result = subprocess.run(command, shell=os.name == 'nt', input=json.dumps(event),
                                text=True, capture_output=True, env=env)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    started = invoke('UserPromptSubmit', prompt='Explain the source data.')
    assert not started.get('decision') == 'block', started
    final = 'The source records monthly claims.'
    stopped = invoke('Stop', stop_hook_active=False, last_assistant_message=final)
    assert stopped.get('decision') == 'block' and 'semantic expression review' in stopped.get('reason',''), stopped
    data_root = Path(gate.windows_extended_path(temp)) if os.name == 'nt' else Path(temp)
    active = hooks._active_directory({**base, 'hook_event_name':'Stop'}, data_root)
    receipt = active/'prose-reviews'/gate.sha(b'turn-b')/(gate.sha(final.encode())+'.json')
    review = {'text_sha256':gate.sha(final.encode()), 'parts':[{
        'text_sha256':gate.sha(final.encode()), 'meaning':'Monthly claims are recorded by the source',
        'rhetorical_role':'Direct description of the input data',
        'expression_assessment':'Reports the actual data directly',
        'facts_preserved':'The period and measurement remain unchanged', 'verdict':'pass'}]}
    payload = base64.b64encode(json.dumps({'text':final,'review':review}).encode()).decode()
    command = [sys.executable,str(root/'harness/codex_hooks.py'),'--root',str(root),
        'record-prose-review','--hook-context',str(active/'context.json'),'--turn-id','turn-b',
        '--payload-base64',payload]
    preflight = invoke('PreToolUse', tool_name='exec_command',
        tool_input={'cmd':shlex.join(command)}, tool_use_id='review-control')
    assert preflight == {}, preflight
    outside = command.copy()
    outside[outside.index('--turn-id') + 1] = 'another-turn'
    denied = invoke('PreToolUse', tool_name='exec_command',
        tool_input={'cmd':shlex.join(outside)}, tool_use_id='bad-review-control')
    assert denied['hookSpecificOutput']['permissionDecision'] == 'deny', denied
    recorded = subprocess.run(command,capture_output=True,text=True)
    assert recorded.returncode == 0, recorded.stderr
    postflight = invoke('PostToolUse', tool_name='exec_command',
        tool_input={'cmd':shlex.join(command)}, tool_response={'exit_code':0},
        tool_use_id='review-control')
    assert postflight.get('decision') != 'block', postflight
    complete = invoke('Stop', stop_hook_active=True, last_assistant_message=final)
    assert complete == {}, complete
print('Host event path requires and consumes the exact semantic review.')
