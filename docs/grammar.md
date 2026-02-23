# Dice Grammar (BNF)

## Backus-Naur Form

<dice-expression> ::= <count-opt> <d-separator> <sides>
<count-opt> ::= <signed-integer> | ε
<sides> ::= <integer>
<d-separator> ::= "d" | "D"

## Lexical Rules

<signed-integer> ::= <integer> | "-" <integer> | "+" <integer>
<integer> ::= <digit> | <digit> <integer>
<digit> ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"

## Notes

- Whitespace may appear between tokens.
- Input must match exactly one <dice-expression>.
- Semantic rule: if <count-opt> is omitted, <count> defaults to 1.
- Semantic constraint: <count> may be any integer; <sides> must be >= 0.
