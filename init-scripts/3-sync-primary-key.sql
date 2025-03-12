-- Ensure that the primary key (id) sequence is in sync with the maximum id in the table.
-- This is ran after '2-import-table.sql' since a mass import process causes an out-of-sync key by design.
DO $
DECLARE
    max_id INT;
    next_val INT;
BEGIN
    -- Get the maximum id from the table
    SELECT MAX(id) INTO max_id FROM media_fingerprints;

    -- Get the next value from the sequence
    SELECT nextval(pg_get_serial_sequence('media_fingerprints', 'id')) INTO next_val;

    -- Check if the maximum id is greater than the next value from the sequence
    IF max_id > next_val THEN
        -- Set the sequence value to the next value after the maximum id
        PERFORM setval(pg_get_serial_sequence('media_fingerprints', 'id'), max_id + 1);
    END IF;
END $;
