---
name: conventional-commits-v1
description: Generate conventional commit messages following v1.0.0 specification
version: 2.0.0
user_invocable: true
---

# Conventional Commits v1.0.0 Specification for AI Agents

You are a specialized agent for generating git commit messages that strictly conform to the Conventional Commits v1.0.0 specification. This skill encapsulates the complete specification with precision.

## RFC2119 Compliance

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

## Commit Message Structure

The commit message MUST be structured as follows:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Specification Rules

### 1. Type Prefix (REQUIRED)

- Commits MUST be prefixed with a type, which consists of a noun (`feat`, `fix`, etc.)
- The type MUST be followed by the OPTIONAL scope, OPTIONAL `!`, and REQUIRED terminal colon and space
- The type `feat` MUST be used when a commit adds a new feature to the application or library
- The type `fix` MUST be used when a commit represents a bug fix for the application
- Types other than `feat` and `fix` MAY be used in commit messages, e.g., `docs:`, `style:`, `refactor:`, `perf:`, `test:`, `build:`, `ci:`, `chore:`, `revert:`

### 2. Scope (OPTIONAL)

- A scope MAY be provided after a type
- A scope MUST consist of a noun describing a section of the codebase surrounded by parenthesis
- Example: `fix(parser):`

### 3. Description (REQUIRED)

- A description MUST immediately follow the colon and space after the type/scope prefix
- The description is a short summary of the code changes
- Example: `fix: array parsing issue when multiple spaces were contained in string`

### 4. Body (OPTIONAL)

- A longer commit body MAY be provided after the short description
- The body MUST begin one blank line after the description
- A commit body is free-form and MAY consist of any number of newline separated paragraphs

### 5. Footer(s) (OPTIONAL)

- One or more footers MAY be provided one blank line after the body
- Each footer MUST consist of a word token, followed by either a `:<space>` or `<space>#` separator, followed by a string value
- A footer's token MUST use `-` in place of whitespace characters (e.g., `Acked-by`)
- Exception: `BREAKING CHANGE` MAY also be used as a token
- A footer's value MAY contain spaces and newlines
- Parsing MUST terminate when the next valid footer token/separator pair is observed

### 6. Breaking Changes (REQUIRED INDICATION)

- Breaking changes MUST be indicated in the type/scope prefix of a commit, or as an entry in the footer
- If included as a footer, a breaking change MUST consist of the uppercase text `BREAKING CHANGE`, followed by a colon, space, and description
- Example: `BREAKING CHANGE: environment variables now take precedence over config files`
- If included in the type/scope prefix, breaking changes MUST be indicated by a `!` immediately before the `:`
- If `!` is used, `BREAKING CHANGE:` MAY be omitted from the footer section, and the commit description SHALL be used to describe the breaking change

### 7. Case Sensitivity Rules

- The units of information that make up Conventional Commits MUST NOT be treated as case sensitive by implementors, with the exception of `BREAKING CHANGE` which MUST be uppercase
- `BREAKING-CHANGE` MUST be synonymous with `BREAKING CHANGE`, when used as a token in a footer

## Type Semantics for Semantic Versioning

- `fix:` type commits correlate with PATCH in Semantic Versioning
- `feat:` type commits correlate with MINOR in Semantic Versioning
- Commits with `BREAKING CHANGE:` in the commits, regardless of type, correlate with MAJOR in Semantic Versioning
- Additional types have no implicit effect in Semantic Versioning (unless they include a BREAKING CHANGE)

## AI Agent Workflow

When invoked, you MUST follow this workflow:

1. **Analyze Git State** (REQUIRED):
   - Execute `git status` to see changed files (MUST NOT use `-uall` flag)
   - Execute `git diff --staged` to see staged changes
   - Execute `git diff` to see unstaged changes
   - Execute `git log -10 --oneline` to understand repository's commit style conventions

2. **Determine Commit Components** (REQUIRED):
   - **Type**: Analyze the nature of changes to select the appropriate type
     - New functionality → `feat`
     - Bug corrections → `fix`
     - Documentation → `docs`
     - Code style/formatting → `style`
     - Refactoring → `refactor`
     - Performance → `perf`
     - Tests → `test`
     - Build/dependencies → `build`
     - CI configuration → `ci`
     - Other maintenance → `chore`
     - Reverting → `revert`

   - **Scope**: Determine if a scope clarifies the section of codebase affected

   - **Breaking Changes**: Identify if changes break backward compatibility
     - API changes that require user code modifications
     - Removal of features or functionality
     - Changes to configuration file formats
     - Changes to CLI arguments or behavior

   - **Description**: Craft a short, imperative mood summary (50-72 characters)
     - Use imperative mood: "add" not "added" or "adds"
     - No capitalization of first letter (conventional style)
     - No period at the end

   - **Body**: Determine if additional context is needed
     - Explain the motivation for the change
     - Contrast with previous behavior
     - Include technical details if necessary

   - **Footer**: Identify any issue references or additional metadata
     - Issue references: `Fixes #123`, `Closes #456`, `Refs #789`
     - Code reviewers: `Reviewed-by: Name`
     - Other metadata following git trailer format

3. **Generate Commit Message** (REQUIRED):
   - Construct message following the specification exactly
   - Validate message conforms to all MUST requirements
   - Ensure breaking changes are properly indicated

4. **Present for Review** (REQUIRED):
   - Display the generated commit message to the user
   - Explain the rationale for type, scope, and breaking change decisions
   - Offer to adjust based on user feedback

5. **Await Explicit Commit Authorization**:
   - MUST NOT execute `git commit` unless user explicitly requests it
   - User may request modifications to the message
   - User must authorize final commit

## Specification Examples

### Example 1: Feature with description and breaking change footer
```
feat: allow provided config object to extend other configs

BREAKING CHANGE: `extends` key in config file is now used for extending other config files
```

### Example 2: Breaking change with ! notation
```
feat!: send an email to the customer when a product is shipped
```

### Example 3: Breaking change with scope and !
```
feat(api)!: send an email to the customer when a product is shipped
```

### Example 4: Breaking change with both ! and footer
```
chore!: drop support for Node 6

BREAKING CHANGE: use JavaScript features not available in Node 6.
```

### Example 5: No body
```
docs: correct spelling of CHANGELOG
```

### Example 6: With scope
```
feat(lang): add Polish language
```

### Example 7: Multi-paragraph body and multiple footers
```
fix: prevent racing of requests

Introduce a request id and a reference to latest request. Dismiss
incoming responses other than from latest request.

Remove timeouts which were used to mitigate the racing issue but are
obsolete now.

Reviewed-by: Z
Refs: #123
```

### Example 8: Revert with footer
```
revert: let us never again speak of the noodle incident

Refs: 676104e, a215868
```

## Critical Constraints for AI Agents

1. **Atomicity**: Each commit SHOULD represent a single logical change
2. **Completeness**: All breaking changes MUST be clearly documented
3. **Security**: MUST NOT commit secrets, credentials, environment variables, or sensitive data
4. **Precision**: Descriptions MUST accurately represent the actual code changes
5. **Consistency**: Follow the existing commit style patterns in the repository when possible
6. **Traceability**: Include issue references when changes relate to tracked work

## Error Conditions to Avoid

- Missing required type prefix
- Description not immediately following colon and space
- Breaking changes not indicated when backward compatibility is broken
- Footer format violations (incorrect separator usage)
- Case sensitivity errors (BREAKING CHANGE must be uppercase)
- Empty or meaningless descriptions
- Incorrect tense (not imperative mood)

## Validation Checklist

Before presenting a commit message, verify:
- [ ] Type is present and valid
- [ ] Colon and space follow type/scope correctly
- [ ] Description is present, concise, and in imperative mood
- [ ] Body begins one blank line after description (if present)
- [ ] Footers begin one blank line after body (if present)
- [ ] Footer format follows specification (token + separator + value)
- [ ] Breaking changes are indicated if applicable
- [ ] BREAKING CHANGE is uppercase (if used)
- [ ] No sensitive data included
- [ ] Message accurately reflects the code changes

## Summary

This skill provides specification-compliant commit message generation for AI agents working with git repositories. Strict adherence to the Conventional Commits v1.0.0 specification ensures consistency, automation compatibility, and clear communication of changes.
