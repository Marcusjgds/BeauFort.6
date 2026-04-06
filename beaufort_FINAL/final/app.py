from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
import os, sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bf_secret_2025")

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "models")
LOGO_DIR   = os.path.join(BASE_DIR, "uploads", "logos")
DB_PATH    = os.path.join(BASE_DIR, "database.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(LOGO_DIR, exist_ok=True)

ALLOWED_MODELS = {"rbxm"}
ALLOWED_IMAGES = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "BF.2026")

# ── DB ───────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, description TEXT DEFAULT '',
            price_type TEXT DEFAULT 'free', price INTEGER DEFAULT 0,
            category TEXT DEFAULT 'Other', file TEXT NOT NULL,
            thumbnail TEXT DEFAULT '', author TEXT NOT NULL,
            downloads INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        db.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        db.execute("""CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            icon TEXT DEFAULT '📄',
            content TEXT DEFAULT '',
            visible INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0)""")
        db.execute("""CREATE TABLE IF NOT EXISTS site_settings (
            key TEXT PRIMARY KEY, value TEXT)""")
        defaults = [
            ("maintenance","0"), ("site_closed","0"),
            ("maintenance_msg","Site en maintenance, revenez bientot !"),
            ("site_closed_msg","Le site est temporairement ferme."),
            ("site_logo",""), ("site_theme","dark"),
            ("site_name","Boutique de BeauFort"),
            ("hero_title","Des modeles sans compromis"),
            ("hero_subtitle","Decouvre et partage les meilleurs modeles .rbxmx pour tes projets."),
            ("discord_url",""),
        ]
        for k, v in defaults:
            db.execute("INSERT OR IGNORE INTO site_settings (key,value) VALUES (?,?)", (k,v))
        pages_defaults = [
            ("histoire","Notre Histoire","📖","<h2>L'histoire de BeauFort</h2><p>Bienvenue dans l'univers BeauFort...</p>",1,1),
            ("discord","Discord","💬","<h2>Rejoins notre Discord</h2><p>Clique sur le bouton ci-dessous !</p>",1,2),
            ("recrutement","Recrutement","🎯","<h2>Recrutement ouvert</h2><p>Nous recrutons des builders et scripters !</p>",1,3),
            ("apropos","A propos","ℹ️","<h2>A propos de BeauFort</h2><p>Boutique de BeauFort est une marketplace Roblox.</p>",1,4),
        ]
        for slug,title,icon,content,visible,order in pages_defaults:
            db.execute("INSERT OR IGNORE INTO pages (slug,title,icon,content,visible,sort_order) VALUES (?,?,?,?,?,?)",
                (slug,title,icon,content,visible,order))
        db.commit()

init_db()

def get_setting(key, default=""):
    with get_db() as db:
        row = db.execute("SELECT value FROM site_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

def set_setting(key, value):
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO site_settings (key,value) VALUES (?,?)", (key, value))
        db.commit()

def get_all_settings():
    with get_db() as db:
        return {r["key"]: r["value"] for r in db.execute("SELECT key,value FROM site_settings").fetchall()}

def get_nav_pages():
    with get_db() as db:
        return [dict(p) for p in db.execute("SELECT * FROM pages WHERE visible=1 ORDER BY sort_order").fetchall()]

def allowed_model(fn): return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED_MODELS
def allowed_image(fn): return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED_IMAGES

def make_ctx():
    s = get_all_settings()
    return {
        "site_logo": s.get("site_logo",""),
        "site_name": s.get("site_name","Boutique de BeauFort"),
        "site_theme": s.get("site_theme","dark"),
        "nav_pages": get_nav_pages(),
        "logged_in": "user_id" in session,
        "username": session.get("username",""),
        "is_admin": session.get("is_admin", False),
        "can_upload": session.get("can_upload", False),
    }

@app.before_request
def check_status():
    exempt = ["/admin","/static","/uploads","/login","/logout","/api"]
    if any(request.path.startswith(e) for e in exempt): return None
    if get_setting("site_closed") == "1" and not session.get("is_admin"):
        return render_template("closed.html", msg=get_setting("site_closed_msg"), **make_ctx()), 503
    if get_setting("maintenance") == "1" and not session.get("is_admin"):
        return render_template("maintenance.html", msg=get_setting("maintenance_msg"), **make_ctx()), 503

# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    s = get_all_settings()
    with get_db() as db:
        models = [dict(m) for m in db.execute("SELECT * FROM models ORDER BY created_at DESC").fetchall()]
    ctx = make_ctx()
    ctx["models"] = models
    ctx["hero_title"] = s.get("hero_title","")
    ctx["hero_subtitle"] = s.get("hero_subtitle","")
    return render_template("index.html", **ctx)

@app.route("/page/<slug>")
def page(slug):
    with get_db() as db:
        p = db.execute("SELECT * FROM pages WHERE slug=? AND visible=1", (slug,)).fetchone()
    if not p: return redirect(url_for("index"))
    ctx = make_ctx()
    ctx["page"] = dict(p)
    ctx["discord_url"] = get_setting("discord_url","")
    return render_template("page.html", **ctx)

@app.route("/model/<int:mid>")
def model_detail(mid):
    with get_db() as db:
        m = db.execute("SELECT * FROM models WHERE id=?", (mid,)).fetchone()
    if not m: return redirect(url_for("index"))
    ctx = make_ctx()
    ctx["model"] = dict(m)
    return render_template("model_detail.html", **ctx)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None, **make_ctx())
    username = request.form.get("username","").strip()
    password = request.form.get("password","").strip()
    if not username or not password:
        return render_template("login.html", error="Pseudo et mot de passe requis.", **make_ctx())
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?) AND password=?", (username,password)).fetchone()
    if not user:
        return render_template("login.html", error="Pseudo ou mot de passe incorrect.", **make_ctx())
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["is_admin"] = False
    session["can_upload"] = True
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ── ADMIN ─────────────────────────────────────────────────────────────────────
@app.route("/admin", methods=["GET","POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            session["can_upload"] = True
            session["username"] = "Admin"
            session["user_id"] = 0
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_login.html", error="Mot de passe incorrect.", **make_ctx())
    if session.get("is_admin"): return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html", error=None, **make_ctx())

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("is_admin"): return redirect(url_for("admin"))
    s = get_all_settings()
    with get_db() as db:
        users  = [dict(u) for u in db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()]
        models = [dict(m) for m in db.execute("SELECT * FROM models ORDER BY created_at DESC").fetchall()]
        all_pages = [dict(p) for p in db.execute("SELECT * FROM pages ORDER BY sort_order").fetchall()]
    ctx = make_ctx()
    ctx["db_users"] = users
    ctx["db_models"] = models
    ctx["db_pages"] = all_pages
    ctx["settings"] = s
    return render_template("admin_dashboard.html", **ctx)

@app.route("/admin/add_user", methods=["POST"])
def admin_add_user():
    if not session.get("is_admin"): return jsonify({"success":False})
    username = request.form.get("username","").strip()
    password = request.form.get("password","").strip()
    if not username or not password:
        return jsonify({"success":False,"error":"Pseudo et mot de passe requis"})
    try:
        with get_db() as db:
            db.execute("INSERT INTO users (username,password) VALUES (?,?)", (username,password))
            db.commit()
        return jsonify({"success":True,"username":username})
    except:
        return jsonify({"success":False,"error":"Utilisateur deja existant"})

@app.route("/admin/remove_user/<int:uid>", methods=["POST"])
def admin_remove_user(uid):
    if not session.get("is_admin"): return jsonify({"success":False})
    with get_db() as db:
        db.execute("DELETE FROM users WHERE id=?", (uid,))
        db.commit()
    return jsonify({"success":True})

@app.route("/admin/delete_model/<int:mid>", methods=["POST"])
def admin_delete_model(mid):
    if not session.get("is_admin"): return jsonify({"success":False})
    with get_db() as db:
        m = db.execute("SELECT * FROM models WHERE id=?", (mid,)).fetchone()
        if m:
            try: os.remove(os.path.join(UPLOAD_DIR, m["file"]))
            except: pass
            if m["thumbnail"]:
                try: os.remove(os.path.join(UPLOAD_DIR, m["thumbnail"]))
                except: pass
        db.execute("DELETE FROM models WHERE id=?", (mid,))
        db.commit()
    return jsonify({"success":True})

@app.route("/admin/save_settings", methods=["POST"])
def admin_save_settings():
    if not session.get("is_admin"): return jsonify({"success":False})
    data = request.get_json() or {}
    for key, value in data.items():
        set_setting(key, str(value))
    return jsonify({"success":True})

@app.route("/admin/save_page", methods=["POST"])
def admin_save_page():
    if not session.get("is_admin"): return jsonify({"success":False})
    data = request.get_json() or {}
    pid = data.get("id")
    with get_db() as db:
        if pid:
            db.execute("UPDATE pages SET title=?,icon=?,content=?,visible=? WHERE id=?",
                (data.get("title",""),data.get("icon","📄"),data.get("content",""),int(data.get("visible",1)),pid))
        else:
            import re
            slug = re.sub(r'[^a-z0-9-]','',data.get("title","page").lower().replace(" ","-"))
            db.execute("INSERT INTO pages (slug,title,icon,content,visible,sort_order) VALUES (?,?,?,?,?,?)",
                (slug,data.get("title",""),data.get("icon","📄"),data.get("content",""),1,99))
        db.commit()
    return jsonify({"success":True})

@app.route("/admin/delete_page/<int:pid>", methods=["POST"])
def admin_delete_page(pid):
    if not session.get("is_admin"): return jsonify({"success":False})
    with get_db() as db:
        db.execute("DELETE FROM pages WHERE id=?", (pid,))
        db.commit()
    return jsonify({"success":True})

@app.route("/upload_model", methods=["POST"])
def upload_model():
    if not session.get("can_upload") and not session.get("is_admin"):
        return jsonify({"success":False,"error":"Non autorise"})
    name = request.form.get("model_name","").strip()
    desc = request.form.get("description","").strip()
    price_type = request.form.get("price_type","free")
    price = request.form.get("price","0")
    category = request.form.get("category","Other").strip()
    if not name: return jsonify({"success":False,"error":"Nom requis"})
    mf = request.files.get("model_file")
    if not mf or not allowed_model(mf.filename):
        return jsonify({"success":False,"error":"Fichier .rbxm/.rbxmx requis"})
    mfn = secure_filename(f"{session.get('user_id','0')}_{mf.filename}")
    mf.save(os.path.join(UPLOAD_DIR, mfn))
    tp = ""
    tf = request.files.get("thumbnail")
    if tf and tf.filename and allowed_image(tf.filename):
        tfn = secure_filename(f"thumb_{session.get('user_id','0')}_{tf.filename}")
        tf.save(os.path.join(UPLOAD_DIR, tfn))
        tp = tfn
    rp = 0
    if price_type == "paid":
        try: rp = int(price)
        except: pass
    with get_db() as db:
        cur = db.execute("INSERT INTO models (name,description,price_type,price,category,file,thumbnail,author) VALUES (?,?,?,?,?,?,?,?)",
            (name,desc,price_type,rp,category,mfn,tp,session.get("username","Admin")))
        db.commit()
        model = dict(db.execute("SELECT * FROM models WHERE id=?", (cur.lastrowid,)).fetchone())
    return jsonify({"success":True,"model":model})

@app.route("/upload_logo", methods=["POST"])
def upload_logo():
    if not session.get("is_admin"): return jsonify({"success":False})
    logo = request.files.get("logo")
    if not logo or not allowed_image(logo.filename): return jsonify({"success":False})
    fn = secure_filename(f"logo_{logo.filename}")
    logo.save(os.path.join(LOGO_DIR, fn))
    set_setting("site_logo", fn)
    return jsonify({"success":True,"logo_path":fn})

@app.route("/uploads/models/<path:filename>")
def serve_model(filename): return send_from_directory(UPLOAD_DIR, filename)

@app.route("/uploads/logos/<path:filename>")
def serve_logo(filename): return send_from_directory(LOGO_DIR, filename)

@app.route("/download/<int:model_id>")
def download_model(model_id):
    with get_db() as db:
        m = db.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
        if not m: return "Introuvable", 404
        db.execute("UPDATE models SET downloads=downloads+1 WHERE id=?", (model_id,))
        db.commit()
    return send_from_directory(UPLOAD_DIR, m["file"], as_attachment=True)

@app.route("/privacy")
def privacy(): return render_template("privacy.html", **make_ctx())

@app.route("/terms")
def terms(): return render_template("terms.html", **make_ctx())

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
