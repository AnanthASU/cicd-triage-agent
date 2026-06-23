# CI/CD Failure Triage Report

**Source:** `schema_failure.log`  
**Category:** Schema or API contract failure  
**Confidence:** 0.97  
**Owner hint:** Backend/API owner or integration owner who changed payload shape, schema, or mappings.

## Likely Root Cause

Validation failed because produced data does not match expected schema/API/XML/XSD contract.

## Recommended Actions

- Compare expected schema with actual payload from the failing log.
- Check optional vs required fields and default values.
- Add or update contract tests for the changed field.
- Confirm downstream consumers can handle the changed schema.

## Impacted Areas

- `EstimateProfilePayload.js`
- `MCEProfile.xsd`
- `Node/npm dependency chain`
- `Schema / API contract validation`

## Evidence Lines

- Line 4: `Schema validation failed for EstimateProfilePayload.json`  
  - Signal: SCHEMA_OR_CONTRACT_FAILURE: Schema validation failure
- Line 5: `required property reviewerOrgCd is missing`  
  - Signal: SCHEMA_OR_CONTRACT_FAILURE: JSON schema mismatch
- Line 6: `additional property previousReviewerOrgCd does not match schema`  
  - Signal: SCHEMA_OR_CONTRACT_FAILURE: JSON schema mismatch
- Line 7: `XML validation failed against MCEProfile.xsd`  
  - Signal: SCHEMA_OR_CONTRACT_FAILURE: XML/XSD validation failure
- Line 9: `ERROR: contract test failed`  
  - Signal: SCHEMA_OR_CONTRACT_FAILURE: API contract failure

## Known Fix Matches

### Schema validation failure after payload shape change
- Category: `SCHEMA_OR_CONTRACT_FAILURE`
- Fix: Compare actual payload against schema. Add missing required fields or update the schema if the contract intentionally changed.
- Prevention: Add contract tests and sample payload validation in CI.

### React act warning caused by unresolved async state update
- Category: `FRONTEND_TEST_FAILURE`
- Fix: Await user events and async UI updates. Use await waitFor(...) around assertions triggered by state updates.
- Prevention: Standardize RTL helpers and avoid mixing fake timers with unresolved promises.

### Type drift between API model and UI props
- Category: `TYPESCRIPT_COMPILE_FAILURE`
- Fix: Update the interface/type at the boundary and adjust consuming selectors/components. Fix the first compiler error first.
- Prevention: Add contract tests or generated type validation at API boundaries.

## Teams / Slack Summary

> CI triage for `schema_failure.log`: Schema or API contract failure (confidence 0.97). Likely cause: Validation failed because produced data does not match expected schema/API/XML/XSD contract. First evidence: Schema validation failed for EstimateProfilePayload.json

## Guardrails

- This agent does not modify code or trigger deployments.
- Treat recommendations as triage assistance, not final approval.
- For customer or sensitive logs, remove secrets before sharing externally.