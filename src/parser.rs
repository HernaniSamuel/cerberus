use pest::Parser;
use pest_derive::Parser;
use crate::ast::*;

#[derive(Parser)]
#[grammar = "cerberus.pest"]
pub struct CerberusParser;

pub fn parse(source: &str) -> Result<Program, String> {
    let pairs = CerberusParser::parse(Rule::program, source)
        .map_err(|e| format!("Parser error: {}", e))?;

    let mut program_pair = pairs.into_iter().next().unwrap();
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
            Rule::statement => {
                let inner = stmt_pair.into_inner().next().unwrap();

                match inner.as_rule() {
                    Rule::return_stmt => {
                        let value_str = inner.into_inner().next().unwrap().as_str();
                        let value = value_str.parse::<i32>().unwrap();
                        statements.push(Statement::Return(value));
                    }
                    _ => {}
                }
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