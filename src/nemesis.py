# STARS...

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set

from fates import (
    IRProgram,
    IRFunction,
    IRInstr,
    IR_OwLiteral,
    IR_MvVar,
    IR_Assign,
    IR_Return,
    IRLiteral,
    IRVarRef,
)


# -------------------------
# Nemesis Errors
# -------------------------

@dataclass
class NemesisError(Exception):
    """Ownership error detected by Nemesis."""
    message: str
    function: str
    instr: IRInstr

    def __str__(self) -> str:
        return (
            f"OWNERSHIP ERROR in function '{self.function}':\n"
            f"   {self.message}\n"
            f"   Instruction: {self.instr!r}"
        )


# -------------------------
# Variable states
# -------------------------

class VarState:
    """Possible states of a variable during execution."""
    UNINIT = "uninit"  # Not initialized
    ALIVE = "alive"   # Alive and usable
    MOVED = "moved"   # It was moved; it can no longer be used.


# -------------------------
# Verification context
# -------------------------

@dataclass
class CheckContext:
    """
    Maintains the state of all variables during checking.
    This makes it easy to track what is happening.
    """
    function_name: str

    # Current state of each variable
    var_states: Dict[str, str]

    # How many times each variable was moved
    move_count: Dict[str, int]

    def __init__(self, function_name: str, locals: list[str]):
        self.function_name = function_name
        self.var_states = {name: VarState.UNINIT for name in locals}
        self.move_count = {name: 0 for name in locals}

    def is_alive(self, var: str) -> bool:
        """Check whether the variable is alive and can be used."""
        return self.var_states.get(var) == VarState.ALIVE

    def is_moved(self, var: str) -> bool:
        """Check whether the variable has already been moved."""
        return self.var_states.get(var) == VarState.MOVED

    def is_uninit(self, var: str) -> bool:
        """Check whether the variable has not been initialized."""
        return self.var_states.get(var) == VarState.UNINIT

    def mark_alive(self, var: str) -> None:
        """Mark the variable as alive."""
        self.var_states[var] = VarState.ALIVE

    def mark_moved(self, var: str) -> None:
        """Mark the variable as moved and increment the counter."""
        self.var_states[var] = VarState.MOVED
        self.move_count[var] += 1

    def get_move_count(self, var: str) -> int:
        """Return how many times the variable was moved."""
        return self.move_count.get(var, 0)


# -------------------------
# Entrypoint
# -------------------------

def check_program(ir: IRProgram) -> None:
    """
    Check all functions in the program.
    Raises NemesisError if an ownership violation is found.
    """
    for fn in ir.functions:
        check_function(fn)


# -------------------------
# Per-function verification
# -------------------------

def check_function(fn: IRFunction) -> None:
    """
    Check an entire function, instruction by instruction.
    Maintains the state of all local variables.
    """
    ctx = CheckContext(fn.name, fn.locals)

    for instr in fn.instrs:
        # Dispatch to the specific checker for each instruction
        if isinstance(instr, IR_OwLiteral):
            check_ow_literal(ctx, instr)

        elif isinstance(instr, IR_MvVar):
            check_mv_var(ctx, instr)

        elif isinstance(instr, IR_Assign):
            check_assign(ctx, instr)

        elif isinstance(instr, IR_Return):
            check_return(ctx, instr)

        else:
            raise NemesisError(
                f"Unknown instruction type: {type(instr).__name__}",
                ctx.function_name,
                instr
            )


# -------------------------
# RULE 1: ow only works with literals
# -------------------------

def check_ow_literal(ctx: CheckContext, instr: IR_OwLiteral) -> None:
    """
    Checks: let x = ow 10;

    RULES:
    - 'ow' can only be used with literals (numbers)
    - 'ow' creates a new value, so the variable becomes alive
    """
    # The IR_OwLiteral instruction already guarantees it is a literal
    # So we only need to mark the variable as alive
    ctx.mark_alive(instr.target)


# -------------------------
# RULE 2: mv only works with live variables
# RULE 4: each variable can only be moved once
# -------------------------

def check_mv_var(ctx: CheckContext, instr: IR_MvVar) -> None:
    """
    Checks: let x = mv y;

    RULES:
    - 'mv' can only be used with variables (not literals)
    - The source variable must be alive
    - Each variable can only be moved once
    - After moving, the source becomes "moved" and can no longer be used
    - The target becomes alive
    """
    source = instr.source
    target = instr.target

    # Check whether the source variable exists
    if source not in ctx.var_states:
        raise NemesisError(
            f"Trying to move variable '{source}' which does not exist",
            ctx.function_name,
            instr
        )

    # RULE: Cannot move an uninitialized variable
    if ctx.is_uninit(source):
        raise NemesisError(
            f"Cannot move variable '{source}' that has not been initialized",
            ctx.function_name,
            instr
        )

    # RULE: Cannot move a variable that has already been moved
    if ctx.is_moved(source):
        raise NemesisError(
            f"Variable '{source}' was already moved before. "
            f"Each variable can only be moved ONCE! "
            f"(total moves: {ctx.get_move_count(source)})",
            ctx.function_name,
            instr
        )

    # All good! Consume the source and mark the target as alive
    ctx.mark_moved(source)
    ctx.mark_alive(target)


# -------------------------
# RULE: Generic assignment (rare, but possible)
# -------------------------

def check_assign(ctx: CheckContext, instr: IR_Assign) -> None:
    """
    Checks: x = y; (without ow/mv)

    RULES:
    - If the operand is a variable, it must be alive
    - Cannot use a variable that was moved
    - Cannot use an uninitialized variable
    """
    op = instr.operand

    if isinstance(op, IRVarRef):
        var_name = op.name

        # Check whether the variable was moved
        if ctx.is_moved(var_name):
            raise NemesisError(
                f"Use-after-move! Variable '{var_name}' was moved and can no longer be used. "
                f"(moved {ctx.get_move_count(var_name)} time(s))",
                ctx.function_name,
                instr
            )

        # Check whether the variable was initialized
        if ctx.is_uninit(var_name):
            raise NemesisError(
                f"Use of uninitialized variable: '{var_name}'",
                ctx.function_name,
                instr
            )

    # Assignment always creates a live value in the target
    ctx.mark_alive(instr.target)


# -------------------------
# RULE 3: return requires ow/mv
# -------------------------

def check_return(ctx: CheckContext, instr: IR_Return) -> None:
    """
    Checks: return mv x; or return ow 10;

    RULES:
    - Return requires a live value
    - If returning a variable, it must be alive
    - Cannot return a moved variable
    - Cannot return an uninitialized variable
    - Return consumes the value (marks it as moved if it is a variable)
    """
    op = instr.operand

    if isinstance(op, IRVarRef):
        var_name = op.name

        # Check whether the variable was moved
        if ctx.is_moved(var_name):
            raise NemesisError(
                f"Trying to return variable '{var_name}' that was already moved. "
                f"Cannot return a value that no longer exists!",
                ctx.function_name,
                instr
            )

        # Check whether the variable was initialized
        if ctx.is_uninit(var_name):
            raise NemesisError(
                f"Trying to return variable '{var_name}' that was not initialized",
                ctx.function_name,
                instr
            )

        # Return consumes the value
        ctx.mark_moved(var_name)

    elif isinstance(op, IRLiteral):
        # Returning a literal is always OK
        pass

    else:
        raise NemesisError(
            f"Unknown operand type in return: {type(op).__name__}",
            ctx.function_name,
            instr
        )
