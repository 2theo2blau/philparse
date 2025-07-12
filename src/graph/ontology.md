# Classification Taxonomy for Graph Construction

## Sentence classes:

### Argumentative Components

- Claim/Assertion: A statement presented as a fact or truth that the author intends to support. It is the core proposition being argued for at a local level.
- Premise/Justification: A statement offered as a reason, evidence, or justification in support of a Claim or Conclusion.
- Conclusion: A claim that is explicitly presented as the result of a line of reasoning (premises). Often signaled by words like "therefore," "hence," "thus."
- Rebuttal/Counter-Claim: A statement that directly opposes or refutes a previously mentioned claim (often a Position Statement).
- Concession: A statement that acknowledges the validity of a point from an opposing view, often to narrow the scope of the author's own argument.
- Implication/Consequence: A statement describing what logically follows from a preceding claim or event.

### Definitional & Expository Components

- Formal Definition: A sentence that explicitly states the meaning of a term.
- Term Introduction/Stipulation: A statement where the author introduces a new term or stipulates a specific use for an existing one for the purposes of their argument.
- Example: A concrete case used to clarify an abstract concept, definition, or claim.
- Distinction/Disambiguation: A statement that explicitly draws a boundary or highlights the difference between two concepts.

### Attributive Components

- Position Statement: A summary or statement of a belief, theory, or argument held by another person or group.
- Quotation: A direct, verbatim excerpt from another source, used as evidence or for analysis.
- Citation: The reference marker itself (e.g., ${}^1$, [^1], (Quine 1951)).

###  Structural & Meta-Components

- Thesis: A high-level claim that encapsulates the central argument of the entire paper or a major section.
- Roadmap/Structural Statement: A sentence that outlines the structure of the argument or the steps the author will take.
- Problem Statement: A sentence that poses the central question or problem the text aims to address. Can be a direct or rhetorical question.


## Relationship Ontology

| Relationship Type | Description | Valid Source Nodes | Valid Target Nodes | Example |
| Supports | Provides evidence or justification for | `Premise`, `Quotation`, `Example` | `Claim`, `Conclusion`, `Thesis` | A `premise` supports a `claim` |
| Rebuts | Directly contradicts or argues against | `Rebuttal`, `Conclusion` | `Claim`, `Position Statement` | A `rebuttal` rebuts a `position statement` |
| Clarifies | Makes a concept or statement clearer | `Definition`, `Distinction`, `Example` | `Claim`, `Premise`, `Term Introduction`| A `definition` clarifies a `claim` |
| Illustrates | Provides a concrete example of | `Example` | `Definition`, `Claim`, `Distinction` | an `example` illustrates a `definition` |
| Implies | Logically leads to a consequence | `Claim`, `Premise` | `Implication`, `Conclusion` | A `claim` implies a `consequence` |
| Quantifies/Limits | Narrows the scope or concedes a point | `Concession` | `Claim`, `Thesis` | A `concession` quantifies a `Thesis` |
| Addresses | Attempts to answer or solve | `Thesis`, `Claim` | `Problem Statement`, `Inquiry` | A `Thesis Statement` addresses a `Problem Statement` |
| Outlines | Describes the structure of | `Roadmap` | `Thesis`, `Section` | A `roadmap` outlines the paper's argument |
| Attributes | Assigns an idea to a source | `Position Statement`, `Quotation` | External Entity/Bibliography entry | A `position statement` attributes a view to Quine |
| Cites | Provides a reference for | Citation | External Document, **Note** | A citation cites a note |
| Continues | Follows sequentially in a description | any | any | A premise continues another premise |
