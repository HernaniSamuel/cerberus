#[derive(Debug, Clone)]
pub struct Program {
    pub function: Function,
}

#[derive(Debug, Clone)]
pub struct Function {
    pub name: String,
    pub return_type: Type,
    pub body: Block,
}

#[derive(Debug, Clone)]
pub struct Block {
    pub statements: Vec<Statement>,
}

#[derive(Debug, Clone)]
pub enum Statement {
    Return(i32),
}

#[derive(Debug, Clone)]
pub enum Type {
    I32,
}