# Growth Project Rules

## Core Principles

### 1. Maintainability Over Speed
Code quality is prioritized over quick fixes. Every line should be written as if it will be maintained for years.

### 2. Explicit Over Implicit
Prefer explicit behavior over clever shortcuts. Magic should be avoided unless it significantly improves clarity.

### 3. Simple Over Complex
The simplest solution that meets requirements is preferred. Complexity is only added when necessary.

### 4. Extensible Design
Every component should be designed with future expansion in mind, even if features aren't implemented immediately.

## Technical Rules

### Code Structure

#### File Organization
- Files should be no more than 500 lines
- Functions should be no more than 50 lines
- Classes should have a single responsibility
- Modules should have clear, descriptive names

#### Naming Conventions
- Use descriptive, specific names
- Avoid abbreviations unless they're industry-standard
- Use consistent naming patterns throughout the codebase
- Follow PEP 8 for Python code

#### Type Safety
- Use type hints for all function signatures
- Use dataclasses or Pydantic models for data structures
- Validate inputs at system boundaries
- Prefer immutable data structures when possible

### Documentation Requirements

#### Docstrings
- All public functions and classes must have docstrings
- Follow Google Python Style Guide for docstrings
- Include parameter descriptions and return values
- Document exceptions that may be raised

#### Inline Comments
- Use comments to explain "why", not "what"
- Comment complex algorithms or non-obvious decisions
- Keep comments updated with code changes
- Remove outdated comments

#### Architecture Documentation
- Major architectural decisions must be documented
- Update documentation when making significant changes
- Include diagrams for complex systems
- Document extensibility points clearly

### Testing Requirements

#### Test Coverage
- Minimum 90% code coverage
- All public APIs must be tested
- Include edge case testing
- Use property-based testing where appropriate

#### Test Structure
- Tests should be fast and isolated
- Use descriptive test names
- Follow Arrange-Act-Assert pattern
- Mock external dependencies

### Dependency Management

#### External Dependencies
- Minimize external dependencies
- Pin dependency versions in requirements.txt
- Regularly audit dependencies for security issues
- Prefer standard library solutions when adequate

#### Internal Dependencies
- Use dependency injection to manage dependencies
- Avoid circular dependencies
- Keep modules loosely coupled
- Document dependency relationships

## Process Rules

### Git Workflow

#### Branching Strategy
- Use feature branches for all changes
- Branch from main for new features
- Delete branches after merging
- Use descriptive branch names (e.g., `feature/todoist-integration`)

#### Commit Messages
- Use present tense imperative ("Add feature", not "Added feature")
- Include issue number when applicable
- Keep first line under 50 characters
- Separate subject from body with blank line

#### Pull Requests
- All changes must go through PR review
- PRs should be small and focused
- Include description of changes and rationale
- Request review from appropriate maintainers

### Code Review Standards

#### Review Process
- At least one maintainer must approve PRs
- Reviewers should understand the code's purpose
- Focus on correctness, readability, and maintainability
- Provide constructive feedback with explanations

#### Review Criteria
- Does the code meet requirements?
- Is the code clear and well-documented?
- Are there any potential bugs or edge cases?
- Does it follow project style and conventions?
- Is it testable and tested?

### Release Process

#### Versioning
- Follow Semantic Versioning (SemVer)
- Major: Breaking changes
- Minor: New features (backward compatible)
- Patch: Bug fixes (backward compatible)

#### Release Checklist
- All tests pass
- Documentation is updated
- Version numbers are bumped
- CHANGELOG is updated
- Security audit is performed

## Architecture Rules

### Design Patterns

#### Required Patterns
- Factory pattern for object creation
- Strategy pattern for interchangeable algorithms
- Observer pattern for event handling
- Singleton pattern sparingly for configuration

#### Prohibited Patterns
- God objects with multiple responsibilities
- Deep inheritance hierarchies
- Global state
- Hidden side effects

### Extensibility Requirements

#### Plugin Architecture
- Core functionality should be plugin-compatible
- Define clear interfaces for extension points
- Provide default implementations for all interfaces
- Document extension points thoroughly

#### Configuration
- All behavior should be configurable
- Use environment variables for deployment settings
- Provide sensible defaults
- Validate configuration at startup

### Performance Considerations

#### Resource Management
- Close files, network connections, and other resources
- Use context managers for resource handling
- Avoid memory leaks
- Optimize critical paths

#### Scalability
- Design for reasonable data volumes
- Consider caching for expensive operations
- Avoid blocking operations where possible
- Use async/await for I/O-bound operations

## Security Rules

### Data Protection
- Never commit secrets to the repository
- Use environment variables for sensitive data
- Encrypt data in transit and at rest when appropriate
- Validate all input data

### Access Control
- Principle of least privilege
- Regular access reviews
- Secure default configurations
- Audit logging for sensitive operations

### Security Practices
- Keep dependencies up to date
- Regular security audits
- Input validation at system boundaries
- Secure coding practices