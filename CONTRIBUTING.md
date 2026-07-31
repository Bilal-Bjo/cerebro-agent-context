# Contributing

Thank you for helping make agent context safer and easier to inspect.

## Principles

- Keep Cerebro local-first and vendor-neutral.
- Prefer deterministic behavior over opaque convenience.
- Treat source and runtime evidence as more authoritative than memory.
- Keep all examples completely synthetic.
- Never commit credentials, sessions, customer data, or private operational details.
- Add executable proof for behavior changes.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Run the checks:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src \
python3 -m unittest discover -s tests -v

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src \
python3 -m cerebro_context validate \
  --brain examples/northstar-shop/brain
```

## Pull requests

Describe:

- the behavior being changed;
- why the change belongs in the trust model;
- tests that prove it;
- compatibility or security consequences;
- any residual behavior that remains unproved.

Keep changes focused. New retrieval backends must include an evaluation showing improvement over
the deterministic lexical baseline.

## Synthetic fixtures

Use reserved or obviously fictional values:

- `example.com` for URLs;
- Northstar or another clearly fictional organization;
- fake source locators such as `repo://example@abc123`;
- generated data with no relationship to a real person or customer.

Do not “sanitize” a real credential or customer record into a fixture. Create a synthetic one from
scratch.
