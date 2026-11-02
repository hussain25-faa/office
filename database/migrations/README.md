# Database migrations

Never delete or recreate the live database to apply a schema change.

1. Create a timestamped `.sql` migration in this folder.
2. Back up `business_erp.sqlite3` before applying it.
3. Use additive `ALTER TABLE`, new tables, indexes, or carefully planned data migrations.
4. Test against a copy of the production database first.
5. Record applied migrations in a migration tracking table (add this before introducing automated migration execution).

SQLite has limited `ALTER TABLE` support; use a transaction and a copy-table migration when necessary.
