def calculator(a, b, operation):
    match operation:
        case '+':
            return a + b
        case '-':
            return a - b
        case '*':
            return a * b
        case '/':
            if b != 0:
                return a / b
            else:
                return "Error: Division by zero"
        case '%':
            return a % b
        case _:
            return "Invalid operation"

# Example usage
print(calculator(10, 5, '+')) # Output: 15
print(calculator(10, 5, '-')) # Output: 5
print(calculator(10, 5, '*')) # Output: 50
print(calculator(10, 5, '/')) # Output: 2.0
print(calculator(10, 5, '%')) # Output: 0
print(calculator(10, 0, '/')) # Output: Error: Division by zero
print(calculator(10, 5, '^')) # Output: Invalid operation
