# Contributing to Growth

Welcome! We're excited to have you contribute to Growth, a personal productivity system designed for long-term maintainability and extensibility.

## Code of Conduct

This project adheres to the Contributor Covenant code of conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before submitting a bug report:
1. Check the issue tracker to see if the bug has already been reported
2. Try to reproduce the bug with the latest version of the code

When submitting a bug report, please include:
- A clear and descriptive title
- Steps to reproduce the issue
- Expected vs. actual behavior
- Screenshots or code examples if relevant
- Your environment details (OS, Python version, etc.)

### Suggesting Enhancements

Feature requests are welcome! Please provide:
- A clear and descriptive title
- Detailed explanation of the proposed feature
- Use cases and justification
- Potential implementation approaches (if you have ideas)

### Code Contributions

1. Fork the repository
2. Create a new branch for your feature or bug fix
3. Write clear, documented code following our style guidelines
4. Add tests for your changes
5. Ensure all tests pass
6. Submit a pull request with a clear description

## Development Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/growth.git
   cd growth
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. Run tests:
   ```
   pytest
   ```

## Style Guide

### Python Code

We follow the PEP 8 style guide with some additional conventions:

- Use 4 spaces for indentation (no tabs)
- Maximum line length: 88 characters
- Use descriptive variable and function names
- Write docstrings for all public classes and functions
- Use type hints for all function signatures

### Example:
```python
def calculate_study_time(topics: List[str], difficulty: int) -> int:
    """
    Calculate recommended study time based on topics and difficulty.
    
    Args:
        topics: List of topic names to study
        difficulty: Difficulty level (1-10)
        
    Returns:
        Recommended study time in minutes
    """
    # Implementation here
    pass
```

### Documentation

- Write clear, concise documentation
- Update README.md and other docs as needed
- Use Markdown for documentation files
- Include examples for complex features

## Testing

All contributions must include appropriate tests:

- Unit tests for individual functions and classes
- Integration tests for major components
- End-to-end tests for critical workflows

Run tests with:
```
pytest
```

Check test coverage with:
```
pytest --cov=growth
```

## Pull Request Process

1. Ensure your code follows the style guide
2. Add or update documentation as needed
3. Include tests that cover your changes
4. Describe your changes clearly in the PR description
5. Link any related issues
6. Request review from maintainers

## Commit Message Guidelines

Use clear, concise commit messages following this format:

```
type(scope): brief description

Detailed explanation if needed.
```

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code style changes
- refactor: Code refactoring
- test: Test-related changes
- chore: Maintenance tasks

Example:
```
feat(todoist): add task dependency management

Implement support for creating dependent tasks in Todoist
with proper error handling and validation.
```

## Architecture Principles

When contributing, keep these principles in mind:

1. **Modularity**: Components should be loosely coupled
2. **Extensibility**: Design for future features
3. **Maintainability**: Code should be clear and well-documented
4. **Testability**: Components should be easy to test in isolation
5. **Performance**: Consider efficiency implications

## Questions?

If you have questions about contributing, feel free to:
1. Open an issue for discussion
2. Contact the maintainers directly
3. Join our community chat (link in README)

Thank you for contributing to Growth!