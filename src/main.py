from lark import Lark, UnexpectedToken, UnexpectedCharacters, Tree
from pathlib import Path
from pprint import pprint
import sys

from parser import CST2AST
from ast_cerberus import Program


# file paths that should be load by the load_source function
GRAMMAR_PATH: str =  "cerberus.lark"
TEST_SOURCE: str = "test.re1"


# This function should find the path of any source like .re1 or .lark
def load_source(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"Error: file '{path}' not found.")
        sys.exit(1)
    return p.read_text(encoding="utf-8")


# This function should build the lark parser correctly based on cerberus.lark grammar
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


# This function should print the lark CST in a pretty way for debug
def pretty_print_cst(tree: Tree) -> None:
    print(tree.pretty())


# This function should print the AST in a pretty way for debug
def pretty_print_ast(node: object) -> None:
    # dataclasses print in a clean approach with repr()
    pprint(node)


# This function should call all other functions of the pipeline in the right order
def main() -> None:
    print("Loading source...")
    src: str = load_source(TEST_SOURCE)

    print("Building parser...")
    parser: Lark = build_parser()

    print("Analysing...")
    try:
        print("=== CST ===")
        cst: Tree = parser.parse(src)
        pretty_print_cst(cst)

        print("=== AST ===")
        ast: Program = CST2AST().transform(cst)
        pretty_print_ast(ast)

    except UnexpectedToken as e:
        print("\nSyntax Error (unexpected tokens):")
        print(e)
    except UnexpectedCharacters as e:
        print("\nSyntax Error (unexpected characters):")
        print(e)
    except Exception as e:
        print("\nUnexpected error during parsing:")
        print(type(e).__name__, e)


# The entry point of the code
if __name__ == "__main__":
    main()
