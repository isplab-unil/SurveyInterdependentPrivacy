# -*- coding: utf-8 -*-
__author__ = "Benjamin Trubert, Kévin Huguenin, Mathias Humbert"
__copyright__ = "Copyright 2019, The Information Security and Privacy Lab at the University of Lausanne (https://www.unil.ch/isplab/)"
__credits__ = ["Benjamin Trubert", "Kévin Huguenin", "Mathias Humbert"]

__version__ = "1"
__license__ = "MIT"
__maintainer__ = "Benjamin Trubert"
__email__ = "benjamin.trubert@unil.ch"

import networkx as nx
import matplotlib.pyplot as plt
import sqlite3
import community as louvain_community  # python-louvain package
import re
import argparse
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

    parser = argparse.ArgumentParser(description="Generate the latex citation graph from a database.")

    parser.add_argument('-d', '--database', help='path to the SQLite database file containing the citations', type=str, required=True)
    parser.add_argument('-a', '--aux', help='path to the aux file', type=str, required=True)
    parser.add_argument('-b', '--bibtex', help='path to the bibtex file', type=str, required=True)
    parser.add_argument('-o', '--output', help='path of the file to save the latex graph', type=str, required=True)

    args = parser.parse_args()

    # Define colors for communities
    colors = {0: 'cyan', 1: 'red', 2: 'green', 3: 'violet', 4: 'orange', 5: 'blue', 6: 'black'}

    # Citation key of papers not detailed in the survey
    citation_blacklist = ["westin_privacy_1970", "nissenbaum_privacy_2010", "bloustein_individual_1978", "narayanan_obfuscated_2005", "floridi_open_2014", "blondel_fast_2008", "kamada_algorithm_1989",
                          "koller_probabilistic_2009", "pearl_probabilistic_1988", "jensen_optimal_1994", "menezes_handbook_1997", "shamir1979share", "sahai_fuzzy_2005", "goyal_attribute-based_2006",
                          "paillier_public-key_1999", "elgamal_public_1985", "dwork_differential_2006", "kifer_no_2011", "kifer_pufferfish_2014", "chen_correlated_2014", "yang_bayesian_2015",
                          "zhu_correlated_2015", "liu_dependence_2016", "song_pufferfish_2017", "levi_age_2015", "fu_learning_2014", "klug_concepts_2003", "carminati_enforcing_2009",
                          "karwatzki_adverse_2017", "choi_collaborative_2011", "eagle_inferring_2009", "crandall_inferring_2010", "thornton_estimating_2012", "eagle_inferring_2009",
                          "crandall_inferring_2010", "backes_walk2friends_2017", "kale_utility_2018", "manichaikul_robust_2010", "redmiles_dancing_2018", "yu_my_2018",
                          "meier_windfall_2014"]

    # Find citation keys of the articles cited in the survey
    citation_key = re.compile("cite{(.+_.+_\d+)}")
    with open(args.aux, 'r') as f:
        citation_list = [x for x in citation_key.findall(f.read()) if x not in citation_blacklist]

    # Get the title associated to a citation key
    parser = bibtex.Parser()
    bib_data = parser.parse_file(args.bibtex)
    citations = {clean_title(entry.fields['title']): cite for cite, entry in bib_data.entries.items() if cite in citation_list}

    # Connect to the database
    db = sqlite3.connect(args.database)
    db.row_factory = dict_factory
    cursor = db.cursor()

    # Use undirected graph
    graph = nx.Graph()

    # Labels used in the cite command in LaTeX
    label = {}

    for article in cursor.execute("SELECT DISTINCT title, first_author, venue, year FROM article JOIN reference ON article.msid = reference.article or article.msid = reference.reference"):
        # Add article as a node in the graph
        if article['title'] in citations:
            graph.add_node(article['title'])
            # Add its citation key latex \cite command as node label
            label[article['title']] = '\cite{%s}' % citations[clean_title(article['title'])]

    # List of edges to build a directed graph in latex
    edges = []
    for edge in cursor.execute("SELECT DISTINCT a1.title as t1, a2.title as t2 FROM reference JOIN article AS a1 ON reference = a1.msid JOIN article AS a2 ON article = a2.msid"):
        # Add new edge to the graph
        if edge['t1'] in citations and edge['t2'] in citations:
            graph.add_edge(edge['t1'], edge['t2'])
            edges.append((edge['t1'], edge['t2']))

    # Compute the communities of the graph
    parts = louvain_community.best_partition(graph)
    values = [colors[parts.get(node)] for node in graph.nodes()]

    # Get the position to draw the graph with Latex
    plt.figure(figsize=(12, 12))
    pos = nx.kamada_kawai_layout(graph, scale=20)

    # Separate article within their community
    communities = {}
    for title in label:
        color = colors[parts.get(title)]
        if color not in communities:
            communities[color] = []
        communities[color].append({'title': title})

    # Compute the centrality of each node
    centrality = nx.betweenness_centrality(graph)
    for _, community in communities.items():
        for node in community:
            node['centrality'] = centrality[node['title']]
        # Sort the community, the node with the greatest centrality if the last in the list
        community.sort(key=lambda k: k['centrality'])

    # Generate LaTeX code to draw the graph (with tikz)
    latex = "" \
            "\\tikzstyle{vertex}=[rectangle, minimum size=5pt]\n" \
            "\\tikzstyle{border} = [vertex, draw, line width=2pt, inner sep=2pt]\n" \
            "\\tikzstyle{edge} = [draw, very thick, ->, black!42]\n"

    for c, color in colors.items():
        latex += "\\tikzstyle{c%s vertex} = [vertex, fill=%s!42]\n" % (c, color)
        latex += "\\tikzstyle{c%s vertex border} = [border, fill=%s!42]\n" % (c, color)

    latex += "\n" \
             "\\scalebox{.45}{\n" \
             "\\begin{tikzpicture}[xscale=0.9, yscale=1.2, auto, swap]\n"

    # Add the nodes to the graph
    for node, position in pos.items():
        border = "border" if communities[colors[parts.get(node)]][-1]['title'] == node else ''
        latex += "\\node[c%s vertex %s] (%s) at (%s, %s) {\LARGE%s};\n" % (
            str(parts.get(node)), border, node, "{0:.2f}".format(
                position[0]), "{0:.2f}".format(position[1]), label[node])

    # Add the edges to the graph
    latex += "\n\\begin{pgfonlayer}{bg}\n"
    for s, d in edges:
        latex += "\\path[edge] (%s) -- (%s);\n" % (s, d)
    latex += "\\end{pgfonlayer}\n\n"

    latex += "\\end{tikzpicture}\n}"

    # Create a latex file and save the graph
    with open(args.output, 'w') as f:
        f.write(latex)
