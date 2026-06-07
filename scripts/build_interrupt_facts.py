#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path
from collections import defaultdict


def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def infer_var_accesses(functions, global_vars, switches):
    # By-function switch mapping
    switches_by_func = defaultdict(list)
    for sw in switches:
        switches_by_func[sw.get('function')].append(sw)

    names = [g['name'] for g in global_vars]
    accesses = []
    per_var_contexts = defaultdict(set)
    for category in ('interrupt_functions', 'main_functions', 'regular_functions'):
        for fn in functions.get(category, []):
            body = fn.get('function_body', '') or ''
            context = fn.get('type', category.replace('_functions', ''))
            fn_name = fn['name']
            fn_start_line = fn.get('line_number', 0)
            
            fn_switches = sorted(switches_by_func.get(fn_name, []), key=lambda x: x.get('line_number', 0))

            for var in names:
                if var not in body:
                    continue
                write_patterns = [
                    rf'\b{re.escape(var)}\s*(\[[^\]]+\])?\s*=',
                    rf'\b{re.escape(var)}\s*(\[[^\]]+\])?\s*\+\+',
                    rf'\+\+\s*{re.escape(var)}',
                    rf'\b{re.escape(var)}\s*(\[[^\]]+\])?\s*--',
                    rf'--\s*{re.escape(var)}',
                ]
                
                # Analyze per line to map out local scope guards
                lines = body.splitlines()
                
                for i, ln in enumerate(lines):
                    if var not in ln:
                        continue
                    
                    curr_line = fn_start_line + i
                    is_guarded = False
                    is_disabled = False
                    for sw in fn_switches:
                        if sw.get('line_number', 0) <= curr_line:
                            if sw.get('operation') == 'disable':
                                is_disabled = True
                            elif sw.get('operation') == 'enable':
                                is_disabled = False
                    
                    is_guarded = is_disabled
                    is_write = any(re.search(p, ln) for p in write_patterns)
                    acc_type = 'write' if is_write else 'read'
                    
                    accesses.append({
                        'function_name': fn_name,
                        'function_type': context,
                        'variable_name': var,
                        'access_type': acc_type,
                        'line_number': curr_line,
                        'is_guarded': is_guarded
                    })
                    per_var_contexts[var].add(context if context != 'interrupt' else fn_name)

    # Merge accesses (same function & var): if ANY occurance is NOT guarded, it is exposed to preemption
    merged_accesses = []
    access_guard_map = {}
    for acc in accesses:
        key = (acc['function_name'], acc['function_type'], acc['variable_name'], acc['access_type'])
        if key not in access_guard_map:
            access_guard_map[key] = acc['is_guarded']
        else:
            # Requires all instance of this variable access type in the function to be guarded
            access_guard_map[key] = access_guard_map[key] and acc['is_guarded']
            
    for (f_n, f_t, v, a_t), guarded in access_guard_map.items():
        merged_accesses.append({
            'function_name': f_n,
            'function_type': f_t,
            'variable_name': v,
            'access_type': a_t,
            'line_number': -1,
            'is_guarded': guarded
        })

    return merged_accesses, per_var_contexts


def build_relations(functions, switches, priorities, accesses):
    fn_by_name = {}
    for category in ('interrupt_functions', 'main_functions', 'regular_functions'):
        for fn in functions.get(category, []):
            fn_by_name[fn['name']] = fn

    interrupts = functions.get('interrupt_functions', [])
    mains = functions.get('main_functions', [])

    preemptions = []
    # main -> interrupt by default for all known ISRs 
    for main in mains:
        for isr in interrupts:
            preemptions.append({
                'src': main['name'],
                'dst': isr['name'],
                'reason': 'main_can_be_interrupted',
            })
            
    # priority-based ISR preemption with PLATFORM AWARENESS
    for a in interrupts:
        for b in interrupts:
            if a['name'] == b['name']:
                continue
                
            arch_a = a.get('architecture', 'Generic')
            arch_b = b.get('architecture', 'Generic')
            
            prio_a = a.get('priority', -1)
            prio_b = b.get('priority', -1)
            
            prio_a_val = int(prio_a) if isinstance(prio_a, str) and prio_a.lstrip('-').isdigit() else prio_a
            prio_b_val = int(prio_b) if isinstance(prio_b, str) and prio_b.lstrip('-').isdigit() else prio_b
            
            if prio_a_val is None: prio_a_val = -1
            if prio_b_val is None: prio_b_val = -1
            
            a_can_be_preempted_by_b = False
            
            # Assume ARM evaluates smaller numbers as higher priority
            if 'ARM' in arch_a.upper() or 'ARM' in arch_b.upper():
                if prio_b_val < prio_a_val:
                    a_can_be_preempted_by_b = True
            else:
                # Default/Generic: larger numbers mean higher priority
                if prio_b_val > prio_a_val:
                    a_can_be_preempted_by_b = True
                    
            if a_can_be_preempted_by_b:
                preemptions.append({
                    'src': a['name'],
                    'dst': b['name'],
                    'reason': 'higher_priority_interrupt',
                })

    switch_relations = []
    for sw in switches:
        targets = sw.get('mapped_targets') or sw.get('mapped_target_functions') or []
        for t in targets:
            switch_relations.append({
                'src_function': sw.get('function'),
                'line_number': sw.get('line_number'),
                'operation': sw.get('operation'),
                'target_interrupt': t,
            })

    # Prepare preemption lookup mapping
    can_preempt = defaultdict(set)
    for rel in preemptions:
        can_preempt[rel['src']].add(rel['dst'])

    accesses_by_var = defaultdict(list)
    for acc in accesses:
        accesses_by_var[acc['variable_name']].append(acc)

    cross_context = []
    cross_set = set()
    
    for var, items in accesses_by_var.items():
        for src_item in items:
            for dst_item in items:
                src_name = src_item['function_name']
                dst_name = dst_item['function_name']
                if src_name == dst_name:
                    continue
                    
                src_type = src_item['function_type']
                dst_type = dst_item['function_type']
                
                # Ignored if both operations are safely in generic code 
                # (although realistically if interrupted it could affect, normally we focus on ISR vs Main/Reg)
                if src_type == dst_type == 'regular':
                    continue
                    
                # 1. IntraProcGuards: Guard Check
                # If source scope explicitly disabled interrupts, it limits preemption window
                if src_item.get('is_guarded', False):
                    continue
                    
                # 2. CanPreempt: Feasibility Check
                can_preempt_flag = False
                if dst_name in can_preempt.get(src_name, set()):
                    can_preempt_flag = True
                else:
                    # Regular functions can fallback to being preempted by any ISR 
                    # if they are active within main thread (approx fallback)
                    if src_type == 'regular' and dst_type == 'interrupt':
                        can_preempt_flag = True
                        
                if not can_preempt_flag:
                    continue
                    
                cross_set.add((
                    var,
                    src_name, src_type, src_item['access_type'],
                    dst_name, dst_type, dst_item['access_type']
                ))

    for (var, s_fn, s_ty, s_acc, d_fn, d_ty, d_acc) in cross_set:
        cross_context.append({
            'variable_name': var,
            'src_function': s_fn,
            'src_type': s_ty,
            'src_access': s_acc,
            'dst_function': d_fn,
            'dst_type': d_ty,
            'dst_access': d_acc,
        })

    return {
        'preemptions': preemptions,
        'switch_relations': switch_relations,
        'cross_context_accesses': cross_context,
    }


def main(case_dir: str):
    case = Path(case_dir)
    analysis = case / 'improved_interrupt_analysis'
    functions = load_json(analysis / 'functions.json')
    switches = load_json(analysis / 'interrupt_switches.json')
    # If the switches are nested inside 'switches' key (it happens in some versions)
    # let's be safe.
    if isinstance(switches, dict) and "switches" in switches:
        switches = switches["switches"]
        
    priorities = load_json(analysis / 'interrupt_priorities.json')
    global_vars = load_json(analysis / 'global_variables.json')
    
    accesses, per_var_contexts = infer_var_accesses(functions, global_vars, switches)
    relations = build_relations(functions, switches, priorities, accesses)

    facts = {
        'case_path': str(case),
        'functions': functions,
        'interrupt_switches': switches,
        'interrupt_priorities': priorities,
        'global_variables': global_vars,
        'inferred_accesses': accesses,
        'shared_variables': [
            {
                'name': var,
                'contexts': sorted(ctxs),
            }
            for var, ctxs in sorted(per_var_contexts.items())
            if len(ctxs) >= 2 or any(c.startswith('svp_') for c in ctxs)
        ],
    }

    out_dir = analysis / 'interrupt_facts'
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / 'interrupt_facts.json', 'w', encoding='utf-8') as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)
    with open(out_dir / 'interrupt_relations.json', 'w', encoding='utf-8') as f:
        json.dump(relations, f, indent=2, ensure_ascii=False)

    print(out_dir / 'interrupt_facts.json')
    print(out_dir / 'interrupt_relations.json')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('usage: build_interrupt_facts.py <case_dir>')
        sys.exit(1)
    main(sys.argv[1])
