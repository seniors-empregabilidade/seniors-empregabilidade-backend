DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
# PostgreSQL rejects an OFFSET above bigint; a larger value must fail validation
# with a 422 instead of reaching the database and becoming a 500.
MAX_OFFSET = 2**63 - 1
