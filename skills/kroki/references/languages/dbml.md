# DBML Reference

DBML (Database Markup Language) is a clean, terse DSL for relational schemas. It generates ER-style diagrams optimized for database design.

**Engine:** Companion container (`kroki-dbml`)
**File extensions:** `.dbml`
**Kroki type string:** `dbml`

## Basic schema

```dbml
Table users {
  id integer [primary key]
  email varchar [unique, not null]
  created_at timestamp
}

Table orders {
  id integer [primary key]
  user_id integer [ref: > users.id]
  total decimal
  placed_at timestamp
}
```

## With table groups and notes

```dbml
Table products {
  id integer [primary key]
  sku varchar [unique]
  name varchar
  Note: 'Product catalog'
}

Table line_items {
  id integer [primary key]
  order_id integer [ref: > orders.id]
  product_id integer [ref: > products.id]
  quantity integer
  unit_price decimal
}

TableGroup commerce {
  products
  line_items
}
```

## Relationship syntax

| Syntax | Cardinality |
|--------|-------------|
| `ref: > users.id` | many-to-one (this row references one user) |
| `ref: < users.id` | one-to-many |
| `ref: - users.id` | one-to-one |
| `ref: <> users.id` | many-to-many |

## Legend Support

**Stitch required.** No native legend syntax — but the cardinality crow's-foot notation is self-describing.

## Common Pitfalls

- The `ref:` direction is from the column to the target. `user_id [ref: > users.id]` means "many line_items per one user."
- Comments use `Note: '...'` not `--` — DBML does not support SQL-style comments inside table blocks.
- Column types are free-form text — DBML doesn't validate against any specific dialect.
- Composite primary keys: `indexes { (col1, col2) [pk] }` block, not `[primary key]` on each column.

## Upstream Docs

- https://dbml.dbdiagram.io/docs/
- https://github.com/holistics/dbml
