# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

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
- Code injection through crafted input (config files, report files)
- Unintended data exposure in generated reports
- Dependency vulnerabilities

This policy does **not** cover:
- Vulnerabilities found in systems tested using this tool
- Issues in mitmproxy or other upstream dependencies (report those to their respective projects)