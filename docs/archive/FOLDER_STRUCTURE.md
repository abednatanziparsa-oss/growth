# Growth Folder Structure

## Overview

This document describes the folder structure for the Growth project, following clean architecture principles to ensure maintainability and extensibility.

## Root Directory

```
growth/
├── src/                 # Source code
├── tests/               # Test files
├── docs/                # Documentation
├── config/              # Configuration files
├── scripts/             # Utility scripts
├── requirements.txt     # Python dependencies
├── requirements-dev.txt # Development dependencies
├── README.md           # Project overview
├── LICENSE             # License information
└── .gitignore          # Git ignore rules
```

## Source Directory Structure

```
src/
├── growth/                     # Main package
│   ├── __init__.py
│   ├── cli/                    # Command-line interface
│   │   ├── __init__.py
│   │   ├── commands/
│   │   └── cli_app.py
│   ├── core/                   # Core application logic
│   │   ├── __init__.py
│   │   ├── application.py
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── study_plan.py
│   │   │   ├── task.py
│   │   │   └── validators.py
│   │   └── ports/
│   │       ├── __init__.py
│   │       ├── task_builder.py
│   │       └── validator.py
│   ├── infrastructure/         # External integrations
│   │   ├── __init__.py
│   │   ├── todoist/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── task_builder.py
│   │   │   └── validator.py
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── yaml_parser.py
│   │   │   └── json_parser.py
│   │   └── loaders/
│   │       ├── __init__.py
│   │       └── yaml_loader.py
│   ├── presentation/           # User interfaces
│   │   ├── __init__.py
│   │   └── cli/
│   │       ├── __init__.py
│   │       ├── commands/
│   │       │   ├── __init__.py
│   │       │   ├── study_plan.py
│   │       │   └── tasks.py
│   │       └── cli_app.py
│   └── config/                 # Configuration management
│       ├── __init__.py
│       └── settings.py
└── setup.py                    # Package setup
```

## Test Directory Structure

```
tests/
├── __init__.py
├── conftest.py              # pytest configuration
├── test_core/               # Core logic tests
│   ├── __init__.py
│   ├── test_application.py
│   └── test_domain/
│       ├── __init__.py
│       ├── test_study_plan.py
│       └── test_task.py
├── test_infrastructure/     # Integration tests
│   ├── __init__.py
│   ├── test_todoist/
│   │   ├── __init__.py
│   │   ├── test_client.py
│   │   └── test_task_builder.py
│   ├── test_parsers/
│   │   ├── __init__.py
│   │   └── test_yaml_parser.py
│   └── test_loaders/
│       ├── __init__.py
│       └── test_yaml_loader.py
└── test_presentation/       # UI tests
    ├── __init__.py
    └── test_cli/
        ├── __init__.py
        └── test_commands.py
```

## Configuration Directory

```
config/
├── study_plans/             # Example study plans
│   ├── placement_exam.yaml
│   └── programming_fundamentals.yaml
├── templates/               # Configuration templates
│   └── config.template.yaml
└── default_config.yaml      # Default configuration
```

## Documentation Directory

```
docs/
├── architecture/            # Architecture documentation
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   ├── AGENTS.md
│   ├── CONTRIBUTING.md
│   └── PROJECT_RULES.md
├── api/                     # API documentation
├── user_guides/             # User guides
├── developer_guides/        # Developer guides
└── diagrams/                # System diagrams
```

## Scripts Directory

```
scripts/
├── setup.sh                 # Development environment setup
├── build.sh                 # Build scripts
├── deploy.sh                # Deployment scripts
└── utils/                   # Utility scripts
```

## Key Design Decisions

### Separation of Concerns
- `core/` contains business logic independent of frameworks
- `infrastructure/` contains external service integrations
- `presentation/` contains user interface code
- `config/` contains configuration management

### Extensibility
- Each major component is in its own directory
- Plugin architecture supported through ports and adapters pattern
- New integrations can be added without modifying core logic

### Testability
- Tests mirror the source structure for easy navigation
- Each component has dedicated test files
- Integration tests are separated from unit tests

### Maintainability
- Clear naming conventions
- Single responsibility principle applied to directories
- Dependency direction flows inward (presentation -> core -> infrastructure)