You are an expert in linguistic analysis and argumentation theory. Your task is to analyze a given sentence (the "Target Component") within its preceding context. You must:
1.  Classify the Target Component using one of the labels from the "Classification Taxonomy".
2.  Identify all relationships the Target Component has with *previously seen* components from the "Context". Use the "Relationship Ontology" to define the relationship type.
3.  For each relationship, specify the direction:
    - "outgoing": The Target Component connects TO the context component (Target Component is the source)
    - "incoming": The Target Component receives FROM the context component (Target Component is the target)
4.  Provide a brief justification for your classification and for each relationship.
5.  You MUST respond with a single, valid JSON object and nothing else.

---
## Classification Taxonomy

### Argumentative Components
- Claim/Assertion: A statement presented as a fact or truth that the author intends to support.
- Premise/Justification: A statement offered as a reason, evidence, or justification in support of a Claim or Conclusion.
- Conclusion: A claim that is explicitly presented as the result of a line of reasoning (premises).
- Rebuttal/Counter-Claim: A statement that directly opposes or refutes a previously mentioned claim.
- Concession: A statement that acknowledges a point from an opposing view.
- Implication/Consequence: A statement describing what logically follows from a preceding claim or event.

### Definitional & Expository Components
- Formal Definition: A sentence that explicitly states the meaning of a term.
- Term Introduction/Stipulation: A statement where the author introduces a new term or stipulates a specific use.
- Example: A concrete case used to clarify an abstract concept, definition, or claim.
- Distinction/Disambiguation: A statement that explicitly draws a boundary or highlights the difference between two concepts.

### Attributive Components
- Position Statement: A summary or statement of a belief, theory, or argument held by another person or group.
- Quotation: A direct, verbatim excerpt from another source.
- Citation: The reference marker itself (e.g., ${}^1$, [^1], (Quine 1951)).

### Structural & Meta-Components
- Thesis: A high-level claim that encapsulates the central argument of the entire paper or a major section.
- Roadmap/Structural Statement: A sentence that outlines the structure of the argument or the steps the author will take.
- Problem Statement: A sentence that poses the central question or problem the text aims to address.

---
## Relationship Ontology

| Relationship Type | Description | Valid Source Nodes | Valid Target Nodes |
|---|---|---|---|
| Supports | Provides evidence or justification for | `Premise`, `Quotation`, `Example` | `Claim`, `Conclusion`, `Thesis` |
| Rebuts | Directly contradicts or argues against | `Rebuttal`, `Conclusion` | `Claim`, `Position Statement` |
| Clarifies | Makes a concept or statement clearer | `Definition`, `Distinction`, `Example` | `Claim`, `Premise`, `Term Introduction`|
| Illustrates | Provides a concrete example of | `Example` | `Definition`, `Claim`, `Distinction` |
| Implies | Logically leads to a consequence | `Claim`, `Premise` | `Implication`, `Conclusion` |
| Quantifies/Limits | Narrows the scope or concedes a point | `Concession` | `Claim`, `Thesis` |
| Addresses | Attempts to answer or solve | `Thesis`, `Claim` | `Problem Statement` |
| Outlines | Describes the structure of | `Roadmap` | `Thesis`, `Section` |
| Attributes | Assigns an idea to a source | `Position Statement`, `Quotation` | External Entity/Bibliography entry |
| Cites | Provides a reference for | Citation | External Document, Note |
| Continues | Follows sequentially in a description | any | any |

---
## Analysis Task

### Context (Previously Classified Components)
{{CONTEXT_JSON}}

### Target Component
{{TARGET_COMPONENT_JSON}}

---
## Required JSON Output Format

{
  "classification": "string (must be from the taxonomy)",
  "justification": "string (briefly explain why this classification was chosen)",
  "relationships": [
    {
      "target_id": "string (the ID of the component in the context)",
      "type": "string (must be from the relationship ontology)",
      "direction": "string (either 'outgoing' if this component connects to the target, or 'incoming' if this component receives from the target)",
      "justification": "string (briefly explain why this relationship exists)"
    }
  ]
}

---
## Examples

### Example 1
**Context:**
[
  {
    "id": "sec1_para1_comp1",
    "text": "Boghossian raises some preliminary concerns about my way of setting up the dialectic."
  }
]
**Target Component:**
{ "id": "sec1_para1_comp2", "text": "I will get them out of the way before moving on to the main issues." }

**Output:**
{
  "classification": "Roadmap/Structural Statement",
  "justification": "The author is stating the structure of the upcoming text, indicating they will address preliminary concerns first.",
  "relationships": [
    {
      "target_id": "sec1_para1_comp1",
      "type": "Continues",
      "direction": "incoming",
      "justification": "This statement follows sequentially from the previous one, explaining what the author will do about the concerns just mentioned."
    }
  ]
}

### Example 2
**Context:**
[
  {
    "id": "sec2_para6_comp3",
    "text": "His justification in Boghossian's sense for believing that B is irreducibly dependent on his having a visual impression as of there being an instance of modus ponens in front of him."
  },
  {
    "id": "sec2_para6_comp4",
    "text": "Moreover, the dependence seems to be epistemic by Boghossian's standards, for if visual impressions are justifiers in the way he suggests, the mathematician's visual impression is part of what justifies his belief that B, rather than a mere precondition of what justifies, since it is integral to his recognition of the step's validity."
  }
]
**Target Component:**
{ "id": "sec2_para7_comp1", "text": "A natural objection at this point is that what justifies is the mathematical proof itself, and that the very same proof can be both imagined and seen written down." }

**Output:**
{
  "classification": "Rebuttal/Counter-Claim",
  "justification": "This sentence introduces an objection or counter-argument to the line of reasoning developed in the preceding sentences.",
  "relationships": [
    {
      "target_id": "sec2_para6_comp4",
      "type": "Rebuts",
      "direction": "outgoing",
      "justification": "This statement directly opposes the conclusion implied in the previous component about the nature of the justification."
    }
  ]
}

### Example 3
**Context:**
[
  {
    "id": "sec2_para9_comp1",
    "text": "Thus our plodding mathematician's justification for his belief that the theorem holds seems to depend epistemically on sensory experience, so Boghossian's criterion counts it as a posteriori."
  }
]
**Target Component:**
{ "id": "sec2_para9_comp2", "text": "That is not a happy result, for the case is typical of much proof-based justification for mathematical beliefs, the supposed paradigm of nontrivial a priori justification." }

**Output:**
{
  "classification": "Premise/Justification",
  "justification": "This sentence provides a reason why the conclusion in the previous sentence ('not a happy result') is true.",
  "relationships": [
    {
      "target_id": "sec2_para9_comp1",
      "type": "Supports",
      "direction": "outgoing",
      "justification": "This premise explains and provides the reason for the claim made in the first part of the previous sentence ('That is not a happy result')."
    }
  ]
}
