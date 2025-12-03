use pest::Parser;
use pest_derive::Parser;
use crate::ast::*;

#[derive(Parser)]
#[grammar = "cerberus.pest"]
pub struct CerberusParser;

pub fn parse(source: &str) -> Result<Program, String> {
    let pairs = CerberusParser::parse(Rule::program, source)
        .map_err(|e| format!("Parser error: {}", e))?;

    let program_pair = pairs.into_iter().next().unwrap();
    let function_pair = program_pair.into_inner().next().unwrap();

    let mut inner = function_pair.into_inner();

    // fn name
    let name = inner.next().unwrap().as_str().to_string();

    // return type
    let _return_type = inner.next().unwrap();

    // block
    let block_pair = inner.next().unwrap();
    let mut statements = Vec::new();

    for stmt_pair in block_pair.into_inner() {
        match stmt_pair.as_rule() {
            Rule::let_stmt => {
                statements.push(parse_let(stmt_pair)?);
            }
            Rule::return_stmt => {
                statements.push(parse_return(stmt_pair)?);
            }
            _ => {}
        }
    }

    Ok(Program {
        function: Function {
            name,
            return_type: Type::I32,
            body: Block { statements },
        },
    })
}

fn parse_let(pair: pest::iterators::Pair<Rule>) -> Result<Statement, String> {
    let mut inner = pair.into_inner();

    let name = inner.next().unwrap().as_str().to_string();
    let _type_pair = inner.next().unwrap();
    let expr_pair = inner.next().unwrap();

    Ok(Statement::Let {
        name,
        ty: Type::I32,
        value: parse_expr(expr_pair)?,
    })
}

fn parse_return(pair: pest::iterators::Pair<Rule>) -> Result<Statement, String> {
    let expr_pair = pair.into_inner().next().unwrap();
    Ok(Statement::Return(parse_expr(expr_pair)?))
}

fn parse_expr(pair: pest::iterators::Pair<Rule>) -> Result<Expr, String> {
    match pair.as_rule() {
        Rule::owned_expr => {
            // "ow 10" turns into Expr::Owned(Box::new(Expr::Integer(10)))
            let primary = pair.into_inner().next().unwrap();
            Ok(Expr::Owned(Box::new(parse_primary(primary)?)))
        }
        Rule::integer => {
            let n = pair.as_str().parse::<i32>()
                .map_err(|e| format!("Invalid integer: {}", e))?;
            Ok(Expr::Integer(n))
        }
        Rule::ident => {
            Ok(Expr::Ident(pair.as_str().to_string()))
        }
        Rule::expr => {
            // Recursão: expressão dentro de outra (parênteses)
            parse_expr(pair.into_inner().next().unwrap())
        }
        _ => Err(format!("Unexpected expr rule: {:?}", pair.as_rule())),
    }
}

fn parse_primary(pair: pest::iterators::Pair<Rule>) -> Result<Expr, String> {
    match pair.as_rule() {
        Rule::integer => {
            let n = pair.as_str().parse::<i32>()
                .map_err(|e| format!("Invalid integer: {}", e))?;
            Ok(Expr::Integer(n))
        }
        Rule::ident => {
            Ok(Expr::Ident(pair.as_str().to_string()))
        }
        Rule::expr => {
            // Expressão dentro de parênteses
            parse_expr(pair.into_inner().next().unwrap())
        }
        _ => Err(format!("Unexpected primary rule: {:?}", pair.as_rule())),
    }
}