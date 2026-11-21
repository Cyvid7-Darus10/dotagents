---
description: Enforce TDD workflow for Swift. Write Swift Testing tests first, then implement. Verify 80%+ coverage.
disable-model-invocation: true
---

# Swift TDD Command

This command enforces test-driven development methodology for Swift code using Swift Testing and protocol-based mocking.

## What This Command Does

1. **Define Types/Protocols**: Scaffold function signatures and protocol interfaces first
2. **Write Swift Tests**: Create comprehensive `@Test` functions (RED)
3. **Run Tests**: Verify tests fail for the right reason
4. **Implement Code**: Write minimal code to pass (GREEN)
5. **Refactor**: Improve while keeping tests green
6. **Check Coverage**: Ensure 80%+ coverage

## When to Use

Use `/swift-test` when:
- Implementing new Swift functions or types
- Adding test coverage to existing Swift code
- Fixing bugs (write failing test first)
- Building critical business logic
- Learning TDD workflow in Swift

## TDD Cycle

```
RED     -> Write failing @Test
GREEN   -> Implement minimal code to pass
REFACTOR -> Improve code, tests stay green
REPEAT  -> Next test case
```

## Example Session

````text
User: /swift-test I need a function to validate email addresses

Agent:
# TDD Session: Email Validator

## Step 1: Define Interface

```swift
// EmailValidator.swift
struct EmailValidator {
    enum ValidationError: Error, Equatable {
        case empty
        case missingAtSign
        case invalidFormat
    }

    func validate(_ email: String) throws(ValidationError) -> String {
        fatalError("Not implemented")
    }
}
```

## Step 2: Write Swift Tests (RED)

```swift
// EmailValidatorTests.swift
import Testing

@Suite("EmailValidator Tests")
struct EmailValidatorTests {
    let validator = EmailValidator()

    @Test("Valid email returns the email")
    func validEmail() throws {
        let result = try validator.validate("user@example.com")
        #expect(result == "user@example.com")
    }

    @Test("Empty email throws empty error")
    func emptyEmail() {
        #expect(throws: EmailValidator.ValidationError.empty) {
            try validator.validate("")
        }
    }

    @Test("Email without @ throws missingAtSign")
    func missingAtSign() {
        #expect(throws: EmailValidator.ValidationError.missingAtSign) {
            try validator.validate("userexample.com")
        }
    }

    @Test("Validates common email formats", arguments: [
        "user@example.com",
        "name+tag@domain.co",
        "first.last@sub.domain.org",
    ])
    func validFormats(email: String) throws {
        let result = try validator.validate(email)
        #expect(result == email)
    }

    @Test("Rejects invalid formats", arguments: [
        "no-domain@",
        "@no-local",
        "spaces in@email.com",
    ])
    func invalidFormats(email: String) {
        #expect(throws: EmailValidator.ValidationError.invalidFormat) {
            try validator.validate(email)
        }
    }
}
```

## Step 3: Run Tests - Verify FAIL

```bash
$ swift test

EmailValidatorTests > Valid email returns the email FAILED
  Fatal error: Not implemented

FAILED (5 tests, 0 passed, 5 failed)
```

✓ Tests fail as expected (fatalError).

## Step 4: Implement Minimal Code (GREEN)

```swift
// EmailValidator.swift
struct EmailValidator {
    enum ValidationError: Error, Equatable {
        case empty
        case missingAtSign
        case invalidFormat
    }

    private static let pattern = #"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"#

    func validate(_ email: String) throws(ValidationError) -> String {
        guard !email.isEmpty else { throw .empty }
        guard email.contains("@") else { throw .missingAtSign }
        guard email.range(of: Self.pattern, options: .regularExpression) != nil else {
            throw .invalidFormat
        }
        return email
    }
}
```

## Step 5: Run Tests - Verify PASS

```bash
$ swift test

EmailValidatorTests > Valid email returns the email PASSED
EmailValidatorTests > Empty email throws empty error PASSED
EmailValidatorTests > Email without @ throws missingAtSign PASSED
EmailValidatorTests > Validates common email formats :: user@example.com PASSED
EmailValidatorTests > Validates common email formats :: name+tag@domain.co PASSED
EmailValidatorTests > Validates common email formats :: first.last@sub.domain.org PASSED
EmailValidatorTests > Rejects invalid formats :: no-domain@ PASSED
EmailValidatorTests > Rejects invalid formats :: @no-local PASSED
EmailValidatorTests > Rejects invalid formats :: spaces in@email.com PASSED

PASSED (9 tests, 9 passed, 0 failed)
```

✓ All tests passing!

## Step 6: Check Coverage

```bash
$ swift test --enable-code-coverage

Coverage: 100.0% of statements
```

✓ Coverage: 100%

## TDD Complete!
````

## Test Patterns

### Basic @Test

```swift
@Test("Adding two positive numbers")
func addPositiveNumbers() {
    #expect(Calculator.add(2, 3) == 5)
}
```

### @Suite for Organization

```swift
@Suite("UserService Tests")
struct UserServiceTests {
    let mockRepo = MockUserRepository()
    let service: UserService

    init() {
        service = UserService(repository: mockRepo)
    }

    @Test("Fetch user by ID")
    func fetchUser() async throws {
        mockRepo.stubbedUser = User(id: UUID(), name: "Alice")
        let user = try await service.getUser(id: mockRepo.stubbedUser!.id)
        #expect(user.name == "Alice")
    }
}
```

### Parameterized Tests

```swift
@Test("All priority levels have names", arguments: Priority.allCases)
func priorityNames(priority: Priority) {
    #expect(!priority.displayName.isEmpty)
}
```

### Async Testing

```swift
@Test("Concurrent fetch completes")
func concurrentFetch() async throws {
    async let tasks = service.fetchTasks()
    async let user = service.fetchUser()
    let result = try await (tasks, user)
    #expect(!result.0.isEmpty)
}
```

### ViewModel Testing

```swift
@Test("Load tasks updates state")
@MainActor
func loadTasks() async {
    let viewModel = TaskListViewModel(repository: MockTaskRepository())
    await viewModel.loadTasks()
    #expect(!viewModel.tasks.isEmpty)
}
```

## Coverage Commands

```bash
# Run tests with coverage (SPM)
swift test --enable-code-coverage

# Run specific test
swift test --filter "EmailValidatorTests"

# Xcode: run tests
xcodebuild test -scheme MyApp -destination 'platform=iOS Simulator,name=iPhone 16'

# Xcode: run specific test
xcodebuild test -scheme MyApp -only-testing:MyAppTests/UserServiceTests
```

## Coverage Targets

| Code Type | Target |
|-----------|--------|
| Critical business logic | 100% |
| Public APIs / Services | 90%+ |
| General code | 80%+ |
| Generated / UI boilerplate | Exclude |

## TDD Best Practices

**DO:**
- Write test FIRST, before any implementation
- Run tests after each change
- Use `#expect` and `#require` for clear assertions
- Use protocol-based mocks (no third-party framework needed)
- Use `@MainActor` for ViewModel tests
- Use parameterized tests for data-driven validation
- Include edge cases (empty, nil, boundary values)

**DON'T:**
- Write implementation before tests
- Skip the RED phase
- Test private functions directly
- Use `sleep()` in async tests
- Force-unwrap in tests (use `#require`)
- Mix XCTest and Swift Testing in the same file

## Related Commands

- `/swift-review` - Review code after implementation
- `/build-fix` - Fix build errors
- `/verify` - Run full verification loop

## Related

- Skill: `skills/swift-testing/`
- Skill: `skills/tdd-workflow/`
