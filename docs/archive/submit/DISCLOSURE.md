# Fresh Project Disclosure

This document fulfills the fresh-project disclosure requirement of the AWS Agents for Humans Hackathon rules [R1].

## Project Origin

**Recoup** was created as a new project during the AWS Agents for Humans Hackathon submission window (August 10 – September 14, 2026).

- **Repository created:** September 1, 2026
- **First commit:** September 1, 2026 (verifiable via `git log`)
- **Submission deadline:** September 14, 2026 at 5:00 PM PDT

## Pre-existing Materials

The following materials were created or used before the hackathon period:

| Material | Description | Used as |
|----------|-------------|---------|
| Strands Agents SDK | Open-source AWS SDK; publicly available | Dependency |
| AWS CDK | Open-source infrastructure library | Dependency |
| Next.js, FastAPI, Pydantic | Open-source frameworks | Dependencies |
| AWS SLA documentation | Publicly available at aws.amazon.com/api-gateway/sla/ | Reference for SLA catalog |

## What is New

All application code, architecture decisions, domain models, the SLA catalog structure, evaluation scenarios, CDK stacks, UI components, Cedar policies, and this repository were created during the hackathon window.

## Team

Solo submission.

## Verification

```bash
git log --format="%ai %s" | head -10
```

The first commit timestamp will confirm the project was created after August 10, 2026.
