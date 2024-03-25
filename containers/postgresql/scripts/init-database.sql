CREATE DATABASE literev;
CREATE USER literev WITH PASSWORD 'literevqsx3409po';
ALTER ROLE literev SET client_encoding TO 'utf8';
ALTER ROLE literev SET default_transaction_isolation TO 'read committed';
ALTER ROLE literev SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE literev TO literev;
ALTER SYSTEM SET listen_addresses TO '*';
ALTER USER literev CREATEDB;
