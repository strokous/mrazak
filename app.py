from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta
import smtplib
import json
import urllib.request
import os
from email.mime.text import MIMEText
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.secret_key = "nejake_super_tajne_heslo_pro_sessions"

# ====================================================================
# TVŮJ ODKAZ Z NEONU (NA KONCI PONECHÁNO JEN ?sslmode=require)
# ====================================================================
DATABASE_URL = "postgresql://neondb_owner:npg_1GjwOQiD9Lxz@ep-holy-sea-a2xwo123.eu-central-1.aws.neon.tech/neondb?sslmode=require"

# GMAIL A NTFY CONFIGURATION
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
EMAIL_ODESILATELE = "domacimrazak@gmail.com"
HESLO_ODESILATELE = "jvps aotz fmob ifqb"
NTFY_CHANNEL = "mrazak_notifikace_rodina_987456"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

class User(UserMixin):
    def __init__(self, id, username, pozadi):
        self.id = id
        self.username = username
        self.pozadi = pozadi

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@login_manager.user_loader
def load_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, pozadi FROM uzivatele WHERE id = %s", (int(user_id),))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_data:
            return User(user_data[0], user_data[1], user_data[2])
    except Exception as e:
        print("Chyba při load_user:", e)
    return None

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Změnili jsme mnozstvi na FLOAT a přidali jednotka TEXT
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS potraviny (
                id SERIAL PRIMARY KEY,
                nazev TEXT NOT NULL,
                mnozstvi FLOAT NOT NULL,
                jednotka TEXT DEFAULT 'ks',
                datum_nakupu TEXT,
                v_mrazaku INTEGER NOT NULL,
                uzivatel_id INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uzivatele (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                pozadi TEXT
            )
        """)
        # AUTOMATICKÁ MIGRACE: Pokud tabulka už existovala ze starší verze, doklepeme tam chybějící sloupec a typ
        cursor.execute("ALTER TABLE potraviny ADD COLUMN IF NOT EXISTS jednotka TEXT DEFAULT 'ks';")
        cursor.execute("ALTER TABLE potraviny ALTER COLUMN mnozstvi TYPE FLOAT;")
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Databáze úspěšně inicializována a zmigrována na Neonu!")
    except Exception as e:
        print("Chyba při inicializaci DB:", e)

def odeslat_push_notifikaci(text_zpravy, titulky="Mrazák ❄️"):
    url = f"https://ntfy.sh/{NTFY_CHANNEL}"
    try:
        req = urllib.request.Request(
            url, 
            data=text_zpravy.encode('utf-8'),
            headers={
                "Title": titulky.encode('utf-8').decode('latin1'),
                "Priority": "default",
                "Tags": "warning,snowflake"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            pass
    except Exception as e:
        print("Chyba push notifikace:", e)

def odeslat_email(komu, predmet, text_zpravy):
    msg = MIMEText(text_zpravy, _charset="utf-8")
    msg["Subject"] = predmet
    msg["From"] = EMAIL_ODESILATELE
    msg["To"] = komu
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_ODESILATELE, HESLO_ODESILATELE)
            server.sendmail(EMAIL_ODESILATELE, komu, msg.as_string())
        return True
    except Exception as e:
        print("Chyba e-mailu:", e)
        return False

def get_vsechny_uzivatele():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM uzivatele ORDER BY username ASC")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data

def get_potraviny(sort_by="datum", user_filter="vse"):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Taháme z DB i jednotku
    query = """
        SELECT p.id, p.nazev, p.mnozstvi, p.datum_nakupu, p.v_mrazaku, u.username, p.jednotka 
        FROM potraviny p
        LEFT JOIN uzivatele u ON p.uzivatel_id = u.id
    """
    params = []
    if user_filter != "vse":
        query += " WHERE p.uzivatel_id = %s"
        params.append(int(user_filter))
    
    if sort_by == "abeceda":
        query += " ORDER BY LOWER(p.nazev) ASC"
    else:
        query += """
            ORDER BY 
                CASE WHEN p.datum_nakupu IS NULL OR p.datum_nakupu = '' THEN 1 ELSE 0 END ASC, 
                p.datum_nakupu ASC
        """
    cursor.execute(query, params)
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data

@app.route("/manifest.json")
def manifest():
    return send_from_directory("templates", "manifest.json")

@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js")

@app.route("/get_ntfy_channel")
@login_required
def get_ntfy_channel():
    return jsonify({"channel": NTFY_CHANNEL})

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        remember_me = True if request.form.get("remember") == "on" else False
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password, pozadi FROM uzivatele WHERE username = %s", (username,))
            user_data = cursor.fetchone()
            cursor.close()
            conn.close()
            if user_data and user_data[2] == password:
                user = User(user_data[0], user_data[1], user_data[3])
                login_user(user, remember=remember_me)
                return redirect(url_for("home"))
            else:
                flash("Nesprávné jméno nebo heslo!")
        except Exception as e:
            flash("Chyba spojení s databází!")
            print(e)
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO uzivatele (username, email, password) VALUES (%s, %s, %s)", (username, email, password))
            conn.commit()
            cursor.close()
            conn.close()
            flash("Registrace úspěšná!")
            return redirect(url_for("login"))
        except psycopg2.IntegrityError:
            flash("Jméno nebo e-mail už existují!")
        except Exception as e:
            flash("Chyba při zápisu do databáze!")
            print(e)
    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/update_bg", methods=["POST"])
@login_required
def update_bg():
    data_url = request.form.get("image_data")
    if data_url:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE uzivatele SET pozadi = %s WHERE id = %s", (data_url, current_user.id))
        conn.commit()
        cursor.close()
        conn.close()
    odkud = request.args.get("from", "home")
    return redirect(url_for(odkud, sort=request.args.get("sort", "datum"), user=request.args.get("user", "vse")))

@app.route("/")
@login_required
def home():
    sort_by = request.args.get("sort", "datum")
    user_filter = request.args.get("user", "vse")
    potraviny = get_potraviny(sort_by, user_filter)
    vsechni_uzivatele = get_vsechny_uzivatele()
    upravene = []
    for item in potraviny:
        datum = item[3]
        if datum:
            try: datum = datetime.strptime(datum, "%Y-%m-%d").strftime("%d.%m.%Y")
            except: pass
        vlozil_jmeno = item[5] if item[5] else "Neznámý"
        
        # Pěkné formátování čísla (pokud je to celé číslo jako 5.0, ukážeme jen 5, pokud 1.5, necháme 1.5)
        mnozstvi = item[2]
        if mnozstvi is not None and mnozstvi % 1 == 0:
            mnozstvi = int(mnozstvi)
            
        jednotka = item[6] if item[6] else "ks"
        upravene.append((item[0], item[1], mnozstvi, datum, item[4], vlozil_jmeno, jednotka))
    return render_template("index.html", potraviny=upravene, sort_by=sort_by, user_filter=user_filter, uzivatele=vsechni_uzivatele)

@app.route("/search")
@login_required
def search():
    potraviny = get_potraviny("abeceda", "vse")
    upravene = []
    for item in potraviny:
        datum = item[3]
        if datum:
            try: datum = datetime.strptime(datum, "%Y-%m-%d").strftime("%d.%m.%Y")
            except: pass
        vlozil_jmeno = item[5] if item[5] else "Neznámý"
        
        mnozstvi = item[2]
        if mnozstvi is not None and mnozstvi % 1 == 0:
            mnozstvi = int(mnozstvi)
            
        jednotka = item[6] if item[6] else "ks"
        upravene.append((item[0], item[1], mnozstvi, datum, item[4], vlozil_jmeno, jednotka))
    return render_template("search.html", potraviny=upravene)

@app.route("/add", methods=["POST"])
@login_required
def add():
    nazev = request.form["nazev"].strip()
    mnozstvi = float(request.form["mnozstvi"])
    jednotka = request.form.get("jednotka", "ks")
    datum = request.form.get("datum")
    if datum == "": datum = None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # Sčítáme jídlo jen tehdy, pokud sedí název I JEDNOTKA (nesčítáme 1kg kuřete a 1ks kuřete)
    cursor.execute("SELECT id, mnozstvi FROM potraviny WHERE LOWER(nazev) = LOWER(%s) AND jednotka = %s", (nazev, jednotka))
    existujici = cursor.fetchone()
    
    if existujici:
        cursor.execute("UPDATE potraviny SET mnozstvi = %s WHERE id = %s", (existujici[1] + mnozstvi, existujici[0]))
    else:
        cursor.execute("INSERT INTO potraviny (nazev, mnozstvi, jednotka, datum_nakupu, v_mrazaku, uzivatel_id) VALUES (%s, %s, %s, %s, %s, %s)", 
                       (nazev, mnozstvi, jednotka, datum, 1, current_user.id))
    conn.commit()
    cursor.close()
    conn.close()
    odkud = request.args.get("from", "home")
    return redirect(url_for(odkud, sort=request.args.get("sort", "datum"), user=request.args.get("user", "vse")))

@app.route("/remove_one/<int:item_id>")
@login_required
def remove_one(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mnozstvi, nazev, jednotka FROM potraviny WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    if item:
        aktualni_mnozstvi, nazev_jidla, jednotka = item
        
        # Pravidlo pro ubírání: Pokud zbývá víc než 1, ubereme přesně 1 jednotku. Pokud zbývá 1 nebo méně (např 0.5 kg), smažeme položku.
        if aktualni_mnozstvi > 1:
            cursor.execute("UPDATE potraviny SET mnozstvi = mnozstvi - 1 WHERE id = %s", (item_id,))
            conn.commit()
        else:
            cursor.execute("DELETE FROM potraviny WHERE id = %s", (item_id,))
            conn.commit()
            odeslat_push_notifikaci(f"Uživatel {current_user.username} odebral poslední kus.", f"⚠️ Došlo jídlo: {nazev_jidla}")
    cursor.close()
    conn.close()
    odkud = request.args.get("from", "home")
    return redirect(url_for(odkud, sort=request.args.get("sort", "datum"), user=request.args.get("user", "vse")))

@app.route("/delete/<int:item_id>")
@login_required
def delete(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nazev FROM potraviny WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    if item:
        nazev_jidla = item[0]
        cursor.execute("DELETE FROM potraviny WHERE id = %s", (item_id,))
        conn.commit()
        odeslat_push_notifikaci(f"Uživatel {current_user.username} smazal celou položku.", f"⚠️ Došlo jídlo: {nazev_jidla}")
    cursor.close()
    conn.close()
    odkud = request.args.get("from", "home")
    return redirect(url_for(odkud, sort=request.args.get("sort", "datum"), user=request.args.get("user", "vse")))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)