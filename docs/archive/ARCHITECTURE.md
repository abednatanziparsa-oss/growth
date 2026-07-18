# Growth Architecture

## Overview

Growth is a personal productivity system designed to be extensible and maintainable over the long term. It provides automation capabilities for Todoist with an initial focus on study plan management.

## Core Principles

- **Modularity**: Each component should be independently replaceable and extensible
- **Separation of Concerns**: Clear boundaries between different layers of the system
- **Extensibility**: Designed to support future features without major rewrites
- **Testability**: Each component should be easy to test in isolation
- **Maintainability**: Code should be clear and well-documented for long-term support

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Growth Application                       │
├─────────────────────────────────────────────────────────────┤
│                    Presentation Layer                       │
│  ┌───────────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │    CLI/API    │  │   Web UI      │  │     TUI        │  │
│  └───────────────┘  └───────────────┘  └────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    Application Layer                        │
│  ┌───────────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │ Task Builders │  │  Validators   │  │   Schedulers   │  │
│  └───────────────┘  └───────────────┘  └────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                   Business Logic Layer                      │
│  ┌───────────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │ Study Plans   │  │    Tasks      │  │  Calendars     │  │
│  └───────────────┘  └───────────────┘  └────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    Integration Layer                        │
│  ┌───────────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │ Todoist API   │  │ Obsidian API  │  │ Calendar APIs  │  │
│  └───────────────┘  └───────────────┘  └────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                     Data Access Layer                       │
│  ┌───────────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │   Loaders     │  │   Parsers     │  │ Configuration  │  │
│  └───────────────┘  └───────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Component Descriptions

### Presentation Layer
Handles all user interaction:
- CLI for command-line operations
- Web UI for browser-based interaction
- TUI for terminal-based interface

### Application Layer
Controls the main application flow:
- Task Builders: Creates tasks based on study plans
- Validators: Ensures data integrity
- Schedulers: Handles timing and recurrence

### Business Logic Layer
Domain-specific functionality:
- Study Plans: Manages different types of learning plans
- Tasks: Core task management functionality
- Calendars: Integration with calendar systems

### Integration Layer
External service connections:
- Todoist API: Primary integration point
- Obsidian API: For note-taking integration
- Calendar APIs: For scheduling integration

### Data Access Layer
Handles all data input/output:
- Loaders: Load data from various sources
- Parsers: Parse different data formats
- Configuration: Handle application settings

## Design Patterns

### Plugin Architecture
All major components follow a plugin pattern to allow easy extension:
```python
class TaskBuilder(ABC):
    @abstractmethod
    def build_tasks(self, plan: StudyPlan) -> List[Task]:
        pass

class TodoistTaskBuilder(TaskBuilder):
    def build_tasks(self, plan: StudyPlan) -> List[Task]:
        # Todoist-specific implementation
        pass
```

### Factory Pattern
For creating different types of components:
```python
class ComponentFactory:
    def create_task_builder(self, type: str) -> TaskBuilder:
        if type == "todoist":
            return TodoistTaskBuilder()
        elif type == "local":
            return LocalTaskBuilder()
```

### Dependency Injection
Components receive dependencies rather than creating them directly:
```python
class StudyPlanProcessor:
    def __init__(self, task_builder: TaskBuilder, validator: Validator):
        self.task_builder = task_builder
        self.validator = validator
```

## Data Flow

1. User provides input via CLI/Web UI/TUI
2. Input is parsed and validated
3. Business logic processes the data
4. Integration layer communicates with external services
5. Results are returned to the user interface

## Extensibility Points

1. **Task Builders**: Add new ways to create tasks
2. **Validators**: Add new validation rules
3. **Loaders**: Support new data sources
4. **Parsers**: Support new data formats
5. **Integrations**: Add new external service connections
6. **Study Plan Types**: Add new plan categories

## Technology Stack

- **Language**: Python 3.12+
- **Type Checking**: Full type hints throughout
- **Data Validation**: Pydantic for dataclasses
- **Configuration**: YAML for human-readable config
- **Logging**: Standard Python logging module
- **Testing**: pytest for unit testing
- **Documentation**: Sphinx for documentation generation

## Future Considerations

- REST API for web-based access
- GraphQL endpoint for flexible data querying
- WebSocket support for real-time updates
- Plugin system for third-party extensions
- Database integration for persistence beyond Todoist
- AI integration for automated study plan generation
- Machine learning for personalized scheduling