-- Disable Row Level Security (RLS) so the Python script can read and write predictions
ALTER TABLE predictions DISABLE ROW LEVEL SECURITY;
