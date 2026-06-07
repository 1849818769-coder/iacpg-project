#!/usr/bin/env python3
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

NS = {'g': 'http://graphml.graphdrawing.org/xmlns'}

def load_graph(path):
    tree = ET.parse(path)
    root = tree.getroot()
    graph = root.find('g:graph', NS)
    nodes = {}
    edges = []
    for node in graph.findall('g:node', NS):
        data = {d.attrib.get('key'): (d.text or '').strip() for d in node.findall('g:data', NS)}
        nodes[node.attrib['id']] = data
    for edge in graph.findall('g:edge', NS):
        data = {d.attrib.get('key'): (d.text or '').strip() for d in edge.findall('g:data', NS)}
        edges.append((edge.attrib['source'], edge.attrib['target'], data))
    return nodes, edges


def print_summary(nodes, edges):
    by_label = defaultdict(int)
    by_edge = defaultdict(int)
    for n in nodes.values():
        by_label[n.get('labelV', 'UNKNOWN')] += 1
    for _, _, e in edges:
        by_edge[e.get('labelE', 'UNKNOWN')] += 1
    print('== Node Labels ==')
    for k, v in sorted(by_label.items()):
        print(f'{k}: {v}')
    print('\n== Edge Labels ==')
    for k, v in sorted(by_edge.items()):
        print(f'{k}: {v}')


def print_preemptions(nodes, edges):
    for s, t, e in edges:
        if e.get('labelE') == 'INTERRUPT_PREEMPTS':
            print(f"{nodes[s].get('node__IACPG__NAME', s)} -> {nodes[t].get('node__IACPG__NAME', t)} [{e.get('edge__IACPG__TYPE','')}]" )


def print_switches(nodes, edges):
    for s, t, e in edges:
        if e.get('labelE') in ('ENABLES', 'DISABLES'):
            print(f"{nodes[s].get('node__IACPG__NAME', s)} -> {nodes[t].get('node__IACPG__NAME', t)} [{e.get('labelE')}]" )


def print_var(var, nodes, edges):
    for s, t, e in edges:
        if e.get('labelE') == 'ACCESSES_SHARED_VAR' and nodes[t].get('node__IACPG__NAME') == var:
            print(f"{nodes[s].get('node__IACPG__NAME', s)} --{e.get('edge__IACPG__TYPE','')}--> {var}")
        if e.get('labelE') == 'POTENTIAL_CONCURRENCY_ON' and e.get('edge__IACPG__TYPE') == var:
            print(f"{nodes[s].get('node__IACPG__NAME', s)} <-> {nodes[t].get('node__IACPG__NAME', t)} on {var}")


def main():
    if len(sys.argv) < 3:
        print('usage: query_iacpg.py <graphml> <summary|preemptions|switches|var> [var_name]')
        sys.exit(1)
    nodes, edges = load_graph(sys.argv[1])
    cmd = sys.argv[2]
    if cmd == 'summary':
        print_summary(nodes, edges)
    elif cmd == 'preemptions':
        print_preemptions(nodes, edges)
    elif cmd == 'switches':
        print_switches(nodes, edges)
    elif cmd == 'var':
        if len(sys.argv) < 4:
            print('var_name required')
            sys.exit(1)
        print_var(sys.argv[3], nodes, edges)
    else:
        raise SystemExit(f'unknown command: {cmd}')

if __name__ == '__main__':
    main()
