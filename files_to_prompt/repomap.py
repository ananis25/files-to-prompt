"""
Code taken from the [Aider repository](https://github.com/Aider-AI/aider/), but no pagerank stuff.

TODO: Use a cheap LLM to generate docstrings for all classes/functions which don't have them.
"""

import sys
import warnings
from collections import namedtuple
from pathlib import Path

from grep_ast import TreeContext, filename_to_lang

# tree_sitter is throwing a FutureWarning
warnings.simplefilter("ignore", category=FutureWarning)
from tree_sitter_languages import get_language, get_parser  # noqa: E402

################################################################################
# Minimal data structure for storing code tags (definitions/references).
################################################################################

Tag = namedtuple("Tag", "rel_fname fname line name kind end_line")

################################################################################
# A minimal class to build and display a “repo map” with tree-sitter.
################################################################################


class RepoMap:
    def __init__(self):
        pass

    def get_repo_map(self, file_paths):
        """
        Given a list of file paths, build a graph of definitions and references,
        rank them, and produce a textual "map" showing the code lines where
        definitions occur.
        """
        # Identify and rank definitions across all files
        tags = []
        for fname in file_paths:
            tags.extend(self.get_tags(fname, fname))

        # Generate a textual “map” of these definitions
        return self.to_tree(tags)

    def get_tags(self, fname, rel_fname):
        """
        Parse a file with tree-sitter to find definitions and references.
        If references are not found, we optionally backfill them with a
        pygments-based fallback.
        """
        lang = filename_to_lang(fname)
        if not lang:
            return []

        try:
            language = get_language(lang)
            parser = get_parser(lang)
        except Exception as err:
            print(f"Skipping file {fname}: {err}", file=sys.stderr)
            return []

        # Load the tree-sitter queries for the given language
        query_scm = get_scm_fname(lang)
        if not query_scm or not query_scm.exists():
            return []

        query_scm_text = query_scm.read_text()

        code = read_file_text(fname)
        if not code.strip():
            return []

        tree = parser.parse(code.encode("utf-8"))
        query = language.query(query_scm_text)
        captures = query.captures(tree.root_node)

        out = []
        for node, tag in captures:
            kind: str | None = None
            if tag.startswith("name.definition."):
                kind = "def"
            elif tag.startswith("definition.import"):
                kind = "import"
            elif tag.startswith("doc"):
                kind = "doc"

            if kind:
                out.append(
                    Tag(
                        rel_fname=rel_fname,
                        fname=fname,
                        line=node.start_point[0],
                        name=node.text.decode("utf-8"),
                        kind=kind,
                        end_line=node.end_point[0],
                    )
                )

        return out

    def to_tree(self, tags):
        """
        Render a simple textual tree-based listing of the top definitions.
        For each file, we show lines of code where definitions occur.
        """
        if not tags:
            return ""

        # Sort by filename, then by line
        tags = sorted(tags, key=lambda t: (t.rel_fname, t.line))

        output = []
        current_fname = None
        lines_of_interest = []

        # We'll use grep_ast's TreeContext for multiline context around defs.
        # Then we'll format them in a minimal, repeated way.
        def flush():
            """Flush the currently accumulated lines_of_interest for current_fname."""
            if current_fname and lines_of_interest:
                snippet = self.render_tree(current_fname, lines_of_interest)
                output.append(snippet)

        for tag in tags:
            if tag.rel_fname != current_fname:
                # flush the previous batch, start a new one
                flush()
                current_fname = tag.rel_fname
                lines_of_interest = []

            # get lines-of-interest
            if tag.kind == "def" and tag.line >= 0:
                lines_of_interest.append(tag.line)
            if (tag.kind == "doc") and tag.line >= 0:
                lines_of_interest.extend(range(tag.line, tag.end_line + 1))
            if (tag.kind == "import") and tag.line >= 0:
                lines_of_interest.extend(range(tag.line, tag.end_line + 1))

        # flush any leftover
        flush()

        return "".join(output)

    def render_tree(self, fname, lois):
        """
        Use grep_ast's TreeContext to retrieve relevant context lines around
        each “line of interest.”
        """
        code = read_file_text(fname)
        context = TreeContext(
            filename=fname,
            code=code,
            color=False,
            line_number=False,
            child_context=False,
            last_line=False,
            mark_lois=False,
            margin=0,
            loi_pad=0,
        )
        context.add_lines_of_interest(lois)
        context.add_context()
        return context.format()


################################################################################
# Helpers
################################################################################


def read_file_text(fname):
    """Simple helper to read file text as a string."""
    try:
        with open(fname, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        print(f"Could not read {fname}: {e}", file=sys.stderr)
        return ""


def get_scm_fname(lang):
    """
    Return the path to the tree-sitter query .scm file for the given language.
    """
    return Path(__file__).parent.joinpath("queries", f"tree-sitter-{lang}-tags.scm")


################################################################################
# Command-line entry point
################################################################################


def generate_repo_map(file_paths):
    """Generate a minimal tree-sitter-based repo map for a set of files.
    Returns the repo map text as a string.
    """
    # Collect files from all globs

    file_paths = list(set(file_paths))  # deduplicate
    file_paths.sort()

    # Build the repo map
    rm = RepoMap()
    return rm.get_repo_map(file_paths)
