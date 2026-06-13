import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
INSERT INTO potraviny (nazev, v_mrazaku)
VALUES ('Kuře', 1)
""")

cursor.execute("""
INSERT INTO potraviny (nazev, v_mrazaku)
VALUES ('Hranolky', 0)
""")

cursor.execute("""
INSERT INTO potraviny (nazev, v_mrazaku)
VALUES ('Mléko', 0)
""")

conn.commit()
conn.close()

print("Data přidána.")