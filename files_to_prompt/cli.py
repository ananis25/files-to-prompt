import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Annotated, List, Optional

import typer

from files_to_prompt.repomap import generate_repo_map

global_index = 1


def count_tokens(text):
    return f"\nNum tokens: {len(text) // 4}-{len(text) // 3}\n"


def should_ignore(path, gitignore_rules):
    for rule in gitignore_rules:
        if fnmatch(os.path.basename(path), rule):
            return True
        if os.path.isdir(path) and fnmatch(os.path.basename(path) + "/", rule):
            return True
    return False


def read_gitignore(path):
    gitignore_path = os.path.join(path, ".gitignore")
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r") as f:
            return [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    return []


def print_path(writer, path, content, xml):
    if xml:
        print_as_xml(writer, path, content)
    else:
        print_default(writer, path, content)


def print_default(writer, path, content):
    writer(path)
    writer("---")
    writer(content)
    writer("")
    writer("---")


def print_as_xml(writer, path, content):
    global global_index
    writer(f'<document index="{global_index}">')
    writer(f"<source>{path}</source>")
    writer("<document_content>")
    writer(content)
    writer("</document_content>")
    writer("</document>")
    global_index += 1


def process_path(
    path,
    extensions,
    include_hidden,
    ignore_gitignore,
    gitignore_rules,
    ignore_patterns,
    writer,
    claude_xml,
):
    if os.path.isfile(path):
        yield path
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                files = [f for f in files if not f.startswith(".")]

            if not ignore_gitignore:
                gitignore_rules.extend(read_gitignore(root))
                dirs[:] = [
                    d
                    for d in dirs
                    if not should_ignore(os.path.join(root, d), gitignore_rules)
                ]
                files = [
                    f
                    for f in files
                    if not should_ignore(os.path.join(root, f), gitignore_rules)
                ]

            if ignore_patterns:
                files = [
                    f
                    for f in files
                    if not any(fnmatch(f, pattern) for pattern in ignore_patterns)
                ]

            if extensions:
                files = [f for f in files if f.endswith(tuple(extensions))]

            for file in sorted(files):
                file_path = os.path.join(root, file)
                yield file_path


app = typer.Typer()


@app.command()
def main(
    paths: Annotated[List[Path], typer.Argument(exists=True)],
    extensions: Annotated[List[str], typer.Option("--extension", "-e")] = [],
    include_hidden: Annotated[
        bool,
        typer.Option(
            "--include-hidden", help="Include files and folders starting with ."
        ),
    ] = False,
    repomap: Annotated[bool, typer.Option(help="Output in repomap format")] = False,
    ignore_gitignore: Annotated[
        bool, typer.Option(help="Ignore .gitignore files and include all files")
    ] = False,
    ignore_patterns: Annotated[
        List[str], typer.Option("--ignore", help="List of patterns to ignore")
    ] = [],
    output_file: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output to a file instead of stdout"),
    ] = None,
    claude_xml: Annotated[
        bool,
        typer.Option(
            "--cxml",
            "-c",
            help="Output in XML-ish format suitable for Claude's long context window.",
        ),
    ] = False,
) -> None:
    """
    Takes one or more paths to files or directories and outputs every file,
    recursively, each one preceded with its filename.

    The output format depends on the flags:

    Standard format:
    path/to/file.py
    ----
    Contents of file.py goes here
    ---

    Claude XML format (with --cxml):
    <documents>
    <document path="path/to/file1.txt">
    Contents of file1.txt
    </document>
    </documents>
    """
    # Reset global_index for pytest
    global global_index
    global_index = 1
    gitignore_rules = []

    writer = typer.echo
    fp = None
    if output_file:
        fp = open(output_file, "w")
        writer = lambda s: print(s, file=fp)  # noqa

    try:
        for path in paths:
            if not path.exists():
                raise typer.BadParameter(f"Path does not exist: {path}")

            if not ignore_gitignore:
                gitignore_rules.extend(read_gitignore(path.parent))

            if claude_xml and path == paths[0]:
                writer("<documents>")

            for file_path in process_path(
                path,
                extensions,
                include_hidden,
                ignore_gitignore,
                gitignore_rules,
                ignore_patterns,
                writer,
                claude_xml,
            ):
                try:
                    if repomap:
                        text = generate_repo_map([str(file_path)])
                        print_path(writer, file_path, text, claude_xml)
                    else:
                        with open(file_path, "r") as f:
                            print_path(writer, file_path, f.read(), claude_xml)
                except UnicodeDecodeError:
                    typer.secho(
                        f"Warning: Skipping file {file_path} due to UnicodeDecodeError",
                        fg=typer.colors.RED,
                        err=True,
                    )

        if claude_xml:
            writer("</documents>")

    finally:
        if fp:
            fp.close()
            with output_file.open() as f:  # noqa
                content = f.read()
                typer.echo(count_tokens(content))


if __name__ == "__main__":
    app()
