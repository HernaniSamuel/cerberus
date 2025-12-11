from __future__ import annotations

from pathlib import Path
from pprint import pprint
import sys

from lark import Lark, Tree, UnexpectedToken, UnexpectedCharacters

# Frontend
from parser import CST2AST
from ast_cerberus import Program

# Middle-end
from fates import lower_program, IRProgram
from nemesis import check_program

# Backend
from typewriter import generate_c_program


# ---------------------------------------
# Config
# ---------------------------------------
GRAMMAR_PATH: str = "cerberus.lark"
TEST_SOURCE: str = "test.re1"


# ---------------------------------------
# Utilities
# ---------------------------------------

def load_source(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"Error: file '{path}' not found.", file=sys.stderr)
        sys.exit(1)
    return p.read_text(encoding="utf-8")


def build_parser() -> Lark:
    try:
        grammar = Path(GRAMMAR_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: grammar '{GRAMMAR_PATH}' not found.", file=sys.stderr)
        sys.exit(1)

    return Lark(grammar, parser="lalr", start="start", debug=False)


# ---------------------------------------
# Pipeline
# ---------------------------------------

def main() -> None:

    # 1. Load source
    print("Loading source...")
    src = load_source(TEST_SOURCE)
    print("=== Source ===")
    print(src, "\n")

    # 2. Parser
    print("Building parser...")
    parser = build_parser()

    print("=== CST ===")
    try:
        cst = parser.parse(src)
        print(cst.pretty())
    except (UnexpectedToken, UnexpectedCharacters) as e:
        print("Syntax error:", e)
        sys.exit(1)

    # 3. CST → AST
    print("=== AST ===")
    ast = CST2AST().transform(cst)
    pprint(ast)

    # 4. AST → IR
    print("=== IR ===")
    ir = lower_program(ast)
    pprint(ir)

    # 5. Ownership checker (Tyrant)
    print("=== Ownership Check ===")
    try:
        check_program(ir)
        print("Ownership OK.")
    except Exception as e:
        print("Ownership violation:", e)
        sys.exit(1)

    # 6. IR → C (Typewriter)
    print("=== C Code ===")
    c_code = generate_c_program(ir)
    print(c_code)

    # Save output (optional)
    Path("output.c").write_text(c_code, encoding="utf-8")
    print("[Saved output.c]")


if __name__ == "__main__":
    main()
