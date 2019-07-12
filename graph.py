# -*- coding: utf-8 -*-
__author__ = "Benjamin Trubert, Kévin Huguenin, Mathias Humbert"
__copyright__ = "Copyright 2019, The Information Security and Privacy Lab at the University of Lausanne (https://www.unil.ch/isplab/)"
__credits__ = ["Benjamin Trubert", "Kévin Huguenin", "Mathias Humbert"]

__version__ = "1"
__license__ = "MIT"
__maintainer__ = "Benjamin Trubert"
__email__ = "benjamin.trubert@unil.ch"

import argparse
import json
import re
import sqlite3

import community as louvain_community  # python-louvain package
import matplotlib.pyplot as plt
import networkx as nx
from pybtex.database.input import bibtex


# Match title from bibtex and microsoft database
def clean_title(title):
    # remove '-' and ':' from title
    pattern = '[^a-z^0-9]'

    res = title.lower()
    res = re.sub(pattern, " ", res)

    # Remove extra spaces
    res = re.sub(" +", " ", res)
    res = res.strip()

    return res


# get dictionary for sqlite GET request
def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description="Generate the latex citation graph from a database.")

    parser.add_argument('-d', '--database', help='path to the SQLite database file containing the citations', type=str,
                        required=True)
    parser.add_argument(
        '-a', '--aux', help='path to the aux file', type=str, required=True)
    parser.add_argument(
        '-b', '--bibtex', help='path to the bibtex file', type=str, required=True)
    parser.add_argument('-o', '--output',
                        help='path of the file to save the latex graph (does not gerate the graph if omitted', type=str,
                        required=False)
    parser.add_argument('-x', '--exclude',
                        help='list of papers to be excluded (json file)')

    args = parser.parse_args()

    # Citation key of papers not detailed in the survey
    if args.exclude:
        l = json.load(open(args.exclude))
        citation_blacklist = l['excluded']
    else:
        citation_blacklist = []

    # Find citation keys of the articles cited in the survey
    citation_key = re.compile("cite{(.+_.+_\d+)}")
    with open(args.aux, 'r') as f:
        citation_list = [x for x in citation_key.findall(
            f.read()) if x not in citation_blacklist]

    # Get the title associated to a citation key
    parser = bibtex.Parser()
    bib_data = parser.parse_file(args.bibtex)
    citations = {clean_title(entry.fields['title']): cite for cite, entry in bib_data.entries.items() if
                 cite in citation_list}

    # Connect to the database
    db = sqlite3.connect(args.database)
    db.row_factory = dict_factory
    cursor = db.cursor()

    # Use undirected graph
    graph = nx.Graph()

    # Labels used in the cite command in LaTeX
    label = {}

    for article in cursor.execute(
            "SELECT DISTINCT title FROM article JOIN reference ON article.msid = reference.article or article.msid = reference.reference"):
        # Add article as a node in the graph
        if clean_title(article['title']) in citations:
            graph.add_node(article['title'])
            # Add its citation key latex \cite command as node label
            label[article['title']
                  ] = '\cite{%s}' % citations[clean_title(article['title'])]

    # List of edges to build a directed graph in latex
    edges = []
    for edge in cursor.execute(
            "SELECT DISTINCT a1.title as t1, a2.title as t2 FROM reference JOIN article AS a1 ON reference = a1.msid JOIN article AS a2 ON article = a2.msid"):
        # Add new edge to the graph
        if edge['t1'] in citations and edge['t2'] in citations:
            graph.add_edge(edge['t1'], edge['t2'])
            edges.append((edge['t1'], edge['t2']))

    # Compute the communities of the graph
    parts = louvain_community.best_partition(graph)

    # Separate article within their community
    communities = {}
    [communities.setdefault(value, []).append(
        {'title': key}) for key, value in sorted(parts.items())]

    # Display statistiques information
    print("Number of node: %d" % len(label))
    print("Number of edges: %d" % len(edges))
    [print("Community %d: %d article%s" % (i, len(communities[i]), 's' if len(communities[i]) > 1 else '')) for i in
     sorted(communities)]

    if args.output is not None:
        # Define colors for communities
        colors = {0: 'cyan', 1: 'red', 2: 'green', 3: 'violet'}
        for i in range(4, len(communities)):
            colors[i] = 'black'

        # Set color values for each node depending on its community
        values = [colors[parts.get(node)] for node in graph.nodes()]

        # Get the position to draw the graph with Latex
        plt.figure(figsize=(12, 12))
        pos = nx.kamada_kawai_layout(graph, scale=20)

        # Compute the centrality of each node
        centrality = nx.betweenness_centrality(graph)
        for id, community in communities.items():
            for node in community:
                node['centrality'] = centrality[node['title']]
            # Sort the community, the node with the greatest centrality if the last in the list
            community.sort(key=lambda k: k['centrality'])
            if id == 7:
                print(community)

        # Generate LaTeX code to draw the graph (with tikz)

        latex = """\
\\tikzstyle{vertex}=[rectangle, minimum size=5pt]
\\tikzstyle{border} = [vertex, draw, line width=2pt, inner sep=2pt]
\\tikzstyle{edge} = [draw, very thick, ->, black!42]
"""

        for c, color in colors.items():
            latex += "\\tikzstyle{c%s vertex} = [vertex, fill=%s!42]\n" % (
                c, color)
            latex += "\\tikzstyle{c%s vertex border} = [border, fill=%s!42]\n" % (
                c, color)

        latex += """
\\scalebox{.45}{
\\begin{tikzpicture}[xscale=0.9, yscale=1.2, auto, swap]
"""

        # Add the nodes to the graph
        border_node = ""
        for node, position in pos.items():
            if communities[parts.get(node)][-1]['title'] == node:
                border_node += "\\node[c%s vertex %s] (%s) at (%s, %s) {\LARGE%s};\n" % (
                    str(parts.get(node)), "border", node, "{0:.2f}".format(
                        position[0]), "{0:.2f}".format(position[1]), label[node])
            else:
                latex += "\\node[c%s vertex %s] (%s) at (%s, %s) {\LARGE%s};\n" % (
                    str(parts.get(node)), '', node, "{0:.2f}".format(
                        position[0]), "{0:.2f}".format(position[1]), label[node])

        # Add Most central nodes at the end to increase their visibility
        latex += border_node

        # Add the edges to the graph
        latex += "\n\\begin{pgfonlayer}{bg}\n"
        for s, d in edges:
            latex += "\\path[edge] (%s) -- (%s);\n" % (s, d)

        latex += "\\end{pgfonlayer}\n\n"
        latex += "\\end{tikzpicture}\n}"

        # Create a latex file and save the graph
        with open(args.output, 'w') as f:
            f.write(latex)
