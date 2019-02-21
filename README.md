# LaTeX citation graph of the Survey on Interdependent Privacy
This script generates the LaTeX code to draw the citation graph with communities represented in different colors and most central articles framed.
It uses the [NetworkX](https://networkx.github.io/) and [python-louvain](https://github.com/taynaud/python-louvain) packages.

## Content
It contains the following files:
* graph.py (program file)
* articles_refs.db the sqlite database countaining the list of articles and their references
* main.bib the bibtex file containing the bibliographic database of the survey
* main.aux the aux file containing the list of articles cited in the survey

## Graph.py

The python script requires the following command line arguments
* --database (-d) the path to the SQLite file
* --aux (-a) the path to the aux file
* --bibtex (-b) the path to the bibtex file
* --output (-o) the path to the output LaTeX file containing the graph
