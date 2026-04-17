# erd Reference

`erd` (BurntSushi/erd) is a terse text-only entity-relationship DSL. Good for conceptual ER diagrams when you don't need DBML's database-engine flavor.

**Engine:** Companion container (`kroki-erd`)
**File extensions:** `.erd`
**Kroki type string:** `erd`

## Basic ER diagram

```erd
[Person]
*name
height
weight
+birth_place_id

[Birthplace]
*id
city
state
country

Person *--1 Birthplace
```

## Multiple relationships

```erd
[Author]
*id
name

[Book]
*id
title
+author_id

[Reader]
*id
name

[Loan]
*id
+book_id
+reader_id
loan_date

Author 1--* Book
Reader 1--* Loan
Book 1--* Loan
```

## Symbol meanings

| Symbol | Meaning |
|--------|---------|
| `*name` | Primary key |
| `+id`   | Foreign key |
| `name`  | Plain attribute |
| `1--1`  | One-to-one |
| `1--*`  | One-to-many |
| `*--*`  | Many-to-many |
| `?--1`  | Zero-or-one to one |

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- Entity names go in square brackets `[Name]` on their own line.
- Attribute prefixes (`*`, `+`, `?`) must be the first character — no space before.
- Cardinality symbols are exact text — `1--*` works, `1-*` does not.
- Relationships go AFTER all entities — declaring a relationship to an entity that hasn't been defined yet errors out.

## Upstream Docs

- https://github.com/BurntSushi/erd
