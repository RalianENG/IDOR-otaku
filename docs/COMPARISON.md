# Comparison with Other Tools

idotaku occupies a specific niche in the IDOR testing landscape. This document explains how it relates to other tools and when to use each one.

## TL;DR

| | idotaku | Autorize | AuthMatrix | ZAP Access Control |
|---|:---:|:---:|:---:|:---:|
| **Approach** | ID flow tracking | Session replay | Access control matrix | Rule-based replay |
| **Requires Burp** | No | Yes | Yes | No |
| **Setup effort** | Low | Low | High | High |
| **Finds candidates** | Yes | - | - | - |
| **Verifies access** | No | Yes | Yes | Yes |
| **Parameter chains** | Yes | No | Partial | No |
| **HAR import** | Yes | No | No | No |
| **SARIF / CI/CD** | Yes | No | No | Partial |
| **Multi-role testing** | No | 2 roles | Unlimited | Unlimited |

## How idotaku Differs

### Reconnaissance vs. Verification

Most IDOR tools answer: _"Can User B access User A's resource?"_ — they **verify** broken access controls.

idotaku answers a different question: _"Which IDs exist, where do they come from, and where are they used?"_ — it **maps the attack surface**.

This distinction matters because:

- **Verification tools** need you to already know what to test (which endpoints, which IDs).
- **idotaku** helps you _discover_ what to test in the first place.

### Typical Workflow

```
1. Capture traffic        →  idotaku (proxy or HAR import)
2. Map ID landscape       →  idotaku report / chain / sequence
3. Identify candidates    →  idotaku score
4. Verify candidates      →  Autorize, Burp Repeater, or manual testing
5. Report findings        →  idotaku csv / sarif
```

## Tool-by-Tool Comparison

### Autorize (Burp Suite Extension)

**What it does:** Automatically replays every proxied request with a low-privileged session token and compares responses. Color-codes results as Bypassed (red) or Enforced (green).

**Strengths:**
- Fully automatic once configured
- Very fast for broad coverage
- Popular in bug bounty community

**Limitations:**
- Requires Burp Suite
- Only swaps session tokens — does not manipulate object IDs
- No understanding of ID relationships or parameter chains
- Two-context only (privileged vs. low-privileged)

**When to use Autorize:** You have Burp Suite and want to quickly verify access controls across an application.

**When to use idotaku instead:** You want to understand the full ID landscape before testing, need HAR-based offline analysis, or don't have Burp Suite.

### AuthMatrix (Burp Suite Extension)

**What it does:** Structured access control matrix testing. Define roles, users, endpoints, and expected permissions, then batch-test all combinations.

**Strengths:**
- Best for complex role hierarchies (admin, manager, editor, viewer, etc.)
- Cross-user chains can inject one user's IDs into another user's requests
- Save/load for regression testing

**Limitations:**
- Requires Burp Suite + significant manual configuration
- Last updated in 2021
- Only tests requests you manually add

**When to use AuthMatrix:** You need thorough, structured authorization testing against a complex RBAC system.

**When to use idotaku instead:** You want automated discovery of ID relationships without manual endpoint-by-endpoint setup.

### OWASP ZAP Access Control Testing

**What it does:** Rule-based authorization testing. Define which users should access which URLs, then ZAP replays and checks.

**Strengths:**
- Free and open-source
- CI/CD integration via Docker and REST API
- Active OWASP project

**Limitations:**
- Requires manual access rule definition
- No ID tracking or parameter chain analysis
- Heavy application for simple use cases

**When to use ZAP:** You need a free, CI/CD-integrated verification tool with full DAST capabilities.

**When to use idotaku instead:** You want lightweight ID-focused analysis without defining access rules upfront.

### Nuclei (ProjectDiscovery)

**What it does:** Template-based vulnerability scanner. IDOR detection requires writing custom YAML templates.

**Strengths:**
- Fast, Go-based CLI
- Massive template library (6,500+)
- Excellent CI/CD integration

**Limitations:**
- No built-in IDOR detection — requires custom templates
- Cannot dynamically reason about authorization
- Best for known patterns, not business logic

**When to use Nuclei:** You have known IDOR patterns to regression-test.

**When to use idotaku instead:** You're exploring an unknown application and need to discover ID patterns first.

### fuzz-lightyear (Yelp)

**What it does:** Stateful Swagger/OpenAPI fuzzing that compares responses between authorized and attacker sessions.

**Strengths:**
- Designed for microservices
- CI/CD native
- Automatic test generation from API specs

**Limitations:**
- Requires Swagger/OpenAPI specification
- Low maintenance activity
- Requires custom fixture setup

**When to use fuzz-lightyear:** You have OpenAPI specs and want automated API authorization testing.

**When to use idotaku instead:** You don't have API specs, or want to analyze real traffic rather than generated requests.

## Summary

| Your situation | Recommended tool |
|---|---|
| I want to **map ID flows** before testing | **idotaku** |
| I want to **verify access controls** quickly | **Autorize** |
| I have a **complex RBAC** system to audit | **AuthMatrix** |
| I need **free verification** with CI/CD | **ZAP Access Control** |
| I have **OpenAPI specs** to fuzz | **fuzz-lightyear** |
| I want to **regression-test** known patterns | **Nuclei** |
| I have **HAR files** to analyze offline | **idotaku** |
| I need **SARIF output** for GitHub | **idotaku** |

idotaku works best as the **first step** in your IDOR testing workflow — use it to discover the attack surface, then hand off candidates to verification tools.
