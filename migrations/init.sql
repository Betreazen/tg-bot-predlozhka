-- Initial database setup script
-- This file is optional and can be used for any database-level initialization

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes will be handled by Alembic migrations
