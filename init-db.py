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
        id SERIAL PRIMARY KEY,                  -- Unique identifier for each record
        hash BIGINT,                            -- Hash value used for image similarity comparison
        text_ocr TEXT,                          -- Extracted text from OCR (Optical Character Recognition)
        text_ocr_vector TSVECTOR,               -- Text_ocr column converted to tsvector for full-text search
        video_transcription TEXT,               -- Transcription of the video
        video_transcription_vector TSVECTOR,    -- Video_transcription column converted to tsvector for full-text search
        content_type TEXT,                      -- Type of media content (e.g., image, video)
        filename TEXT,                          -- Name of the file
        attachment_index INTEGER,               -- Index of the attachment in the message
        url TEXT,                               -- URL of the media
        timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- Timestamp of when the record was created
        guild_id BIGINT,                        -- Identifier for the guild (server) where the media was found
        channel_id BIGINT,                      -- Identifier for the channel where the media was found
        message_id BIGINT,                      -- Identifier for the message where the media was found
        author_id BIGINT,                       -- Identifier for the author of the message where the media was found
        by_bot BOOLEAN,                         -- Whether the media was posted by a bot (TRUE) or not (FALSE)
        bot_id BIGINT                           -- Identifier for the bot responsible for posting the media, if applicable
    );
""")

# Define the index creation SQL
cursor.execute("CREATE INDEX index_hash ON media_metadata USING spgist(hash bktree_ops);")
cursor.execute("CREATE INDEX index_text_ocr ON media_metadata USING gin(text_ocr gin_trgm_ops);")
cursor.execute("CREATE INDEX index_text_ocr_vector ON media_metadata USING gin(text_ocr_vector);")
cursor.execute("CREATE INDEX index_video_transcription ON media_metadata USING gin(video_transcription gin_trgm_ops);")
cursor.execute("CREATE INDEX index_video_transcription_vector ON media_metadata USING gin(video_transcription_vector);")

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

# Define the trigger for updating the video_transcription_vector column
cursor.execute("""
    CREATE OR REPLACE FUNCTION update_video_transcription_vector()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.video_transcription_vector := to_tsvector('english', NEW.video_transcription);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
""")
cursor.execute("""
    CREATE TRIGGER trigger_video_transcription_vector
    BEFORE INSERT OR UPDATE
    ON media_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_video_transcription_vector();
""")

# Commit the changes and close the connection
conn.commit()
cursor.close()
conn.close()
