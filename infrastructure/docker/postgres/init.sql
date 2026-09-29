-- Runs once when the local Postgres volume is first created.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Test database used by the backend test-suite (recreated by the tests themselves as needed).
CREATE DATABASE careeros_test OWNER careeros;
\connect careeros_test
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
