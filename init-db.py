import os
import psycopg2

from dotenv import load_dotenv

load_dotenv()

# Connect to the PostgreSQL database
conn = psycopg2.connect(dsn=os.environ["DATABASE_URI"])
cursor = conn.cursor()

# Install extensions
# Follow instructions here: https://github.com/KDJDEV/imagehash-reverse-image-search-tutorial#step-1---setup
cursor.execute("CREATE EXTENSION bktree;")
cursor.execute("CREATE EXTENSION pg_trgm;")
cursor.execute("CREATE EXTENSION unaccent;")

# Define the table creation SQL
cursor.execute("""
    CREATE TABLE media_metadata (
        id SERIAL PRIMARY KEY,
        hash BIGINT,
        text_ocr TEXT,
        text_ocr_vector TSVECTOR,
        text_tsb TEXT,
        text_tsb_vector TSVECTOR,
        content_type TEXT,
        filename TEXT,
        timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        guild_id BIGINT,
        channel_id BIGINT,
        message_id BIGINT,
        author_id BIGINT
    );
""")

# Define the index creation SQL
cursor.execute("CREATE INDEX index_hash ON media_metadata USING spgist(hash bktree_ops);")
cursor.execute("CREATE INDEX index_text_ocr ON media_metadata USING gin(text_ocr gin_trgm_ops);")
cursor.execute("CREATE INDEX index_text_ocr_vector ON media_metadata USING gin(text_ocr_vector);")
cursor.execute("CREATE INDEX index_text_tsb ON media_metadata USING gin(text_tsb gin_trgm_ops);")
cursor.execute("CREATE INDEX index_text_tsb_vector ON media_metadata USING gin(text_tsb_vector);")

# Define the trigger for updating the text_ocr_vector column
cursor.execute("""
    CREATE OR REPLACE FUNCTION update_text_ocr_vector()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.text_ocr_vector := to_tsvector('english', NEW.text_ocr);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
""")
cursor.execute("""
    CREATE TRIGGER trigger_text_ocr_vector
    BEFORE INSERT OR UPDATE
    ON media_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_text_ocr_vector();
""")

# Define the trigger for updating the text_tsb_vector column
cursor.execute("""
    CREATE OR REPLACE FUNCTION update_text_tsb_vector()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.text_tsb_vector := to_tsvector('english', NEW.text_tsb);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
""")
cursor.execute("""
    CREATE TRIGGER trigger_text_tsb_vector
    BEFORE INSERT OR UPDATE
    ON media_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_text_tsb_vector();
""")

# Commit the changes and close the connection
conn.commit()
cursor.close()
conn.close()
