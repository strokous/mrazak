from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime, timedelta
import smtplib  # Odesílání e-mailů přes Google
from email.mime.text import MIMEText
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.secret_key = "nejake_super_tajne_heslo_pro_sessions"
DATABASE = "database.db"

# ====================================================================
# NASTAVENÍ GMAIL SERVERU
# ====================================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
EMAIL_ODESILATELE = "domacimrazak@gmail.com"
# !!! SEM VLOŽ TO 16MÍSTNÉ HESLO, KTERÉ TI VYGENEROVAL GOOGLE (VČETNĚ MEZER) !!!
HESLO_ODESILATELE = "fjjy qubb yvlq hmxb" 

# Nastavení Flask-Login a automatického pamatování přihlášení na 30 dní
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

class User(UserMixin):
    def __init__(self, id, username, pozadi):
        self.id = id
        self.username = username
        self.pozadi = pozadi

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, pozadi FROM uzivatele WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    if user_data:
        return User(user_data[0], user_data[1], user_data[2])
    return None

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Tabulka potravin s vazbou na uživatele
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS potraviny (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazev TEXT NOT NULL,
            mnozstvi INTEGER NOT NULL,
            datum_nakupu TEXT,
            v_mrazaku INTEGER NOT NULL,
            uzivatel_id INTEGER
        )
    """)
    
    # Tabulka uživatelů - sloupec password už neukládá hash, ale čistý text
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uzivatele (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            pozadi TEXT
        )
    """)
    conn.commit()
    conn.close()

# Funkce, která do e-mailu zabalí PŮVODNÍ jméno i heslo
def odeslat_pripomenuti_email(komu, uzivatelske_jmeno, heslo):
    text_zpravy = f"Ahoj,\n\nposíláme ti tvoje přihlašovací údaje do aplikace Mrazák.\n\nUživatelské jméno: {uzivatelske_jmeno}\nHeslo: {heslo}\n\nTvůj Mrazák ❄️"
    
    msg = MIMEText(text_zpravy, _charset="utf-8")
    msg["Subject"] = "Připomenutí přihlašovacích údajů - Mrazák"
    msg["From"] = EMAIL_ODESILATELE
    msg["To"] = komu

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_ODESILATELE, HESLO_ODESILATELE)
            server.sendmail(EMAIL_ODESILATELE, komu, msg.as_string())
        return True
    except Exception as e:
        print("Chyba při odesílání e-mailu skrze Gmail:", e)
        return False

# --- POMOCNÉ FUNKCE PRO DATA ---

def get_vsechny_uzivatele():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM uzivatele ORDER BY username ASC")
    data = cursor.fetchall()
    conn.close()
    return data

def get_potraviny(sort_by="datum", user_filter="vse"):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    query = """
        SELECT p.id, p.nazev, p.mnozstvi, p.datum_nakupu, p.v_mrazaku, u.username 
        FROM potraviny p
        LEFT JOIN uzivatele u ON p.uzivatel_id = u.id
    """
    params = []
    
    if user_filter != "vse":
        query += " WHERE p.uzivatel_id = ?"
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
    conn.close()
    return data

# --- ROUTY PRO AUTENTIZACI ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        remember_me = True if request.form.get("remember") == "on" else False
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        # Porovnáváme čistý text (password = ?) bez jakéhokoliv hashování
        cursor.execute("SELECT id, username, password, pozadi FROM uzivatele WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data and user_data[2] == password:
            user = User(user_data[0], user_data[1], user_data[3])
            login_user(user, remember=remember_me)
            return redirect(url_for("home"))
        else:
            flash("Nesprávné jméno nebo heslo!")
            
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]  # Heslo bereme tak, jak je
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            # Ukládáme přímo čisté heslo do databáze
            cursor.execute("INSERT INTO uzivatele (username, email, password) VALUES (?, ?, ?)", (username, email, password))
            conn.commit()
            flash("Registrace úspěšná! Nyní se můžeš přihlásit.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Uživatelské jméno nebo e-mail už jsou obsazené!")
        finally:
            conn.close()
            
    return render_template("register.html")

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        # Vytáhneme z databáze uložené jméno a původní čisté heslo
        cursor.execute("SELECT username, password FROM uzivatele WHERE email = ?", (email,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            username, původní_heslo = user_data
            
            # Odešleme e-mail s původními údaji (žádné generování nového hesla)
            if odeslat_pripomenuti_email(email, username, původní_heslo):
                flash("Tvoje přihlašovací údaje byly odeslány na e-mail!")
            else:
                flash("Chyba při odesílání e-mailu. Zkontroluj detaily v konzoli.")
                
            return redirect(url_for("login"))
        else:
            flash("Tento e-mail u nás není registrován!")
            
    return render_template("forgot_password.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# --- ROUTY MRAZÁKU ---

@app.route("/update_bg", methods=["POST"])
@login_required
def update_bg():
    data_url = request.form.get("image_data")
    if data_url:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("UPDATE uzivatele SET pozadi = ? WHERE id = ?", (data_url, current_user.id))
        conn.commit()
        conn.close()
    return redirect(url_for("home", sort=request.args.get("sort", "datum"), user=request.args.get("user", "vse")))

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
        upravene.append((item[0], item[1], item[2], datum, item[4], vlozil_jmeno))
        
    return render_template("index.html", potraviny=upravene, sort_by=sort_by, user_filter=user_filter, uzivatele=vsechni_uzivatele)

@app.route("/add", methods=["POST"])
@login_required
def add():
    nazev = request.form["nazev"].strip()
    mnozstvi = int(request.form["mnozstvi"])
    datum = request.form.get("datum")
    if datum == "": datum = None
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, mnozstvi FROM potraviny WHERE LOWER(nazev) = LOWER(?)", (nazev,))
    existujici = cursor.fetchone()
    
    if existujici:
        cursor.execute("UPDATE potraviny SET mnozstvi = ? WHERE id = ?", (existujici[1] + mnozstvi, existujici[0]))
    else:
        cursor.execute("INSERT INTO potraviny (nazev, mnozstvi, datum_nakupu, v_mrazaku, uzivatel_id) VALUES (?, ?, ?, ?, ?)", 
                       (nazev, mnozstvi, datum, 1, current_user.id))
        
    conn.commit()
    conn.close()
    return redirect(url_for("home", sort=request.args.get("sort", "datum"), user=request.args.get("user", "vse")))

@app.route("/remove_one/<int:item_id>")
@login_required
def remove_one(item_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT mnozstvi FROM potraviny WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if item:
        if item[0] > 1: cursor.execute("UPDATE potraviny SET mnozstvi = mnozstvi - 1 WHERE id = ?", (item_id,))
        else: cursor.execute("DELETE FROM potraviny WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("home", sort=request.args.get("sort", "datum"), user=request.args.get("user", "vse")))

@app.route("/delete/<int:item_id>")
@login_required
def delete(item_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM potraviny WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("home", sort=request.args.get("sort", "datum"), user=request.args.get("user", "vse")))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)