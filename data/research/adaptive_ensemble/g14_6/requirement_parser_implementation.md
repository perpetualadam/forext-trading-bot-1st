# Requirement parser

`parse_requirement_line` rejects direct URLs, VCS references, editable installs, local paths, requirement includes, constraint includes, index overrides, and find-links overrides. Valid extras and environment markers are retained. Marker syntax is checked without `eval` and without a newly installed parser.

`parse_requirements` still requires the nine production lines. Those lines parse as version specifiers, with `uvicorn` carrying the `standard` extra and no marker. No hash or exact pin was invented.
