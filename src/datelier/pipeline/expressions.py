"""Compile a small expression language into Polars; never evaluate Python code."""

import ast
import math

import polars as pl

from datelier.pipeline.operations import OperationFailure

HELP = (
    'Use col("name"), scalar literals, + - * / // %, comparisons, and/or/not. '
    "Functions: abs, sqrt, log, lower, upper, length, is_null, is_finite, "
    "fill_null(value, fallback), where(condition, yes, no). "
    'Example: fill_null(col("price"), 0) * col("quantity").'
)


def compile_expression(text: str, table: pl.DataFrame) -> pl.Expr:
    if not text.strip() or len(text) > 4096:
        raise OperationFailure("Expressions require 1–4096 characters")
    try:
        tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError, RecursionError) as error:
        raise OperationFailure(f"Invalid expression syntax: {error}") from error
    if sum(1 for _ in ast.walk(tree)) > 256:
        raise OperationFailure("Expression is too complex (maximum 256 syntax nodes)")

    def visit(node: ast.AST, depth: int = 0) -> pl.Expr:
        if depth > 32:
            raise OperationFailure("Expression nesting exceeds 32 levels")

        def child(value: ast.AST) -> pl.Expr:
            return visit(value, depth + 1)

        match node:
            case ast.Constant(value=value):
                if value is None or isinstance(value, (str, bool, int, float)):
                    if isinstance(value, int) and not -(2**63) <= value < 2**63:
                        raise OperationFailure("Integer literals must fit Int64")
                    if isinstance(value, float) and not math.isfinite(value):
                        raise OperationFailure("Numeric literals must be finite")
                    if isinstance(value, str) and len(value) > 1024:
                        raise OperationFailure(
                            "Text literals are limited to 1024 characters"
                        )
                    return pl.lit(value)
            case ast.BinOp(left=left, op=op, right=right):
                a, b = child(left), child(right)
                match op:
                    case ast.Add():
                        return a + b
                    case ast.Sub():
                        return a - b
                    case ast.Mult():
                        return a * b
                    case ast.Div():
                        return a / b
                    case ast.FloorDiv():
                        return a // b
                    case ast.Mod():
                        return a % b
            case ast.UnaryOp(op=op, operand=value):
                expression = child(value)
                match op:
                    case ast.USub():
                        return -expression
                    case ast.UAdd():
                        return expression
                    case ast.Not():
                        return ~expression
            case ast.BoolOp(op=op, values=values):
                result = child(values[0])
                for value in values[1:]:
                    if isinstance(op, ast.And):
                        result = result & child(value)
                    else:
                        result = result | child(value)
                return result
            case ast.Compare(left=left, ops=ops, comparators=values):
                a = child(left)
                result = pl.lit(True)
                for op, value in zip(ops, values, strict=True):
                    b = child(value)
                    match op:
                        case ast.Eq():
                            comparison = a == b
                        case ast.NotEq():
                            comparison = a != b
                        case ast.Lt():
                            comparison = a < b
                        case ast.LtE():
                            comparison = a <= b
                        case ast.Gt():
                            comparison = a > b
                        case ast.GtE():
                            comparison = a >= b
                        case _:
                            raise OperationFailure(
                                "Only == != < <= > >= comparisons are supported"
                            )
                    result = result & comparison
                    a = b
                return result
            case ast.Call(func=ast.Name(id=name), args=args, keywords=keywords):
                if keywords:
                    raise OperationFailure("Keyword arguments are not supported")
                if name == "col" and len(args) == 1:
                    if not isinstance(args[0], ast.Constant) or not isinstance(
                        args[0].value, str
                    ):
                        raise OperationFailure(
                            'col requires a literal column name, e.g. col("value")'
                        )
                    column = args[0].value
                    if column not in table.columns:
                        raise OperationFailure(f"Unknown column: {column!r}")
                    return pl.lit(table.get_column(column).alias("value"))
                if name == "fill_null" and len(args) == 2:
                    return child(args[0]).fill_null(child(args[1]))
                if name == "where" and len(args) == 3:
                    return (
                        pl.when(child(args[0]))
                        .then(child(args[1]))
                        .otherwise(child(args[2]))
                    )
                if len(args) == 1:
                    value = child(args[0])
                    match name:
                        case "abs":
                            return value.abs()
                        case "sqrt":
                            return value.sqrt()
                        case "log":
                            return value.log()
                        case "lower":
                            return value.str.to_lowercase()
                        case "upper":
                            return value.str.to_uppercase()
                        case "length":
                            return value.str.len_chars()
                        case "is_null":
                            return value.is_null()
                        case "is_finite":
                            return value.is_finite()
                raise OperationFailure(
                    f"Unsupported function or argument count: {name}"
                )
        raise OperationFailure(f"Unsupported expression syntax: {type(node).__name__}")

    return visit(tree.body)


def derive_column(
    table: pl.DataFrame, name: str, text: str, replace: bool
) -> pl.DataFrame:
    if not name:
        raise OperationFailure("Derived columns need a nonempty name")
    if name in table.columns and not replace:
        raise OperationFailure(f"Column {name!r} exists; explicitly enable replacement")
    return table.with_columns(compile_expression(text, table).alias(name))
