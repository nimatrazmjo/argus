# PERSONAS — who it's for

## 1. Platform / DevOps engineer (primary operator)
Runs Argus itself. Goal: stand up and operate the stack inside k8s, keep storage cost and
cardinality under control, onboard teams, and stay air-gap and ATO compliant. Hires Argus to
replace a Datadog bill and a vendor dependency with something they fully own. Success =
onboarding a service is one annotation, and retention/cost do not creep.

## 2. Application / service team (consumer)
Owns one of the ~10 (-> 50) internal apps. Goal: see their service's health, traces, and logs
and get paged when it breaks — without becoming observability experts. Hires Argus for "add
one line, get full visibility." Success = they never hand-wire a pipeline.

## 3. Security / compliance reviewer (gatekeeper)
Owns the ATO and the data-handling rules. Goal: confirm no regulated PII/CJIS data is stored
unredacted, nothing phones home, and auth/RBAC ties to the agency IdP. Hires Argus to be
auditable and boundary-respecting. Success = redaction is provable and the component/ATO
surface is small.
