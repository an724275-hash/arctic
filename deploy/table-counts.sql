SELECT format(
    'SELECT %L || chr(9) || count(*)::text FROM %I.%I;',
    schemaname || '.' || tablename, schemaname, tablename
)
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename
\gexec
