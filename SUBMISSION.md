# HackOS submission sheet — OVERTURN

Everything below is ready to paste into the submission form. Nothing here is
secret. Fill the two link fields once the repo and video are public.

## Fields

**Project name**
OVERTURN

**One-line pitch**
The denial, answered with evidence.

**Track**
Track 2 — The Agent That Can Explain Why

**Short description (100 words)**
OVERTURN is an agent that reads a health-insurance denial and the documents
behind it, finds the contradictions, re-queries the source, and drafts an
appeal packet a human can send. In the demo case, an insurer denied Ava's MRI
for four reasons: three are contradicted by the policy, the clinical record
and the procedure codes, and the fourth is a specialist letter that is
genuinely missing. OVERTURN rebuts the three with line-level citations and
refuses to invent the fourth. The packet scores 84/100 — solid, conditional —
and names the one action that takes it to 100.

**Long description (about 450 words)**
A denied health-insurance claim is an evidence problem before it is a legal
problem. The insurer gives reasons; the policy, the clinical record, the
explanation of benefits and the code tables either support those reasons or
contradict them. Most people cannot do that comparison, and the appeal window
closes.

OVERTURN is built for one worker, one denial, one document. In the case in this
repository, Ava is 34, in Sydney, and Northbridge Health denied claim
CLM-2026-0915 for an MRI of her lumbar spine. The denial gives four reasons.
OVERTURN reads seven source tables through Zetaris — policy clauses, denial
reasons, medical records, EOB, procedure codes, claim documents and ICD-10
descriptions — and runs a five-agent loop: a Planner decomposes the case, a
Reconciler builds a 47-line evidence ledger, a Critic attacks the emerging
appeal, an Advocate argues the insurer's side, and either can force a
re-query. A deterministic scorer and a Reporter produce the packet.

The result is specific. Reason 1 says the service is experimental; the cited
clause excludes spinal fusion and says it does not apply to diagnostic MRI.
Reason 2 cites the contrast procedure code; the order, EOB and record all use
the non-contrast code, which needs no prior authorisation. Reason 3 says no
conservative treatment is documented; the record contains twelve physiotherapy
sessions across twelve weeks, and the policy asks for six. Reason 4 is a
specialist referral letter that is genuinely absent. OVERTURN marks it
UNVERIFIED, names DOC-003, and does not fabricate it.

That refusal is the product. The packet scores 84/100 — solid, conditional —
because one required document is missing, and it shows the counterfactual:
supply DOC-003 and it becomes 100/ready. Every evidence line carries its source
row, verification status and a SHA-256 hash chained to the line before it.
Removing a load-bearing source drops the score from 84 to 65, so every citation
has to earn its place.

The output is one document a human can review and send: a cover letter, four
rebuttals with citations, the evidence map, and a missing-evidence checklist.
It is not medical or legal advice, and it does not predict the insurer's
decision. It gives a person the file they need to argue their own case.

**Sponsor technology explanation**
Paste the contents of `SUBMISSION_COPY.md` (four paragraphs, ~450 words).

**GitHub repository**
`https://github.com/<your-account>/overturn` — replace `<your-account>` with the
account or org the repository is published under. The owner is deliberately
left blank here.

**Demo video**
`video/out/overturn-demo.mp4` — 2 min 20 s, 1920×1080, 30 fps, H.264/AAC.
Upload to YouTube (unlisted or public) and paste the link here.

**Slide deck**
`deck/OVERTURN-deck.pdf` — 15 pages, 16:9. Also in the repo.

## Declarations

**Pre-existing components**
None. OVERTURN's product code, data fixtures, film and deck were created during
the build window (22–27 October 2026). No pre-existing product code is included.
The third-party libraries and fonts are listed in `THIRD_PARTY.md`.

**Secrets**
No keys are committed. `.env` is gitignored; `.env.example` contains
placeholders only.

**Honest verification status**
SAMPLE_MODE is fully verified: 36 tests pass, and `python -m overturn.run
--case ava --out out/` produces the 84/conditional packet with no credentials.
The live Zetaris, Meterless Nightshift, H-MEM, World Model and NVIDIA Nemotron
paths are implemented and contract-tested against local HTTP doubles, but no
live run was made because this machine has no sponsor credentials. The
submission states this plainly rather than implying a live run.

## Before you press submit

- [ ] Create the public repo and push (see the command in the handoff).
- [ ] Upload `video/out/overturn-demo.mp4` to YouTube; paste the link.
- [ ] Confirm the repo opens logged-out and the README renders.
- [ ] Upload or link `deck/OVERTURN-deck.pdf`.
- [ ] Paste `SUBMISSION_COPY.md` into the sponsor-technology field.
- [ ] Select Track 2.
- [ ] Submit before 27 October 2026, 23:45 UTC.
