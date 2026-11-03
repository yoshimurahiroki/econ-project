#!/usr/bin/env python3
"""Normalize saved scientific results and generate existing research DAG stages."""
from __future__ import annotations
import argparse
import html
import json
import math
import os
import re
import sys
import shutil
import subprocess
import random
import csv
import tempfile
from pathlib import Path

import state
import research_evidence as evidence

NAME=re.compile(r'^[A-Za-z][A-Za-z0-9_-]*$')
FMT=re.compile(r'^(?:\.[0-9]{1,2})?[fge]$')
TOKEN=re.compile(r'\{\{stat:([A-Za-z][A-Za-z0-9_-]*)\}\}|\{\{(table|figure)\}\}')


def latex_assets(root, require_adapters=True):
    """Resolve canonical templates and generated adapters in each supported layout."""
    roots=[root/'tex',root/'.agents'/'tex']
    names={'paper_source':('paper','ecta_template.tex','ecta_template.tex'),
           'paper_class':('paper','econsocart.cls','econsocart.cls'),
           'paper_config':('paper','econsocart.cfg','econsocart.cfg'),
           'paper_style':('paper','ecta-fullname.bst','ecta-fullname.bst'),
           'slides_source':('slides','main.tex','main.tex'),
           'paper_adapter':('paper','pandoc_template.latex','paper_pandoc_template.latex'),
           'slides_adapter':('slides','pandoc_template.latex','slides_pandoc_template.latex')}
    assets={}
    for key,(folder,name,flat) in names.items():
        options=[p/folder/name for p in roots]+[root/flat,Path(__file__).resolve().parent.parent/'tex'/folder/name,Path(__file__).resolve().parent/flat]
        assets[key]=next((p.resolve() for p in options if p.is_file()),None)
        if assets[key] is None and (require_adapters or not key.endswith('_adapter')): raise ValueError('Missing LaTeX asset: '+key)
    builders=[root/'scripts/build_latex.py',root/'.agents'/'scripts/build_latex.py',root/'build_latex.py',Path(__file__).resolve().parent/'build_latex.py']
    assets['builder']=next((p.resolve() for p in builders if p.is_file()),None)
    if assets['builder'] is None: raise ValueError('Missing LaTeX build helper')
    return assets


def latex_adapter(source, kind):
    """Replace only content slots in the user-supplied template."""
    def replace_once(body, old, new):
        if body.count(old)!=1: raise ValueError('LaTeX template slot changed: '+kind)
        return body.replace(old,new,1)
    common=('$if(bibliography)$$else$\\let\\econbibstyle\\bibliographystyle\n'
            '\\renewcommand{\\bibliographystyle}[1]{}\n$endif$'
            '$common.latex()$\n$if(bibliography)$$else$\\let\\bibliographystyle\\econbibstyle\n$endif$'
            '$if(standalone-renderer)$\n$for(header-includes)$\n$header-includes$\n$endfor$\n$endif$\n')
    if kind=='paper':
        source=replace_once(source,'\\documentclass[ecta,nameyear,draft]{econsocart}', '\\RequirePackage{fontspec}\n\\def\\econselectedclass{$documentclass$}\n\\def\\econjournalclass{econsocart}\n\\ifx\\econselectedclass\\econjournalclass\n\\documentclass[ecta,nameyear,draft]{econsocart}\n\\else\n\\documentclass[$for(classoption)$$classoption$$sep$,$endfor$]{$documentclass$}\n\\fi')
        source=replace_once(source,'\\startlocaldefs',common+'\\newcounter{pandocauthor}\n\\newcommand{\\pandocauthor}[1]{\\stepcounter{pandocauthor}\\author[id=au\\arabic{pandocauthor},addressref={add1}]{\\fnms{}~\\snm{#1}\\ead[label=e\\arabic{pandocauthor}]{}}}\n\\ifx\\econselectedclass\\econjournalclass\n\\startlocaldefs')
        source=replace_once(source,'\\endlocaldefs','\\endlocaldefs\n\\fi')
        source=replace_once(source,'\\begin{frontmatter}','\\ifx\\econselectedclass\\econjournalclass\n\\begin{frontmatter}')
        source=replace_once(source,'\\end{frontmatter}', '\\end{frontmatter}\n\\else\n$if(title)$\\title{$title$}$endif$\n\\author{$for(author)$$author$$sep$ \\and $endfor$}\n$if(date)$\\date{$date$}$endif$\n$if(title)$\\maketitle$endif$\n$if(abstract)$\\begin{abstract}$abstract$\\end{abstract}$endif$\n$if(keywords)$\\noindent\\textbf{Keywords:} $for(keywords)$$keywords$$sep$, $endfor$$endif$\n\\fi')
        source=replace_once(source,'\\title{???}\n\\runtitle{???}', '$if(title)$\\title{$title$}\n\\runtitle{$title$}$endif$')
        source=replace_once(source,'\\author[id=au1,addressref={add1}]{\\fnms{}~\\snm{}\\ead[label=e1]{}}', '$for(author)$\\pandocauthor{$author$}\n$endfor$')
        source=replace_once(source,'\\begin{abstract}\n???\n\\end{abstract}', '$if(abstract)$\\begin{abstract}\n$abstract$\n\\end{abstract}$endif$')
        source=replace_once(source,'\\begin{keyword}\n\\kwd{???}\n\\kwd{???}\n\\end{keyword}', '$if(keywords)$\\begin{keyword}\n$for(keywords)$\\kwd{$keywords$}\n$endfor$\\end{keyword}$endif$')
        source=replace_once(source,'\\section{???}\n???', '$body$')
        source=replace_once(source,'\\bibliographystyle{ecta-fullname} % Style BST file', '% Bibliography style is set to ecta-fullname by the renderer.')
        source=replace_once(source,'\\bibliography{../bibliography}  % Bibliography file (usually \'*.bib\')', '$if(bibliography)$\\bibliography{$for(bibliography)$$bibliography$$sep$,$endfor$}$endif$')
    elif kind=='slides':
        source=replace_once(source,'\\usetheme[numbering=fraction]{metropolis}', '$if(theme)$\\usetheme{$theme$}$else$\\usetheme[numbering=fraction]{metropolis}$endif$')
        source=replace_once(source,'\\title[Footer title]{TITLE}\n\\subtitle{SUBTITLE}\n\\author{Author}\n\\institute{}\n\\date{\\today}', '$if(title)$\\title{$title$}$endif$\n$if(subtitle)$\\subtitle{$subtitle$}$endif$\n\\author{$for(author)$$author$$sep$ \\and $endfor$}\n$if(institute)$\\institute{$institute$}$endif$\n\\date{$if(date)$$date$$else$\\today$endif$}')
        source=replace_once(source,'\\usepackage{amsmath}\n\\begin{document}', '\\usepackage{amsmath}\n'+common+'\\AtBeginEnvironment{longtable}{\\footnotesize\\setlength{\\tabcolsep}{2pt}}\n\\begin{document}')
        start=source.index('\\begin{frame}{}'); end=source.index('\\appendix',start)
        source=source[:start]+'$body$\n\n'+source[end:]
        source=replace_once(source,'\\begin{frame}{References}', '$if(bibliography)$\\begin{frame}{References}')
        source=replace_once(source,'\\bibliography{../bibliography}  % Bibliography file (usually \'*.bib\')', '\\bibliography{$for(bibliography)$$bibliography$$sep$,$endfor$}')
        source=replace_once(source,'\\end{frame}\n\n\\end{document}', '\\end{frame}$endif$\n\n\\end{document}')
        source=replace_once(source,'\\bibliographystyle{../paper/ecta-fullname} % Style BST file', '% Bibliography style is set to ecta-fullname by the renderer.')
    else: raise ValueError('Unknown LaTeX template kind')
    return source


def explicit_latex_options(source,pandoc,target):
    """Read the document's own Pandoc/Quarto choices before selecting a default."""
    result=subprocess.run([pandoc,'-f','markdown','-t','json',str(source)],check=True,capture_output=True,text=True)
    meta=json.loads(result.stdout).get('meta',{})
    def unpack(value):
        if not isinstance(value,dict): return None
        kind,content=value.get('t'),value.get('c')
        if kind=='MetaString': return content
        if kind=='MetaBool': return content
        if kind=='MetaMap': return {k:unpack(v) for k,v in content.items()}
        if kind=='MetaList': return [unpack(v) for v in content]
        if kind=='MetaInlines':
            return ''.join(' ' if v.get('t') in ('Space','SoftBreak','LineBreak') else v.get('c','')
                           for v in content if isinstance(v,dict) and isinstance(v.get('c',''),str))
        return None
    values={k:unpack(v) for k,v in meta.items()}
    options={k:values[k] for k in ('documentclass','theme','template','classoption') if values.get(k)}
    if values.get('bibliography'): options['_bibliography']=values['bibliography']
    formats=values.get('format')
    if isinstance(formats,dict):
        selected=formats.get('beamer' if target=='slides' else 'pdf')
        if isinstance(selected,dict):
            options.update({k:selected[k] for k in ('documentclass','theme','template','classoption') if selected.get(k)})
    return options


def chosen_template(root, origin, value):
    candidate=Path(value)
    if candidate.is_absolute(): return candidate.resolve(strict=True)
    for base in (Path(origin).resolve().parent,root):
        found=base/candidate
        if found.is_file(): return found.resolve()
    raise ValueError('Missing document template: '+str(value))


def render_latex(root, source, figure_svg, figure_pdf, target, output, pandoc, python, pdf=False, origin=None):
    assets=latex_assets(root); adapter=assets[target+'_adapter']
    choices=explicit_latex_options(source,pandoc,target)
    choices.pop('_bibliography',None)
    if 'template' in choices:
        selected=chosen_template(root,origin or source,choices['template'])
        if selected==adapter: choices.pop('template')
        else: choices['template']=str(selected)
    if not choices and adapter.read_text(encoding='utf8')!=latex_adapter(assets[target+'_source'].read_text(encoding='utf8'),target):
        raise ValueError('Generated LaTeX adapter is stale')
    output=Path(output).resolve()
    with tempfile.TemporaryDirectory(prefix='research-latex-') as tmp:
        tmp=Path(tmp); manuscript=tmp/'input.qmd'; tex=tmp/'document.tex'
        manuscript.write_text(Path(source).read_text(encoding='utf8').replace(str(Path(figure_svg).resolve()),str(Path(figure_pdf).resolve())),encoding='utf8')
        env=os.environ.copy()
        directories=list(dict.fromkeys(str(assets[k].parent) for k in ('paper_class','paper_config','paper_style')))
        for key in ('TEXINPUTS','BSTINPUTS'):
            env[key]=os.pathsep.join(directories+[env.get(key,'')])
        env['BIBINPUTS']=os.pathsep.join([str(Path(origin or source).resolve().parent),str(root),env.get('BIBINPUTS','')])
        if choices:
            command=[pandoc,'-f','markdown',str(manuscript),'-s','-t','beamer' if target=='slides' else 'latex','-o',str(output if pdf else tex)]
            if pdf: command+=['--pdf-engine=lualatex']
            for key in ('documentclass','theme','classoption'):
                if key in choices:
                    values=choices[key] if isinstance(choices[key],list) else [choices[key]]
                    for value in values: command+=['-V',key+'='+str(value)]
            if 'template' in choices:
                command+=['--template',choices['template']]
            if target=='slides': command+=['--slide-level=1']
            subprocess.run(command,cwd=root,env=env,check=True)
            if not pdf: shutil.copyfile(tex,output)
            return
        command=[pandoc,'-f','markdown',str(manuscript),'-s','--natbib','-M','biblio-style=ecta-fullname','-V','standalone-renderer=true','--template',str(adapter),'-t','beamer' if target=='slides' else 'latex','-o',str(tex)]
        if target=='paper': command+=['-V','documentclass=econsocart']
        if target=='slides': command+=['--slide-level=1']
        subprocess.run(command,cwd=root,env=env,check=True)
        if pdf:
            subprocess.run([python,str(assets['builder']),str(tex)],cwd=root,env=env,check=True)
            shutil.copyfile(tex.with_suffix('.pdf'),output)
        else: shutil.copyfile(tex,output)


def load(path):
    return evidence.read_json(Path(path).read_bytes(),str(path))


def checked(root, path):
    return root / state.relative(root,path)


def ref(root,path):
    p=checked(root,path)
    return {'path':path,'sha256':state.digest(p)}


def validate_spec(root, spec):
    if not isinstance(spec,dict) or set(spec)-{'pipeline','sources','bindings','article_template','slides_template','figure','models'} or not {'pipeline','sources','bindings','article_template','slides_template','figure'}<=set(spec): raise ValueError('artifact specification has invalid fields')
    if not isinstance(spec['pipeline'],str) or not NAME.fullmatch(spec['pipeline']): raise ValueError('pipeline must be a simple name')
    if not isinstance(spec['sources'],list) or not spec['sources']: raise ValueError('at least one source is required')
    seen=set()
    for row in spec['sources']:
        if not isinstance(row,dict) or set(row)-{'id','result','specification','code','data','coefficient_units','expected_hashes','quantities'} or not {'id','result','code'}<=set(row): raise ValueError('source requires id, result and code; specification, data and coefficient_units are optional')
        name=row['id']
        if not isinstance(name,str) or not NAME.fullmatch(name) or name in seen: raise ValueError('source IDs must be distinct simple names')
        seen.add(name)
        for field in ('result','specification','code','data'):
            if field in row: checked(root,row[field])
        if not isinstance(row.get('coefficient_units',{}),dict) or not isinstance(row.get('expected_hashes',{}),dict) or not isinstance(row.get('quantities',{}),dict): raise ValueError('coefficient_units and expected_hashes must be objects')
        if any(k not in ('code','data','specification') or k not in row or not isinstance(v,str) or not re.fullmatch(r'[0-9a-f]{64}',v) for k,v in row.get('expected_hashes',{}).items()): raise ValueError('expected hashes must identify selected input files')
    if not isinstance(spec['bindings'],dict) or not spec['bindings']: raise ValueError('bindings must be nonempty')
    for name,b in spec['bindings'].items():
        if not NAME.fullmatch(name) or not isinstance(b,dict) or set(b)!={'key','unit','format','display_unit','label'} or any(not isinstance(v,str) or not v for v in b.values()) or not FMT.fullmatch(b['format']): raise ValueError('binding requires key, unit, format, display_unit and label')
    for path in (spec['article_template'],spec['slides_template']): checked(root,path)
    if any('.' not in b['key'] or b['key'].split('.',1)[0] not in seen for b in spec['bindings'].values()): raise ValueError('each binding must name a selected source and statistic')
    if not isinstance(spec['figure'],list) or not spec['figure'] or len(set(spec['figure']))!=len(spec['figure']) or set(spec['figure'])-set(spec['bindings']): raise ValueError('figure must select distinct binding names')
    if len({spec['bindings'][key]['unit'] for key in spec['figure']})!=1 or len({spec['bindings'][key]['display_unit'] for key in spec['figure']})!=1: raise ValueError('a figure must use a single common unit and display unit')
    models=spec.get('models',[])
    if not isinstance(models,list): raise ValueError('models must be a list')
    for model in models:
        if not isinstance(model,dict) or set(model)-{'id','source','equation','code_quote','residual_key','tolerance','judgment','parameters'} or not {'id','source','equation','code_quote','residual_key','tolerance','judgment'}<=set(model) or not NAME.fullmatch(model['id']) or model['source'] not in seen or not isinstance(model['equation'],str) or not model['equation'] or not isinstance(model['code_quote'],str) or not model['code_quote'] or not isinstance(model['residual_key'],list) or not model['residual_key'] or any(not isinstance(v,str) or not v for v in model['residual_key']) or type(model['tolerance']) not in (int,float) or not math.isfinite(model['tolerance']) or model['tolerance']<0: raise ValueError('invalid adopted model mapping')
        evidence.check_judgment(model['judgment'],'model judgment')
    for path in (spec['article_template'],spec['slides_template']):
        text=checked(root,path).read_text(encoding='utf-8')
        names={m.group(1) for m in TOKEN.finditer(text) if m.group(1)}
        if names-set(spec['bindings']): raise ValueError('template has an unknown statistic binding')
        rest=TOKEN.sub('',text)
        if any(token in rest for token in ('{{stat:', '{{table', '{{figure')): raise ValueError('malformed artifact placeholder')
        if not names: raise ValueError('each template must use at least one statistic')
    return spec


def normalize(root,spec,selected=None):
    if selected is not None and not selected <= {source['id'] for source in spec['sources']}: raise ValueError('unknown selected source')
    stats={}; records={}
    for source in spec['sources']:
        name=source['id']
        if selected is not None and name not in selected: continue
        result=load(checked(root,source['result']))
        if not isinstance(result,dict): raise ValueError('source result must be an object')
        refs={key:ref(root,source[key]) for key in ('result','specification','code','data') if key in source}
        provenance=result.get('provenance',result.get('inputs',{}))
        if not isinstance(provenance,dict): raise ValueError('result provenance must be an object')
        checks={}
        for ref_name, hash_names in {'specification':('spec_sha256','specification_sha256'),'data':('data_sha256',),'code':('script_sha256','code_sha256')}.items():
            claimed=next((provenance[k] for k in hash_names if k in provenance),None)
            if claimed is not None:
                if ref_name not in refs or refs[ref_name]['sha256']!=claimed: raise ValueError(f'{name}: {ref_name} does not match declared producer hash')
                checks[ref_name]='verified'
            elif ref_name in refs:
                expected=source.get('expected_hashes',{}).get(ref_name)
                if expected is None or refs[ref_name]['sha256']!=expected: raise ValueError(f'{name}: {ref_name} needs a matching owner-adopted hash')
                checks[ref_name]='owner-adopted hash; producer did not record a hash'
        own=result.get('statistics',{})
        if not isinstance(own,dict): raise ValueError('statistics must be an object')
        quantities={}
        def add(key,value,unit,source_key):
            if not isinstance(key,str) or not key or not isinstance(unit,str) or not unit or type(value) not in (int,float) or not math.isfinite(value): raise ValueError(f'{name}: invalid statistic {key}')
            item={'value':value,'unit':unit}
            if key in quantities and quantities[key]['statistic']!=item: raise ValueError(f'{name}: inconsistent statistic {key}')
            quantities[key]={'statistic':item,'source_key':source_key}
        for key,value in own.items():
            if not isinstance(value,dict) or set(value)!={'value','unit'}: raise ValueError(f'{name}: statistics must contain value and unit')
            add(key,value['value'],value['unit'],['statistics',key])
        for key,requested in source.get('quantities',{}).items():
            if not isinstance(requested,dict) or set(requested)!={'key','unit'}: raise ValueError('selected quantity requires source key and unit')
            add(key,evidence.lookup(result,requested['key'],'selected quantity'),requested['unit'],requested['key'])
        coef=result.get('coefficients',{}); ses=result.get('standard_errors',{}); units=source.get('coefficient_units',{})
        if not isinstance(coef,dict) or not isinstance(ses,dict): raise ValueError('coefficients and standard_errors must be objects')
        for key,value in coef.items():
            sname='coefficient.'+key
            unit=quantities.get(sname,{}).get('statistic',{}).get('unit',units.get(key))
            if unit is None: raise ValueError(f'{name}: coefficient unit required for {key}')
            add(sname,value,unit,['coefficients',key])
        for key,value in ses.items():
            sname='standard_error.'+key
            unit=quantities.get(sname,{}).get('statistic',{}).get('unit',units.get(key))
            if unit is None: raise ValueError(f'{name}: standard error unit required for {key}')
            add(sname,value,unit,['standard_errors',key])
        inference=result.get('inference',{}) or {}
        if isinstance(inference,dict):
            pvalues=inference.get('p_values',{})
            if not pvalues and 'pvalue' in inference and len(coef)==1: pvalues={next(iter(coef)):inference['pvalue']}
            if isinstance(pvalues,dict):
                for k,v in pvalues.items(): add('p_value.'+k,v,'probability',['inference','p_values',k] if 'p_values' in inference else ['inference','pvalue'])
            intervals=inference.get('confidence_intervals_95',{})
            if not intervals and 'confidence_interval_95' in inference and len(coef)==1: intervals={next(iter(coef)):inference['confidence_interval_95']}
            if isinstance(intervals,dict):
                for k,ends in intervals.items():
                    if not isinstance(ends,list) or len(ends)!=2: raise ValueError('confidence interval must have two endpoints')
                    unit=quantities.get('coefficient.'+k,{}).get('statistic',{}).get('unit')
                    for index,(which,v) in enumerate(zip(('lower','upper'),ends)):
                        if v is None: continue
                        add('confidence_95_'+which+'.'+k,v,unit,['inference','confidence_intervals_95',k,index] if 'confidence_intervals_95' in inference else ['inference','confidence_interval_95',index])
        reference=inference.get('reference') if isinstance(inference,dict) else None
        df=inference.get('degrees_of_freedom') if isinstance(inference,dict) else None
        need_wald=any(k in ses and ses[k]>0 and any(prefix+k not in quantities for prefix in ('p_value.','confidence_95_lower.','confidence_95_upper.')) for k in coef)
        if need_wald and reference in ('normal','Student t') and (reference=='normal' or type(df) in (int,float) and math.isfinite(df) and df>0):
            from scipy.stats import norm, t
            distribution=norm if reference=='normal' else t(df)
            critical=float(distribution.ppf(0.975))
            for k,value in coef.items():
                if k not in ses or ses[k]<=0: continue
                unit=quantities['coefficient.'+k]['statistic']['unit']; se=ses[k]
                if 'p_value.'+k not in quantities: add('p_value.'+k,float(2*distribution.sf(abs(value/se))),'probability',{'calculation':'two-sided Wald p-value','reference':reference,'degrees_of_freedom':df,'inputs':[['coefficients',k],['standard_errors',k]]})
                for which,sign in (('lower',-1),('upper',1)):
                    if 'confidence_95_'+which+'.'+k not in quantities: add('confidence_95_'+which+'.'+k,float(value+sign*critical*se),unit,{'calculation':'95% Wald confidence limit','reference':reference,'degrees_of_freedom':df,'inputs':[['coefficients',k],['standard_errors',k]]})
        observations=result.get('observations')
        if observations is not None and 'observations' not in quantities: add('observations',observations,'observations',['observations'])
        for key,value in quantities.items(): stats[name+'.'+key]=value['statistic']
        records[name]={'identity':{'model':result.get('model',result.get('method')),'specification':refs.get('specification',{}).get('sha256')},'references':refs,'hash_checks':checks,'method':result.get('method'),'model':result.get('model'),'engine':result.get('engine'),'versions':result.get('versions'),'adopted':result.get('adopted',result.get('definition')),'options':result.get('options',result.get('design')),'provenance':provenance,'quantity_origins':{k:v['source_key'] for k,v in quantities.items()},'source_result':result}
    for alias,b in spec['bindings'].items():
        if selected is not None and b['key'].split('.',1)[0] not in selected: continue
        if b['key'] not in stats or stats[b['key']]['unit']!=b['unit']: raise ValueError(f'binding {alias} does not match a registered statistic and unit')
    return {'schema':'research-artifact-registry-v1','statistics':stats,'records':records}


def merge_registries(paths):
    combined={'schema':'research-artifact-registry-v1','statistics':{},'records':{}}
    for path in paths:
        fragment=load(path)
        if fragment.get('schema')!='research-artifact-registry-v1': raise ValueError('invalid registry fragment')
        for key in ('statistics','records'):
            if set(combined[key]) & set(fragment[key]): raise ValueError('duplicate registry fragment identity')
            combined[key].update(fragment[key])
    return combined


def table(spec, registry):
    rows=['| Quantity | Estimate | Unit |','|---|---:|---|']
    for b in spec['bindings'].values():
        value=registry['statistics'][b['key']]['value']
        rows.append('| '+b['label'].replace('|','\\|')+' | '+format(value,b['format'])+' | '+b['display_unit'].replace('|','\\|')+' |')
    return '\n'.join(rows)+'\n'


def figure(spec, registry):
    selected=[spec['bindings'][k] for k in spec['figure']]
    values=[registry['statistics'][b['key']]['value'] for b in selected]
    lo=min(0,*values); hi=max(0,*values)
    if hi==lo: hi=lo+1
    width=720; height=90+55*len(values); scale=460/(hi-lo); zero=200+(0-lo)*scale
    rows=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">', '<rect width="100%" height="100%" fill="white"/>',f'<text x="200" y="25" font-family="sans-serif" font-size="15">{html.escape(selected[0]["display_unit"])}</text>',f'<line x1="{zero:.2f}" y1="35" x2="{zero:.2f}" y2="{height-20}" stroke="#555"/>']
    for i,(b,value) in enumerate(zip(selected,values)):
        y=55+i*55; end=200+(value-lo)*scale; left=min(zero,end); bar=abs(end-zero)
        rows += [f'<text x="190" y="{y+5}" text-anchor="end" font-family="sans-serif" font-size="14">{html.escape(b["label"])}</text>',f'<rect x="{left:.2f}" y="{y-14}" width="{bar:.2f}" height="20" fill="#247887"/>',f'<text x="{end+5:.2f}" y="{y+2}" font-family="sans-serif" font-size="13">{format(value,b["format"])}</text>']
    rows.append('</svg>')
    return '\n'.join(rows)+'\n'


def render(root,spec,registry,template,table_path,figure_path):
    raw=checked(root,template).read_text(encoding='utf-8'); parts=[]; captures=[]; length=0; cursor=0
    def append(x):
        nonlocal length
        parts.append(x); length+=len(x)
    for m in TOKEN.finditer(raw):
        append(raw[cursor:m.start()]); alias=m.group(1); special=m.group(2)
        if alias:
            b=spec['bindings'][alias]; item=registry['statistics'][b['key']]; value=format(item['value'],b['format']); start=length; append(value); stop=length; append(' '); ustart=length; append(b['display_unit']); uend=length
            captures.append({'id':alias+'-'+str(len(captures)+1),'alias':alias,'target':{'start':start,'end':stop,'quote':value},'unit_target':{'start':ustart,'end':uend,'quote':b['display_unit']}})
        elif special=='table': append(Path(table_path).read_text(encoding='utf-8'))
        else: append('![Selected quantities]('+str(Path(figure_path).resolve())+')')
        cursor=m.end()
    append(raw[cursor:]); return ''.join(parts),captures


def make_contract(root,spec,registry_path,manuscript_path,trace):
    registry_path=Path(registry_path).resolve().relative_to(root).as_posix(); manuscript_path=Path(manuscript_path).resolve().relative_to(root).as_posix()
    rows=[]
    for capture in trace:
        b=spec['bindings'][capture['alias']]
        rows.append({'id':capture['id'],'target':capture['target'],'unit_target':capture['unit_target'],'unit_display':b['display_unit'],'result':{**ref(root,registry_path),'identity_keys':{},'key':['statistics',b['key']],'unit':b['unit'],'format':b['format']}})
    return {'manuscript':ref(root,manuscript_path),'adopted':{},'numbers':rows}


def make_model_contracts(root,spec,registry_path,article_path):
    registry_file=Path(registry_path).resolve().relative_to(root).as_posix()
    article_file=Path(article_path).resolve().relative_to(root).as_posix()
    registry=load(root/registry_file); article=(root/article_file).read_text(encoding='utf8'); contracts=[]
    for model in spec.get('models',[]):
        name=model['source']; record=registry['records'][name]; identity=record['identity']
        if not all(isinstance(identity.get(k),str) and identity[k] for k in ('model','specification')): raise ValueError('model mapping needs a recorded model and selected specification')
        code_path=record['references']['code']['path']; code=(root/code_path).read_text(encoding='utf8')
        def span(body,quote):
            if body.count(quote)!=1: raise ValueError('model quote must occur exactly once')
            start=body.index(quote); return {'start':start,'end':start+len(quote),'quote':quote}
        mapping={'id':model['id'],'equation':span(article,model['equation']),'code':{**ref(root,code_path),'span':span(code,model['code_quote'])},'judgment':model['judgment'],'result':{**ref(root,registry_file),'identity_keys':{'model':['records',name,'identity','model'],'specification':['records',name,'identity','specification']},'residual_key':['records',name,'source_result',*model['residual_key']],'tolerance':model['tolerance']}}
        contract={'manuscript':ref(root,article_file),'adopted':identity,'models':[mapping]}
        parameter_rows=[]
        for param in model.get('parameters',[]):
            if not isinstance(param,dict) or set(param)!={'id','target','code_quote','spec_key','spec_unit','statistic'}: raise ValueError('invalid adopted parameter mapping')
            spec_ref=record['references'].get('specification');
            if not spec_ref: raise ValueError('parameter mapping needs a specification')
            spec_data=load(root/spec_ref['path']); fixed=evidence.lookup(spec_data,param['spec_key'],'parameter specification'); stat=registry['statistics'][param['statistic']]
            parameter_rows.append({'id':param['id'],'kind':'parameter','status':'derived','target':span(article,param['target']),'code':{**ref(root,code_path),'span':span(code,param['code_quote'])},'judgment':model['judgment'],'origin':{'specification':{**spec_ref,'key':param['spec_key'],'value':fixed,'unit':param['spec_unit']}},'result':{**ref(root,registry_file),'identity_keys':{'model':['records',name,'identity','model'],'specification':['records',name,'identity','specification']},'quantity':{'key':['statistics',param['statistic']],'value':stat['value'],'unit':stat['unit']}}})
        if parameter_rows: contract['mappings']=parameter_rows
        contracts.append({'contract':contract,'check':evidence.bind(contract,root)})
    return contracts


def manifest(root,spec_path,spec,python,pandoc,quarto):
    helper=Path(__file__).resolve().relative_to(root).as_posix()
    core=list(dict.fromkeys(Path(p).resolve().relative_to(root).as_posix() for p in (__file__,evidence.__file__,state.__file__,evidence.paragraph.__file__,state.gate.__file__)))
    H='{root}/'+helper; S='{root}/'+spec_path
    stages=[]; source_dependencies={}
    for source in spec['sources']:
        sid='source-'+source['id']; source_dependencies[sid]=['registry']
        inputs=list(dict.fromkeys([spec_path,*core,*[source[k] for k in ('result','specification','code','data') if k in source]]))
        stages.append({'id':sid,'inputs':inputs,'depends':{},'outputs':{'registry':'registry.json'},'argv':[python,H,'normalize','--root','{root}','--spec',S,'--source',source['id'],'--output','{out:registry}']})
    merge_args=sum((['--registry','{dep:'+sid+':registry}'] for sid in source_dependencies),[])
    stages.append({'id':'registry','inputs':[spec_path,*core],'depends':source_dependencies,'outputs':{'registry':'registry.json'},'argv':[python,H,'merge','--root','{root}','--spec',S,*merge_args,'--output','{out:registry}']})
    stages.append({'id':'table','inputs':[spec_path,*core],'depends':{'registry':['registry']},'outputs':{'table':'table.md'},'argv':[python,H,'table','--root','{root}','--spec',S,'--registry','{dep:registry:registry}','--output','{out:table}']})
    figure_names={spec['bindings'][name]['key'].split('.',1)[0] for name in spec['figure']}
    figure_deps={'source-'+name:['registry'] for name in sorted(figure_names)}
    figure_args=sum((['--registry','{dep:'+sid+':registry}'] for sid in figure_deps),[])
    stages.append({'id':'figure','inputs':[spec_path,*core],'depends':figure_deps,'outputs':{'figure':'figure.svg'},'argv':[python,H,'figure','--root','{root}','--spec',S,*figure_args,'--output','{out:figure}']})
    stages.append({'id':'figure-pdf','inputs':[],'depends':{'figure':['figure']},'outputs':{'figure':'figure.pdf'},'argv':['rsvg-convert','-f','pdf','-o','{out:figure}','{dep:figure:figure}'],'inherit_env':['PATH']})
    for stage,key,extension in [('article','article_template','qmd'),('slides','slides_template','qmd')]:
        stages.append({'id':stage,'inputs':[spec_path,spec[key],*core],'depends':{'registry':['registry'],'table':['table'],'figure':['figure']},'outputs':{'text':stage+'.'+extension,'trace':'trace.json'},'argv':[python,H,'render','--root','{root}','--spec',S,'--registry','{dep:registry:registry}','--template','{root}/'+spec[key],'--table','{dep:table:table}','--figure','{dep:figure:figure}','--output','{out:text}','--trace','{out:trace}']})
    stages.append({'id':'bindings','inputs':[spec_path,*core],'depends':{'registry':['registry'],'article':['text','trace'],'slides':['text','trace']},'outputs':{'article_contract':'article-contract.json','article_check':'article-check.json','slides_contract':'slides-contract.json','slides_check':'slides-check.json','model_contracts':'model-contracts.json'},'argv':[python,H,'bind-generated','--root','{root}','--spec',S,'--registry','{dep:registry:registry}','--article','{dep:article:text}','--article-trace','{dep:article:trace}','--slides','{dep:slides:text}','--slides-trace','{dep:slides:trace}','--article-contract','{out:article_contract}','--article-check','{out:article_check}','--slides-contract','{out:slides_contract}','--slides-check','{out:slides_check}','--model-contracts','{out:model_contracts}']})
    for sid,fmt,source in [('html','html','article'),('latex','latex','article'),('pdf','pdf','article'),('word','docx','article'),('slides-pdf','pdf','slides'),('presentation','pptx','slides')]:
        out={'html':'article.html','latex':'article.tex','pdf':'article.pdf','word':'article.docx','slides-html':'slides.html','slides-latex':'slides.tex','slides-pdf':'slides.pdf','slides-word':'slides.docx','presentation':'slides.pptx'}[sid]
        argv=[pandoc,'{dep:'+source+':text}','-s','-o','{out:artifact}']
        dependencies={source:['text'],'bindings':[source+'_check']+(['model_contracts'] if source=='article' else []),'figure':['figure']}
        inputs=[]
        if fmt=='html': argv+=['--embed-resources']
        elif fmt in ('pdf','latex'):
            target='slides' if source=='slides' else 'paper'
            assets=latex_assets(root)
            inputs=[assets[k].relative_to(root).as_posix() for k in (target+'_source',target+'_adapter','paper_class','paper_config','paper_style','builder')]
            content=checked(root,spec[source+'_template']).read_text(encoding='utf8')
            if content.startswith('---') and any(key in content.split('---',2)[1] for key in ('template','bibliography')):
                options=explicit_latex_options(checked(root,spec[source+'_template']),pandoc,target)
                custom=options.get('template')
                if custom:
                    chosen=chosen_template(root,checked(root,spec[source+'_template']),custom)
                    item=chosen.relative_to(root).as_posix()
                    if item not in inputs: inputs.append(item)
                refs=options.get('_bibliography',[])
                for bibliography in refs if isinstance(refs,list) else [refs]:
                    chosen=chosen_template(root,checked(root,spec[source+'_template']),bibliography)
                    item=chosen.relative_to(root).as_posix()
                    if item not in inputs: inputs.append(item)
            dependencies['figure-pdf']=['figure']
            argv=[python,H,'render-latex','--root','{root}','--spec',S,'--article','{dep:'+source+':text}','--template','{root}/'+spec[source+'_template'],'--figure','{dep:figure:figure}','--figure-pdf','{dep:figure-pdf:figure}','--target',target,'--pandoc',pandoc,'--python',python,'--output','{out:artifact}']
            if fmt=='pdf': argv+=['--pdf']
        elif fmt=='pptx': argv+=['-t','pptx','--slide-level=1']
        tex_cache=root/'.agents'/'cache'/'research-artifacts-tex'
        env={'TEXMFCACHE':str(tex_cache),'TEXMFVAR':str(tex_cache)} if fmt=='pdf' else {}
        stages.append({'id':sid,'inputs':inputs,'depends':dependencies,'outputs':{'artifact':out},'argv':argv,'env':env,'inherit_env':[k for k in ('PATH','HOME','TEXMFHOME','TEXMFCONFIG','TEXMFOUTPUT') if k in os.environ]})
    for sid,source,qformat in [('quarto','article','html')]:
        stages.append({'id':sid,'inputs':[spec_path,*core],'depends':{source:['text'],'bindings':[source+'_check']+(['model_contracts'] if source=='article' else []),'figure':['figure']},'outputs':{'artifact':sid+'.html','runtime':'quarto-runtime.json'},'argv':[python,H,'quarto-render','--root','{root}','--spec',S,'--article','{dep:'+source+':text}','--quarto',quarto,'--quarto-format',qformat,'--output','{out:artifact}','--engine','{out:runtime}'],'inherit_env':[k for k in ('PATH','HOME','XDG_CACHE_HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','QUARTO_CONDA_PREFIX','QUARTO_SHARE_PATH','QUARTO_DENO','QUARTO_DART_SASS','QUARTO_PANDOC','QUARTO_TYPST','QUARTO_DENO_DOM','QUARTO_ESBUILD','QUARTO_PYTHON') if k in os.environ]})
    return {'pipeline':spec['pipeline'],'stages':stages}


def example(root,output,python,pandoc,quarto):
    """Execute a seeded IV and search example and prepare its real DAG."""
    if any(not x or not Path(x).is_absolute() for x in (python,pandoc,quarto)): raise ValueError('example requires absolute Python, Pandoc and Quarto paths')
    out=Path(output); out=(out if out.is_absolute() else root/out).resolve()
    rel=out.relative_to(root).as_posix()
    causal=next((p for p in (root/'skills/econ-data/scripts/research_causal.py',root/'research_causal.py') if p.is_file()),None)
    markets=next((p for p in (root/'skills/econ-data/scripts/research_markets.py',root/'research_markets.py') if p.is_file()),None)
    if causal is None or markets is None: raise ValueError('example needs the installed causal and market model scripts')
    out.mkdir(parents=True,exist_ok=False)
    rng=random.Random(20261101)
    with (out/'sample.csv').open('w',newline='',encoding='utf8') as stream:
        writer=csv.writer(stream); writer.writerow(['id','x','d','z','z2','y'])
        for i in range(1200):
            x,z,z2,error,noise=(rng.gauss(0,1) for _ in range(5)); d=.8*z+.7*z2+.6*error+noise; writer.writerow([str(i),x,d,z,z2,1+1.5*d+.5*x+error])
    iv={'method':'iv_gmm','data':'sample.csv','id':'id','outcome':'y','regressors':['x'],'endogenous':['d'],'instruments':['z','z2'],'population':'seeded simulated units','period':'simulation','unit':'outcome units','estimand':'effect of endogenous treatment','identification':'independent excluded instruments and independent units','assignment':'independent simulated units','inference':{'type':'robust'},'options':{}}
    search={'model':'search','baseline':{'offers':3,'search_cost':.08,'outside_option':0.0},'scenario':{'offers':3,'search_cost':.02,'outside_option':0.0},'unit':'model units','sources':[{'kind':'synthetic','description':'Uniform offers and full recall'}]}
    state.save(out/'iv-spec.json',iv); state.save(out/'search-spec.json',search)
    env=os.environ.copy(); env.update({'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
    for script,sp,res in ((causal,'iv-spec.json','iv-result.json'),(markets,'search-spec.json','search-result.json')):
        proc=subprocess.run([python,str(script),'run',str(out/sp),'--output',str(out/res)],env=env,text=True,capture_output=True)
        if proc.returncode: raise ValueError('example producer failed: '+proc.stderr[-2000:])
    article="""---
title: "Independent synthetic comparisons"
---

The IV treatment effect is {{stat:effect}}; its standard error is {{stat:se}}.

With independent uniform offers on [0,1], full recall and search cost c in [0,1/2], the reservation threshold z satisfies `c = (1-z)^2 / 2`. Its value is {{stat:threshold}}. Expected net surplus is {{stat:surplus}}.

{{table}}

{{figure}}
"""
    slides="""% Independent synthetic comparisons

# IV treatment effect

The estimate is {{stat:effect}}; its standard error is {{stat:se}}.

{{figure}}

# Consumer search

The reservation threshold is {{stat:threshold}} and expected net surplus is {{stat:surplus}}.

{{table}}
"""
    (out/'article.qmd').write_text(article,encoding='utf8'); (out/'slides.qmd').write_text(slides,encoding='utf8')
    def binding(key,unit,label): return {'key':key,'unit':unit,'display_unit':unit,'format':'.3f','label':label}
    ivunit='outcome units per one unit of d'; zunit='dimensionless utility normalized to [0,1]'
    config={'pipeline':'artifact-example','sources':[{'id':'iv','result':rel+'/iv-result.json','specification':rel+'/iv-spec.json','data':rel+'/sample.csv','code':causal.relative_to(root).as_posix(),'expected_hashes':{'code':state.digest(causal)}},{'id':'search','result':rel+'/search-result.json','specification':rel+'/search-spec.json','code':markets.relative_to(root).as_posix(),'expected_hashes':{'code':state.digest(markets)},'quantities':{'reservation_value':{'key':['baseline','reservation_value'],'unit':zunit}}}], 'bindings':{'effect':binding('iv.coefficient.d',ivunit,'IV effect'),'se':binding('iv.standard_error.d',ivunit,'Standard error'),'lower':binding('iv.confidence_95_lower.d',ivunit,'Lower 95% limit'),'upper':binding('iv.confidence_95_upper.d',ivunit,'Upper 95% limit'),'threshold':binding('search.reservation_value',zunit,'Search threshold'),'surplus':binding('search.expected_net_surplus','model units','Search surplus')},'figure':['effect','lower','upper'],'article_template':rel+'/article.qmd','slides_template':rel+'/slides.qmd','models':[{'id':'search-reservation','source':'search','equation':'c = (1-z)^2 / 2','code_quote':'abs((1-z)**2/2-c)','residual_key':['baseline','reservation_equation_error'],'tolerance':1e-10,'judgment':{'reviewer':'example-author','decision':'supported','rationale':'The saved reservation equation, code and residual agree.'},'parameters':[{'id':'search-threshold','target':'reservation threshold z','code_quote':'z = 1-math.sqrt(2*c)','spec_key':['baseline','search_cost'],'spec_unit':zunit,'statistic':'search.reservation_value'}]}]}
    state.save(out/'artifact-spec.json',config); validate_spec(root,config)
    (root/'.agents'/'cache'/'research-artifacts-tex').mkdir(parents=True,exist_ok=True)
    state.save(out/'manifest.json',manifest(root,rel+'/artifact-spec.json',config,python,pandoc,quarto))
    print(json.dumps({'specification':rel+'/artifact-spec.json','manifest':rel+'/manifest.json','results':[rel+'/iv-result.json',rel+'/search-result.json']}))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('command',choices=['example','materialize','normalize','merge','table','figure','render','render-latex','generate-adapters','bind-generated','quarto-render']); p.add_argument('--root',required=True,type=Path); p.add_argument('--spec',type=Path); p.add_argument('--output',type=Path); p.add_argument('--registry',type=Path,action='append'); p.add_argument('--source'); p.add_argument('--template',type=Path); p.add_argument('--table',type=Path); p.add_argument('--figure',type=Path); p.add_argument('--figure-pdf',type=Path); p.add_argument('--target',choices=['paper','slides']); p.add_argument('--pdf',action='store_true'); p.add_argument('--trace',type=Path); p.add_argument('--python'); p.add_argument('--pandoc'); p.add_argument('--quarto'); p.add_argument('--quarto-format',choices=['html','revealjs'],default='html'); p.add_argument('--engine',type=Path);
    for k in ('article','article-trace','slides','slides-trace','article-contract','article-check','slides-contract','slides-check','model-contracts'): p.add_argument('--'+k,type=Path)
    a=p.parse_args(argv)
    try:
        root=a.root.resolve(strict=True)
        if a.command=='example':
            if not a.output: raise ValueError('example requires a new output directory')
            example(root,a.output,a.python,a.pandoc,a.quarto); return 0
        if a.command=='generate-adapters':
            assets=latex_assets(root,require_adapters=False)
            for kind in ('paper','slides'):
                source=assets[kind+'_source']
                destination=source.parent/('pandoc_template.latex' if source.parent.name==kind else kind+'_pandoc_template.latex')
                destination.write_text(latex_adapter(assets[kind+'_source'].read_text(encoding='utf8'),kind),encoding='utf8')
            return 0
        if not a.spec: raise ValueError('specification is required')
        sp=a.spec.resolve(strict=True); rel=sp.relative_to(root).as_posix(); spec=validate_spec(root,load(sp))
        if a.command=='materialize':
            if not a.output or not a.python or not a.pandoc or not a.quarto or any(not Path(x).is_absolute() for x in (a.python,a.pandoc,a.quarto)): raise ValueError('materialize requires output and absolute python, pandoc and quarto paths')
            (root/'.agents'/'cache'/'research-artifacts-tex').mkdir(parents=True,exist_ok=True)
            state.save(a.output,manifest(root,rel,spec,a.python,a.pandoc,a.quarto))
        elif a.command=='normalize': state.save(a.output,normalize(root,spec,{a.source} if a.source else None))
        elif a.command=='merge':
            registry=merge_registries(a.registry)
            for alias,b in spec['bindings'].items():
                if b['key'] not in registry['statistics'] or registry['statistics'][b['key']]['unit']!=b['unit']: raise ValueError(f'binding {alias} does not match registry')
            state.save(a.output,registry)
        elif a.command in ('table','figure'):
            registry=merge_registries(a.registry); a.output.write_text(table(spec,registry) if a.command=='table' else figure(spec,registry),encoding='utf8')
        elif a.command=='render-latex':
            if not all((a.article,a.figure,a.figure_pdf,a.target,a.output,a.python,a.pandoc)): raise ValueError('render-latex requires source, figure files, target and executables')
            render_latex(root,a.article,a.figure,a.figure_pdf,a.target,a.output,a.pandoc,a.python,a.pdf,a.template)
        elif a.command=='render':
            registry=merge_registries(a.registry); template=a.template.resolve().relative_to(root).as_posix(); text,trace=render(root,spec,registry,template,a.table,a.figure); a.output.write_text(text,encoding='utf8'); state.save(a.trace,trace)
        elif a.command=='quarto-render':
            if not a.quarto or not Path(a.quarto).is_absolute(): raise ValueError('quarto executable must be absolute')
            binary=Path(a.quarto).resolve(strict=True); digest=state.digest(binary)
            version=subprocess.run([str(binary),'--version'],capture_output=True,text=True,check=True).stdout.strip()
            with tempfile.TemporaryDirectory(prefix='artifact-quarto-') as tmp:
                source=Path(tmp)/'article.qmd'; shutil.copyfile(a.article,source)
                subprocess.run([str(binary),'render','article.qmd','--to',a.quarto_format,'--output','quarto.html','-M','embed-resources:true','--no-execute','--quiet'],cwd=tmp,check=True)
                if state.digest(binary)!=digest: raise ValueError('Quarto changed during rendering')
                shutil.copyfile(Path(tmp)/'quarto.html',a.output)
            state.save(a.engine,{'executable':str(binary),'sha256':digest,'version':version})
        else:
            for manuscript,trace,contract_out,check_out in ((a.article,a.article_trace,a.article_contract,a.article_check),(a.slides,a.slides_trace,a.slides_contract,a.slides_check)):
                contract=make_contract(root,spec,a.registry[0],manuscript,load(trace)); result=evidence.bind(contract,root); state.save(contract_out,contract); state.save(check_out,result)
            state.save(a.model_contracts,make_model_contracts(root,spec,a.registry[0],a.article))
        return 0
    except (ValueError,TypeError,KeyError,OSError,AttributeError,ImportError,subprocess.CalledProcessError,evidence.EvidenceError) as exc:
        print('research_artifacts: '+str(exc),file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
