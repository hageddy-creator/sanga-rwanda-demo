import os,sqlite3,secrets
from functools import wraps
from flask import Flask,render_template,request,redirect,url_for,session,flash,jsonify
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.exceptions import BadRequest
BASE=os.path.dirname(__file__)
DB=os.getenv('SANGA_DB',os.path.join(BASE,'sanga.db'))
app=Flask(__name__)
app.secret_key=os.getenv('SECRET_KEY',secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax')
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'merchant');CREATE TABLE IF NOT EXISTS shops(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL,name TEXT NOT NULL,city TEXT NOT NULL,country TEXT NOT NULL DEFAULT 'Rwanda',description TEXT DEFAULT '',premium INTEGER NOT NULL DEFAULT 0,FOREIGN KEY(owner_id) REFERENCES users(id));CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY,shop_id INTEGER NOT NULL,title TEXT NOT NULL,category TEXT NOT NULL,price REAL NOT NULL,currency TEXT NOT NULL DEFAULT 'RWF',description TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(shop_id) REFERENCES shops(id));CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY,shop_id INTEGER NOT NULL,amount REAL NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
  if not c.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
   c.execute('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)',('Demo Merchant','merchant@demo.sanga',generate_password_hash('DemoOnly123!'),'merchant'))
   uid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
   c.execute('INSERT INTO shops(owner_id,name,city,country,description) VALUES(?,?,?,?,?)',(uid,'Duka ry’Urugero','Kigali','Rwanda','Amakuru y’igerageza, si iduka nyaryo'))
   sid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
   for title,cat,price in [('Telefoni y’igerageza','Ikoranabuhanga',145000),('Inkweto z’igerageza','Imyambaro',18000),('Gusana mudasobwa — urugero','Serivisi',25000)]:c.execute('INSERT INTO listings(shop_id,title,category,price,description) VALUES(?,?,?,?,?)',(sid,title,cat,price,'Urugero gusa; ntugure iki gicuruzwa.'))
  admin_email=os.getenv('ADMIN_EMAIL');admin_pass=os.getenv('ADMIN_PASSWORD')
  if admin_email and admin_pass and not c.execute('SELECT id FROM users WHERE email=?',(admin_email.lower(),)).fetchone():
   c.execute('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)',('SANGA Admin',admin_email.lower(),generate_password_hash(admin_pass),'admin'))
init()
def csrf():
 if '_csrf' not in session:session['_csrf']=secrets.token_urlsafe(24)
 return session['_csrf']
app.jinja_env.globals['csrf_token']=csrf
@app.before_request
def protect():
 if request.method=='POST' and request.form.get('_csrf')!=csrf():raise BadRequest('CSRF token invalid')
def login_required(fn):
 @wraps(fn)
 def inner(*a,**kw):
  if not session.get('uid'):return redirect(url_for('login'))
  return fn(*a,**kw)
 return inner
@app.route('/')
def home():
 q=request.args.get('q','').strip()[:100];city=request.args.get('city','').strip()[:60];category=request.args.get('category','').strip()[:60];country=request.args.get('country','').strip()[:60];maxprice=request.args.get('maxprice','').strip()
 sql='SELECT l.*,s.name shop,s.city,s.country,s.premium FROM listings l JOIN shops s ON l.shop_id=s.id WHERE 1=1';args=[]
 if q:sql+=' AND (l.title LIKE ? OR l.description LIKE ? OR s.name LIKE ?)';args.extend(['%'+q+'%']*3)
 if city:sql+=' AND s.city LIKE ?';args.append('%'+city+'%')
 if country:sql+=' AND s.country LIKE ?';args.append('%'+country+'%')
 if category:sql+=' AND l.category=?';args.append(category)
 if maxprice:
  try:sql+=' AND l.price<=?';args.append(float(maxprice))
  except ValueError:pass
 sql+=' ORDER BY s.premium DESC,l.created_at DESC LIMIT 100'
 with db() as c:items=c.execute(sql,args).fetchall();cats=[x[0] for x in c.execute('SELECT DISTINCT category FROM listings ORDER BY category')]
 return render_template('index.html',items=items,cats=cats,q=q,city=city,category=category,country=country,maxprice=maxprice)
@app.route('/register',methods=['GET','POST'])
def register():
 if request.method=='POST':
  name=request.form.get('name','').strip()[:80];email=request.form.get('email','').strip().lower()[:150];password=request.form.get('password','');shop=request.form.get('shop','').strip()[:100];city=request.form.get('city','').strip()[:80];country=request.form.get('country','Rwanda').strip()[:80]
  if not all([name,email,password,shop,city,country]) or len(password)<10:flash('Uzuza ibisabwa byose; ijambo ry’ibanga rigire nibura inyuguti 10.','error')
  else:
   try:
    with db() as c:
     c.execute('INSERT INTO users(name,email,password) VALUES(?,?,?)',(name,email,generate_password_hash(password)))
     uid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
     c.execute('INSERT INTO shops(owner_id,name,city,country) VALUES(?,?,?,?)',(uid,shop,city,country))
    session.clear();session['uid']=uid;return redirect(url_for('dashboard'))
   except sqlite3.IntegrityError:flash('Iyi email isanzwe ikoreshwa.','error')
 return render_template('register.html')
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  with db() as c:u=c.execute('SELECT * FROM users WHERE email=?',(request.form.get('email','').strip().lower(),)).fetchone()
  if u and check_password_hash(u['password'],request.form.get('password','')):
   session.clear();session['uid']=u['id'];return redirect(url_for('dashboard'))
  flash('Email cyangwa ijambo ry’ibanga si byo.','error')
 return render_template('login.html')
@app.route('/logout',methods=['POST'])
def logout():session.clear();return redirect(url_for('home'))
@app.route('/dashboard')
@login_required
def dashboard():
 with db() as c:
  u=c.execute('SELECT * FROM users WHERE id=?',(session['uid'],)).fetchone()
  if u['role']=='admin':
   stats={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('users','shops','listings','payments')}
   revenue=c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid'").fetchone()[0]
   shops=c.execute('SELECT s.*,u.email FROM shops s JOIN users u ON s.owner_id=u.id ORDER BY s.id DESC').fetchall()
   return render_template('admin.html',stats=stats,revenue=revenue,shops=shops)
  shop=c.execute('SELECT * FROM shops WHERE owner_id=?',(session['uid'],)).fetchone()
  items=c.execute('SELECT * FROM listings WHERE shop_id=? ORDER BY id DESC',(shop['id'],)).fetchall()
  return render_template('dashboard.html',shop=shop,items=items)
@app.route('/listing/add',methods=['POST'])
@login_required
def add_listing():
 with db() as c:
  shop=c.execute('SELECT id FROM shops WHERE owner_id=?',(session['uid'],)).fetchone()
  if not shop:return redirect(url_for('dashboard'))
  try:price=float(request.form.get('price',''))
  except ValueError:price=-1
  title=request.form.get('title','').strip()[:120];category=request.form.get('category','').strip()[:60]
  if not title or not category or price<0 or price>1e12:flash('Reba izina, icyiciro n’igiciro.','error')
  else:
   c.execute('INSERT INTO listings(shop_id,title,category,price,currency,description) VALUES(?,?,?,?,?,?)',(shop['id'],title,category,price,request.form.get('currency','RWF')[:8],request.form.get('description','').strip()[:500]));flash('Igicuruzwa/serivisi byongewe.','ok')
 return redirect(url_for('dashboard'))
@app.route('/listing/<int:lid>/delete',methods=['POST'])
@login_required
def delete_listing(lid):
 with db() as c:c.execute('DELETE FROM listings WHERE id=? AND shop_id IN (SELECT id FROM shops WHERE owner_id=?)',(lid,session['uid']))
 return redirect(url_for('dashboard'))
@app.route('/premium',methods=['POST'])
@login_required
def premium():
 with db() as c:
  shop=c.execute('SELECT id FROM shops WHERE owner_id=?',(session['uid'],)).fetchone()
  if shop:c.execute("INSERT INTO payments(shop_id,amount,status) VALUES(?,15000,'pending')",(shop['id'],));flash('Premium request yakiriwe (DEMO). Nta mafaranga yishyuwe.','ok')
 return redirect(url_for('dashboard'))
@app.route('/api/listings')
def listings_api():
 with db() as c:items=c.execute('SELECT l.id,l.title,l.category,l.price,l.currency,s.name shop,s.city,s.country FROM listings l JOIN shops s ON s.id=l.shop_id LIMIT 100').fetchall()
 return jsonify([dict(x) for x in items])
if __name__=='__main__':app.run(debug=False,port=int(os.getenv('PORT',5000)))
