# Parse bankstatements

This is a working example on how to use parse PDF files using python.

## Quickstart

1. Download your `PayLah!` statement (from your app, find `e-Statements`)
2. Write your own python code to use `pbsm.bank_statement.PdfStatement`

The `PdfStatement` takes in filepath as input. 

`DbsPaylahStatement` inherits `PdfStatement`, and has it's own algorithm 
to process PayLah! statements.



```python
## Example of a basic code
class PdfStatement:
    def __init__(self, filepath: Path):
        ...

class DbsPaylahStatement(PdfStatement):
    def __init__(self, filepath: Path):
        ...

def main():
    statement = DbsPaylahStatement(statement.filepath)
    df = statement.parse_transaction_to_dataframe()

if __name__ == "__main__":
    main()
```


