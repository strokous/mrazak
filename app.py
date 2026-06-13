from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
DATABASE = "database.db"


def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS potraviny (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazev TEXT NOT NULL,
            mnozstvi INTEGER NOT NULL,
            datum_nakupu TEXT,
            v_mrazaku INTEGER NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_potraviny():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM potraviny")
    data = cursor.fetchall()

    conn.close()
    return data


@app.route("/")
def home():
    potraviny = get_potraviny()

    upravene = []

    for item in potraviny:
        datum = item[3]

        if datum:
            try:
                datum = datetime.strptime(datum, "%Y-%m-%d").strftime("%d. %m. %Y")
            except:
                pass

        upravene.append((item[0], item[1], item[2], datum, item[4]))

    return render_template("index.html", potraviny=upravene)


@app.route("/add", methods=["POST"])
def add():
    nazev = request.form["nazev"]
    mnozstvi = request.form["mnozstvi"]
    datum = request.form.get("datum")  # může být prázdné

    if datum == "":
        datum = None

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO potraviny (nazev, mnozstvi, datum_nakupu, v_mrazaku)
        VALUES (?, ?, ?, ?)
    """, (nazev, mnozstvi, datum, 1))

    conn.commit()
    conn.close()

    return redirect(url_for("home"))


@app.route("/delete/<int:item_id>")
def delete(item_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM potraviny WHERE id = ?", (item_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("home"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)