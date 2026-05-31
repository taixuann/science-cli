# PLAN: Typst Master Styling Integration & AMSN Guideline Compliance

## Classification
docs | refactor | cleanup | feature

## Related Plans
- None — this plan establishes the standard styling configuration for the B3 Internship Thesis project.

## Status
- **Created**: 2026-05-31
- **Status**: draft
- **Branch**: docs/typst-amsm-styles

## Objective
Migrate the exact style regulations from the AMSN Bachelor thesis template (HTML) into the master [main.typ](file:///Users/tai/workspace/projects/active_projects/res_internship/documentation/thesis/main.typ) document, creating a unified layout engine for headings, fonts, colors, lists, tables, figures, and captions, and adding the official Supervisor Certification page, keeping chapter files in `sections/` completely clean of style-specific layout code.

## Context
The user has provided an official HTML version of the Bachelor thesis template (`Bachelor thesis template - AMSN Dept-updated.html`) which contains inline CSS styling representing the department's requirements. Our CSS analysis has revealed the following precise styles:
- **Base Font**: Times New Roman, `13pt`, color `#000000` (black).
- **Line Spacing**: 1.5 spacing (`leading: 1.05em` in Typst), text justified.
- **Heading 1 (Chapters)**: `22pt` bold, color `#17375e` (navy blue), with a `1pt` solid `#4f81bd` (medium-light blue) bottom border. Spacing is `24pt` top, `18pt` bottom.
- **Heading 2 (Subsections)**: `15pt` bold, color `#376092` (medium-deep blue). Spacing is `18pt` top, `12pt` bottom.
- **Heading 3 (Sub-subsections)**: `13pt` bold, color `#000000` (black). Spacing is `12pt` top, `8pt` bottom.
- **Document Margins**: Exactly `2.5cm` for all sides (A4).
- **Supervisor Certification Page**: Required right after the title page, with signature fields for the supervisor and co-supervisor.
- **Table Formatting**: Scientific `booktabs`-style (header top and bottom borders, data bottom border, no vertical lines) with font size `11pt` and bold navy headers.
- **Caption Formatting**: Bold prefixes (e.g. `Figure 1:`, `Table 1:`), font size `13pt`, table captions placed above and figure captions placed below.

## Proposed Changes

### [Thesis Master File]

#### [MODIFY] [main.typ](file:///Users/tai/workspace/projects/active_projects/res_internship/documentation/thesis/main.typ)
We will define the following global settings at the top of the file:
```typst
#set page(
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm),
)
#set text(
  font: "Times New Roman",
  size: 13pt,
  fill: rgb("#000000"),
)
#set par(
  leading: 1.05em, // Equivalent to 1.5 line spacing for 13pt
  justify: true,
  spacing: 1.2em,  // Standard paragraph spacing
)
```

We will implement global `#show` rules for headings to draw bottom borders for chapters and color subheadings appropriately:
```typst
#show heading.where(level: 1): it => block(
  width: 100%,
  stroke: (bottom: 1pt + rgb("#4f81bd")),
  inset: (bottom: 0.5em),
  above: 24pt,
  below: 18pt,
  text(fill: rgb("#17375e"), size: 22pt, weight: "bold", it.body)
)

#show heading.where(level: 2): it => block(
  width: 100%,
  above: 18pt,
  below: 12pt,
  text(fill: rgb("#376092"), size: 15pt, weight: "bold", it.body)
)

#show heading.where(level: 3): it => block(
  width: 100%,
  above: 12pt,
  below: 8pt,
  text(fill: black, size: 13pt, weight: "bold", it.body)
)
```

We will define global styling for tables to ensure all tables look incredibly premium and academic without vertical borders:
```typst
#set table(
  stroke: (x, y) => if y == 0 {
    (top: 1pt + black, bottom: 1pt + black)
  } else if y == 1 {
    (bottom: 0.5pt + black)
  } else {
    none
  },
  fill: (x, y) => if y == 0 { rgb("#f2f5f9") } else { none }
)

#show table.cell: it => {
  set text(size: 11pt) // slightly smaller for readability
  if it.y == 0 {
    set text(weight: "bold", fill: rgb("#17375e"))
    align(center + horizon, it.body)
  } else {
    align(left + horizon, it.body)
  }
}
```

We will configure figure and table captions:
```typst
#show figure.caption: it => [
  #set text(size: 13pt, font: "Times New Roman", fill: black)
  #strong(it.supplement + " " + context it.counter.display(it.numbering))#it.separator #it.body
]
```

We will insert the official supervisor certification page right after the title page:
- Prefaces Roman numeral numbering starts at this page (Page `i`).
- Blanks will be filled out with the actual student name (Tai Xuan) and supervisors (Dr. Nguyen Van Quyen, Dr. Nguyen Thi Ngoc) to create a perfect ready-to-sign page.

## Verification Plan

### Automated Tests
We will compile the document using the local Typst compiler:
```bash
typst compile /Users/tai/workspace/projects/active_projects/res_internship/documentation/thesis/main.typ /Users/tai/workspace/projects/active_projects/res_internship/documentation/thesis/main.pdf
```
We will verify that the compilation finishes with zero warnings and zero errors, and output is generated.

### Manual Verification
Review the visual page numbering sequence, margins, and section headings in the compiled PDF.

## Progress
- [x] PLAN created
- [ ] User approved
- [ ] IMPLEMENT done
- [ ] TEST passed
- [ ] DOCS updated
- [ ] COMMIT done
