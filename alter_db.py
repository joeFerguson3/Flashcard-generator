# Updates data base

import sqlite3

# connect to DB file
conn = sqlite3.connect("instance/flashcards.db")
cursor = conn.cursor()

cursor.execute("""
    ALTER TABLE note_set
    ADD COLUMN subject VARCHAR(255) NOT NULL DEFAULT 'Default';
""")

# save and close
conn.commit()
conn.close()

print("Column 'subject' added successfully!")
