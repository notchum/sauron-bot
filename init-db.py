import os
import psycopg2

from dotenv import load_dotenv

load_dotenv()

# Connect to the PostgreSQL database
conn = psycopg2.connect(dsn=os.environ["DATABASE_URI"])
cursor = conn.cursor()

# Install extensions
# Follow instructions here: https://github.com/KDJDEV/imagehash-reverse-image-search-tutorial#step-1---setup
create_extension_bktree = "CREATE EXTENSION bktree;"
create_extension_trgm = "CREATE EXTENSION pg_trgm;"
create_extension_unaccent = "CREATE EXTENSION unaccent;"
cursor.execute(create_extension_bktree)
cursor.execute(create_extension_trgm)
cursor.execute(create_extension_unaccent)

# Define the table creation SQL
create_table_sql = """
    CREATE TABLE images (
        id SERIAL PRIMARY KEY,
        hash BIGINT,
        text TEXT,
        text_vector TSVECTOR,
        timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        guild_id BIGINT,
        channel_id BIGINT,
        message_id BIGINT,
        author_id BIGINT
    );
"""
cursor.execute(create_table_sql)

# Define the index creation SQL
create_hash_index_sql = "CREATE INDEX index_hast ON images USING spgist(hash bktree_ops);"
create_text_index_sql = "CREATE INDEX index_text ON images USING gin(text gin_trgm_ops);"
cursor.execute(create_hash_index_sql)
cursor.execute(create_text_index_sql)

# Define the trigger creation SQL
create_text_vector_func_sql = """
    CREATE OR REPLACE FUNCTION update_text_vector()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.text_vector := to_tsvector('english', NEW.text);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
"""

create_text_vector_trigger_sql = """
    CREATE TRIGGER images_update_text_vector
    BEFORE INSERT OR UPDATE
    ON images
    FOR EACH ROW
    EXECUTE FUNCTION update_text_vector();
"""

# Commit the changes and close the connection
conn.commit()
cursor.close()
conn.close()
