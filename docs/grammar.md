# Dice Grammar (BNF)

## Backus-Naur Form

<expression> ::= <sum>
<sum> ::= <product> | <sum> "+" <product> | <sum> "-" <product>
<product> ::= <dice> | <product> "*" <dice> | <product> "/" <dice>
<dice> ::= <power> | <dice> <d-separator> <power>
<power> ::= <unary> | <unary> "^" <power>
<unary> ::= <primary> | "+" <unary> | "-" <unary> | <d-separator> <unary>
<primary> ::= <integer> | "(" <expression> ")"

<d-separator> ::= "d" | "D"

## Lexical Rules

<signed-integer> ::= <integer> | "-" <integer> | "+" <integer>
<integer> ::= <digit> | <digit> <integer>
<digit> ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"

## Notes

- Whitespace may appear between tokens.
- Input must match exactly one <expression>.
- Operator precedence (high to low): unary `d`, unary `+/-`, `^`, binary `d`, `*`/`/`, `+`/`-`.
- `d20` is equivalent to `1d20`.
- Semantic constraint: right operand of binary `d` (dice sides) must be >= 0.
