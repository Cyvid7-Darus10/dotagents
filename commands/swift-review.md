---
description: Comprehensive Swift code review for idiomatic patterns, concurrency safety, SwiftUI best practices, and security. Invokes the swift-reviewer agent.
---

# Swift Code Review

This command invokes the **swift-reviewer** agent for comprehensive Swift-specific code review.

## What This Command Does

1. **Identify Swift Changes**: Find modified `.swift` files via `git diff`
2. **Run Build Check**: Execute `swift build` or `xcodebuild build`
3. **Security Scan**: Check for hardcoded secrets, UserDefaults misuse, ATS exceptions
4. **Concurrency Review**: Analyze Sendable conformance, actor isolation, data races
5. **SwiftUI Review**: Check state management, side effects, view composition
6. **Generate Report**: Categorize issues by severity

## When to Use

Use `/swift-review` when:
- After writing or modifying Swift code
- Before committing Swift changes
- Reviewing pull requests with Swift code
- Onboarding to a new Swift codebase
- Learning idiomatic Swift patterns

## Review Categories

### CRITICAL (Must Fix)
- Data races on shared mutable state
- Sendable violations crossing isolation boundaries
- Force unwrap `!` without justification
- Hardcoded credentials or secrets
- Retain cycles in closures
- UserDefaults storing sensitive data

### HIGH (Should Fix)
- `var` where `let` suffices
- Class where struct works
- Side effects in SwiftUI `body`
- Missing `@MainActor` on ViewModels
- Unstructured `Task {}` without cancellation
- Missing `.id()` on ForEach items

### MEDIUM (Consider)
- Fat protocols (split into smaller ones)
- Concrete type dependencies (use protocols)
- Empty catch blocks
- Missing accessibility labels
- Hardcoded user-facing strings

## Automated Checks Run

```bash
# Build check (SPM)
swift build 2>&1 | head -50

# Build check (Xcode)
xcodebuild build -scheme MyApp -destination 'platform=iOS Simulator,name=iPhone 16' 2>&1 | tail -30

# Run tests
swift test 2>&1 | tail -30

# Check for force unwraps
grep -rn '!' --include='*.swift' . | grep -v '//' | grep -v 'IBOutlet' | head -20

# Check for print statements
grep -rn 'print(' --include='*.swift' . | grep -v 'Tests/' | grep -v '//' | head -20
```

## Example Usage

````text
User: /swift-review

Agent:
# Swift Code Review Report

## Files Reviewed
- Isip/Services/CaptureService.swift (modified)
- Isip/Views/Capture/CaptureBar.swift (modified)

## Build Results
✓ Build: Successful
✓ Tests: 12 passed

## Issues Found

[CRITICAL] Mutable shared state without actor protection
File: Isip/Services/CaptureService.swift:15
Issue: `var recordings: [Recording]` in a class accessed from multiple async contexts.
```swift
class CaptureService {
    var recordings: [Recording] = []  // Not thread-safe
}
```
Fix: Convert to actor or protect with `@MainActor`
```swift
actor CaptureService {
    private var recordings: [Recording] = []
}
```

[HIGH] Side effect in SwiftUI body
File: Isip/Views/Capture/CaptureBar.swift:32
Issue: Network call triggered during view body evaluation
```swift
var body: some View {
    let _ = loadRecordings()  // Called every render
    // ...
}
```
Fix: Move to `.task {}` modifier
```swift
var body: some View {
    content
        .task { await loadRecordings() }
}
```

## Summary
- CRITICAL: 1
- HIGH: 1
- MEDIUM: 0

Recommendation: ❌ Block merge until CRITICAL issue is fixed
````

## Approval Criteria

| Status | Condition |
|--------|-----------|
| ✅ Approve | No CRITICAL or HIGH issues |
| ⚠️ Warning | Only MEDIUM issues (merge with caution) |
| ❌ Block | CRITICAL or HIGH issues found |

## Integration with Other Commands

- Use `/swift-test` first to ensure tests pass
- Use `/build-fix` if build errors occur
- Use `/swift-review` before committing
- Use `/code-review` for non-Swift-specific concerns

## Related

- Agent: `agents/swift-reviewer.md`
- Skills: `skills/swift-patterns/`, `skills/swift-testing/`
