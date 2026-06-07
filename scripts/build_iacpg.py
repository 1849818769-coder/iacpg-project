#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {'g': 'http://graphml.graphdrawing.org/xmlns'}
ET.register_namespace('', NS['g'])
ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')

ROOT = Path(__file__).resolve().parents[1]
JDK = os.environ.get('JAVA_HOME', '')
def find_joern_tool(tool_name):
    # Try environment variable
    env_var = tool_name.upper().replace('-', '_')
    path_from_env = os.environ.get(env_var)
    if path_from_env and os.path.isfile(path_from_env):
        return path_from_env
        
    # Try standard PATH
    path_from_which = shutil.which(tool_name)
    if path_from_which:
        return path_from_which
        
    # Try resolving via 'joern' command (symlinks usually point to /opt/joern-cli/joern)
    joern_path = shutil.which('joern')
    if joern_path:
        real_joern_path = os.path.realpath(joern_path)
        joern_dir = os.path.dirname(real_joern_path)
        tool_in_joern_dir = os.path.join(joern_dir, tool_name)
        if os.path.isfile(tool_in_joern_dir):
            return tool_in_joern_dir
            
    return None

JOERN_PARSE = find_joern_tool('joern-parse')
JOERN_EXPORT = find_joern_tool('joern-export')


def sh(cmd, cwd=None):
    env = os.environ.copy()
    if JDK:
        env['JAVA_HOME'] = JDK
        env['PATH'] = f"{Path(JDK) / 'bin'}:" + env.get('PATH', '')
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def require_tool(path_or_name, label):
    if not path_or_name:
        raise SystemExit(f'{label} not found in PATH; set {label.upper().replace("-", "_")} or update PATH')
    return path_or_name


def load_json(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def ensure_keys(root, graph):
    def existing_key_ids():
        return {k.attrib.get('id') for k in root.findall('g:key', NS)}

    wanted = [
        ('labelV', 'node', 'labelV', 'string'),
        ('labelE', 'edge', 'labelE', 'string'),
        ('node__IACPG__KIND', 'node', 'KIND', 'string'),
        ('node__IACPG__NAME', 'node', 'NAME', 'string'),
        ('node__IACPG__TYPE', 'node', 'TYPE', 'string'),
        ('node__IACPG__LINE', 'node', 'LINE', 'string'),
        ('node__IACPG__JSON', 'node', 'JSON', 'string'),
        ('edge__IACPG__TYPE', 'edge', 'TYPE', 'string'),
    ]
    ids = existing_key_ids()
    for kid, scope, name, typ in wanted:
        if kid in ids:
            continue
        elem = ET.Element(f"{{{NS['g']}}}key", id=kid, **{'for': scope, 'attr.name': name, 'attr.type': typ})
        root.insert(0, elem)


def data_elem(key, text):
    d = ET.Element(f"{{{NS['g']}}}data", key=key)
    d.text = str(text)
    return d


def make_node(node_id, label, **fields):
    n = ET.Element(f"{{{NS['g']}}}node", id=str(node_id))
    n.append(data_elem('labelV', label))
    for k, v in fields.items():
        n.append(data_elem(k, v))
    return n


def make_edge(src, dst, label, etype=None):
    e = ET.Element(f"{{{NS['g']}}}edge", source=str(src), target=str(dst))
    e.append(data_elem('labelE', label))
    if etype:
        e.append(data_elem('edge__IACPG__TYPE', etype))
    return e


def find_method_node_id(method_xml: Path, method_name: str):
    tree = ET.parse(method_xml)
    root = tree.getroot()
    for node in root.findall('.//g:node', NS):
        label = node.find("g:data[@key='labelV']", NS)
        if label is None or label.text != 'METHOD':
            continue
        name = node.find("g:data[@key='node__METHOD__NAME']", NS)
        if name is not None and name.text == method_name:
            return node.attrib['id']
    return None


def main(case_dir: str):
    joern_parse = require_tool(JOERN_PARSE, 'joern-parse')
    joern_export = require_tool(JOERN_EXPORT, 'joern-export')

    case = Path(case_dir).resolve()
    analysis = case / 'improved_interrupt_analysis'
    facts_dir = analysis / 'interrupt_facts'
    if not (facts_dir / 'interrupt_facts.json').exists():
        raise SystemExit('interrupt_facts.json missing; run build_interrupt_facts.py first')

    work_dir = analysis / 'iacpg_artifacts'
    work_dir.mkdir(parents=True, exist_ok=True)
    cpg_bin = work_dir / 'cpg.bin'
    if not cpg_bin.exists():
        sh([joern_parse, str(case), '-o', str(cpg_bin)])

    facts = load_json(facts_dir / 'interrupt_facts.json')
    relations = load_json(facts_dir / 'interrupt_relations.json')

    graphml_path = work_dir / 'iacpg.graphml'
    root = ET.Element(f"{{{NS['g']}}}graphml", attrib={
        '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 'http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd'
    })
    graph = ET.SubElement(root, f"{{{NS['g']}}}graph", id='IACPG', edgedefault='directed')
    ensure_keys(root, graph)

    method_node_ids = {}
    function_defs = []
    for category in ('interrupt_functions', 'main_functions', 'regular_functions'):
        function_defs.extend(facts['functions'].get(category, []))

    for fn in function_defs:
        src_name = Path(fn['file_path']).name
        method_xml = work_dir / 'cpg_graphml' / src_name / f"{fn['name']}.xml" / 'export.xml'
        if not method_xml.exists():
            export_dir = work_dir / 'cpg_graphml'
            if not export_dir.exists():
                sh([joern_export, str(cpg_bin), '--repr', 'cpg', '--format', 'graphml', '-o', str(export_dir)])
        method_id = find_method_node_id(method_xml, fn['name'])
        if method_id is None:
            method_id = f"method::{fn['name']}"
        method_node_ids[fn['name']] = method_id
        n = make_node(
            method_id,
            'METHOD',
            node__IACPG__KIND='METHOD',
            node__IACPG__NAME=fn['name'],
            node__IACPG__TYPE=fn.get('type', category.replace('_functions', '')),
            node__IACPG__LINE=fn.get('line_number', ''),
            node__IACPG__JSON=json.dumps(fn, ensure_ascii=False),
        )
        graph.append(n)

    shared_var_nodes = {}
    for gv in facts.get('global_variables', []):
        var_name = gv['name']
        nid = f"sharedvar::{var_name}"
        shared_var_nodes[var_name] = nid
        graph.append(make_node(nid, 'IACPG_SHARED_VAR', node__IACPG__KIND='SHARED_VAR', node__IACPG__NAME=var_name, node__IACPG__TYPE=gv.get('type',''), node__IACPG__LINE=gv.get('line_number',''), node__IACPG__JSON=json.dumps(gv, ensure_ascii=False)))

    for fn in function_defs:
        ftype = fn.get('type') or 'regular'
        tag_id = f"tag::{fn['name']}::{ftype}"
        graph.append(make_node(tag_id, 'IACPG_TAG', node__IACPG__KIND='TAG', node__IACPG__NAME=fn['name'], node__IACPG__TYPE=ftype, node__IACPG__LINE=fn.get('line_number',''), node__IACPG__JSON=json.dumps({'tag': ftype}, ensure_ascii=False)))
        graph.append(make_edge(method_node_ids[fn['name']], tag_id, 'HAS_INTERRUPT_ROLE', 'HAS_INTERRUPT_ROLE'))

    for rel in relations.get('preemptions', []):
        src = method_node_ids.get(rel['src'])
        dst = method_node_ids.get(rel['dst'])
        if src and dst:
            graph.append(make_edge(src, dst, 'INTERRUPT_PREEMPTS', rel['reason']))

    for sw in facts.get('interrupt_switches', []):
        sw_id = f"switch::{sw['function']}::{sw['line_number']}::{sw['operation']}"
        graph.append(make_node(sw_id, 'IACPG_SWITCH', node__IACPG__KIND='SWITCH', node__IACPG__NAME=sw.get('code', ''), node__IACPG__TYPE=sw.get('operation', ''), node__IACPG__LINE=sw.get('line_number', ''), node__IACPG__JSON=json.dumps(sw, ensure_ascii=False)))
        if sw.get('function') in method_node_ids:
            graph.append(make_edge(method_node_ids[sw['function']], sw_id, 'CONTAINS_INTERRUPT_SWITCH', sw.get('operation', '')))
        for tgt in (sw.get('mapped_targets') or sw.get('mapped_target_functions') or []):
            if tgt in method_node_ids:
                graph.append(make_edge(sw_id, method_node_ids[tgt], 'ENABLES' if sw.get('operation') == 'enable' else 'DISABLES', sw.get('operation')))

    for acc in facts.get('inferred_accesses', []):
        fn = acc['function_name']
        var = acc['variable_name']
        if fn in method_node_ids and var in shared_var_nodes:
            graph.append(make_edge(method_node_ids[fn], shared_var_nodes[var], 'ACCESSES_SHARED_VAR', acc['access_type']))

    for rel in relations.get('cross_context_accesses', []):
        src = method_node_ids.get(rel['src_function'])
        dst = method_node_ids.get(rel['dst_function'])
        if src and dst:
            graph.append(make_edge(src, dst, 'POTENTIAL_CONCURRENCY_ON', rel['variable_name']))

    ET.ElementTree(root).write(graphml_path, encoding='utf-8', xml_declaration=True)
    print(graphml_path)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('usage: build_iacpg.py <case_dir>')
        sys.exit(1)
    main(sys.argv[1])
