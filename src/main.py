from lark import Lark, UnexpectedToken, UnexpectedCharacters, Tree
from pathlib import Path
import sys
from typing import Optional

GRAMMAR_PATH: str =  "cerberus.lark"
TEST_SOURCE: str = "test.re1"


def load_source(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"Error: file '{path}' not found.")
        sys.exit(1)
    return p.read_text(encoding="utf-8")

def build_parser() -> Lark:
    try:
        grammar = Path(GRAMMAR_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: grammar '{GRAMMAR_PATH}' not found.")
        sys.exit(1)

    parser: Lark = Lark(
        grammar,
        parser="lalr",
        start="start",
        debug=False,
    )
    return parser

def pretty_print_cst(tree: Tree) -> None:
    print(tree.pretty())

def main() -> None:
    print("Loading source...")
    src: str = load_source(TEST_SOURCE)

    print("Building parser...")
    parser: Lark = build_parser()

    print("Analysing...")
    try:
        tree: Tree = parser.parse(src)
        print("=== CST ===")
        pretty_print_cst(tree)
    except UnexpectedToken as e:
        print("\nSyntax Error (unexpected tokens):")
        print(e)
    except UnexpectedCharacters as e:
        print("\nSyntax Error (unexpected characters):")
        print(e)
    except Exception as e:
        print("\nUnexpected error during parsing:")
        print(type(e).__name__, e)


if __name__ == "__main__":
    main()