# Feedback on Nebius Token Factory, NVIDIA Nemotron, and Tavily

This document is a structured feedback log for the Mnemos hackathon submission. Complete the observation fields after running real requests. Do not present expected behavior as measured results.

## Test environment

- Test date:
- Region / deployment:
- Token Factory API endpoint:
- Model IDs tested:
- Tavily API/SDK version:
- Number of requests per test:
- Test prompt set or reproduction steps:

## Nebius Token Factory

### What worked
- Record whether authentication, model listing, chat completions, and error responses worked in the tested environment.
- Include reproducible request details without including API keys or private data.

### Issues observed
- Request ID / timestamp (if available):
- Endpoint and model ID:
- HTTP status and sanitized error:
- Expected result:
- Actual result:

### Actionable suggestions
- Report any improvements supported by tests, such as clearer model-access errors, model catalog discoverability, latency visibility, or SDK examples. Mark suggestions as suggestions rather than observed defects.

## NVIDIA Nemotron model behavior

Compare the configured fast model and reasoning model on the same representative prompts.

| Prompt / task | Model ID | Latency | Output quality notes | Errors / retries |
| --- | --- | --- | --- | --- |
| Short direct answer | | | | |
| Memory extraction | | | | |
| Research synthesis | | | | |
| Long-context follow-up | | | | |

Record measured latency and quality observations here. Do not claim a context window, latency profile, or quality result without verifying the model's current documentation or measuring it.

## Tavily

| Query | Search succeeded? | Useful sources? | Missing / stale sources | Notes |
| --- | --- | --- | --- | --- |
| Current technology update | | | | |
| Narrow factual query | | | | |
| Multi-source research question | | | | |

Record whether the returned sources were relevant, current, and sufficient for the generated answer. Note whether failures were network errors, API errors, empty results, or quota limits.

## Summary for the submission

- Most useful capability observed:
- Most important limitation observed:
- Reproduction steps:
- Suggested improvement:
- Evidence collected (sanitized logs, request IDs, measurements):

**Integrity note:** This file intentionally starts as a template. Replace the prompts above with evidence from your own tests before submitting feedback; do not submit unverified claims as first-hand observations.
