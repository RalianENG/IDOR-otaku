# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | :white_check_mark: |
| 0.3.x   | :white_check_mark: |
| < 0.3   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email: **ralianengineering@gmail.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Impact assessment (if possible)

You can expect an initial response within 72 hours. We will work with you to understand the issue and coordinate a fix before any public disclosure.

## Scope

This policy covers vulnerabilities in the `idotaku` tool itself, including:
- Code injection through crafted input (config files, report files, HAR files)
- XSS or script injection in HTML exports (`chain --html`, `sequence --html`)
- Unintended data exposure in generated reports or SARIF/CSV exports
- SSRF or unintended network access via the `verify` command
- ReDoS through user-supplied regex patterns in configuration
- Dependency vulnerabilities

This policy does **not** cover:
- Vulnerabilities found in systems tested using this tool
- Issues in mitmproxy or other upstream dependencies (report those to their respective projects)
- Security of the target systems accessed via `verify` command (users are responsible for obtaining proper authorization)