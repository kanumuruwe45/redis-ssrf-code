from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    session,
    flash,
    redirect,
    url_for,
    g,
    send_from_directory,
)
from peewee import SqliteDatabase, CharField, Model, ForeignKeyField
from datetime import datetime
from secrets import token_urlsafe
from functools import wraps
import bcrypt
from weasyprint import HTML
import os
from tornado.wsgi import WSGIContainer
from tornado.ioloop import IOLoop
from tornado.web import FallbackHandler, RequestHandler, Application
from tornado.websocket import WebSocketHandler


import redis 
redisClient = redis.StrictRedis(host="127.0.0.1",port=6379,db=0,decode_responses=True)

DATABASE = "salesapp.db"
SECRET_KEY = token_urlsafe(32)

app = Flask(__name__, static_folder="static")
app.config.from_object(__name__)
#commenetd


# Hello Rajehs
# app.config.update(
#     SESSION_COOKIE_SECURE = False,
#     REMEMBER_COOKIE_SECURE = False
# )

database = SqliteDatabase(DATABASE)


class BaseModel(Model):
    class Meta:
        database = database


class User(BaseModel):
    email = CharField(unique=True)
    first_name = CharField()
    last_name = CharField()
    password = CharField()
    remarks = CharField()


class Customer(BaseModel):
    salesperson = ForeignKeyField(User, backref="customers")
    name = CharField()
    url = CharField()


def create_tables():
    with database:
        database.create_tables([User, Customer])


def auth_user(user):
   
    session["logged_in"] = True
    session["user_id"] = user['fname']
    session["email"] = user['email']
    session.permanent = True
    flash("You are logged in as {}".format(user['email']))


def login_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if session.get("logged_in"):
            return f(*args, **kwargs)

        return redirect(url_for("pre_login"))

    return inner


@app.before_request
def before_request():
    g.db = database
    g.db.connect()


@app.after_request
def after_request(response):
    g.db.close()
    return response


@app.route("/", methods=["GET", "POST"])
def pre_login():
    if request.method == "GET":
        return render_template("index.html")
    elif request.method == "POST":
        query='ec2instance*'
        keys = redisClient.keys(query)
       
        temp=[]
    
        for j in keys:
            temp = redisClient.hgetall(j)
            if request.form.get("email")==temp['email'] and bcrypt.checkpw(str(request.form.get("password")).encode(), temp["pwd"].encode() ):
                auth_user(temp)
                
                
                return redirect(url_for("go_home"))
           
        return redirect(url_for("pre_login"))


@app.route("/home", methods=["GET"])
@login_required
def go_home():
    return render_template("home.html")


@app.route("/customer", methods=["GET", "POST"])
@login_required
def create_customer():
    if request.method == "GET":
        salesperson = User.get(User.email == session.get("email"))
        try:
            customers = list(
                Customer.select().where(Customer.salesperson == salesperson).dicts()
            )
            return render_template("customer.html", all_customers=customers)
        except Exception:
            return render_template("customer.html", all_customers=None)

    if request.method == "POST":
        user = User.get(User.email == session.get("email"))
        customer_name = request.form.get("name")
        customer_url = request.form.get("url")

        try:
            new_cust = Customer(name=customer_name, url=customer_url, salesperson=user)
            new_cust.save()
            return redirect(url_for("create_customer"))
        except Exception:
            return jsonify({"error": True})


@app.route("/update", methods=["GET", "POST"])
@login_required
def update_user():
    if request.method == "GET":
        email = session.get("email")
        ref_user = User.get_or_none(User.email == email)
        return render_template("update.html", remarks=ref_user.remarks)

    if request.method == "POST":
        email = session.get("email")
        if request.form.get("remarks"):
            try:
                query = User.update(remarks=request.form.get("remarks")).where(
                    User.email == email
                )
                query.execute()
                return render_template("home.html")
            except Exception:
                return "Unable to update user"
        else:
            return render_template("home.html")


@app.route("/signup", methods=["POST", "GET"])
def signup():
    
    if request.method == "POST":
        userdetails={}
       
        if request.form.get("email") and request.form.get("password"):
            print(request.form.get("password"))
            query='ec2instance*'
            keys = redisClient.keys(query)
            
            
            for j in keys:
                temp = redisClient.hgetall(j)
                if request.form.get("email")==temp['email']:
                    return render_template("signup.html")
            userdetails['fname']=str(request.form.get("first_name"))
            userdetails['sname']=str(request.form.get("last_name"))
            userdetails['pwd']=bcrypt.hashpw(str(request.form.get("password")).encode(), bcrypt.gensalt())
            userdetails['email']=str(request.form.get("email"))
            userdetails['remarks']=str(request.form.get("remarks"))
            query='ec2instance*'
            keys = len(redisClient.keys(query))
            
            if keys<=0:
                keys=1
            else:
                keys=keys+1
            count="ec2instance"+str(keys+1)
          
            
            redisClient.hmset(count, userdetails)
            userdetails={}
           
           
            return redirect(url_for("pre_login"))
        else:
            return redirect(url_for("pre_login"))
    elif request.method == "GET":
        return render_template("signup.html")
    else:
        return "Can't recognize HTTP Verb"


@app.route("/genpdf", methods=["GET"])
@login_required
def gen_pdf():
    email = session.get("email")
    query='ec2instance*'
    keys = redisClient.keys(query)
  
    temp=[]
    user={}
    for j in keys:
        temp = redisClient.hgetall(j)
        if email==temp['email']:

            user=temp
            print("Generate pdf")

            html_string = """
        <html>
            <head>
                <title>%s's Profile</title>
            </head>
            <body>
                <h3>%s</h1>
                <p>%s %s</p>
                %s

            </body>
        </html>
        """ % (
            user['email'],
            user['email'],
            user['fname'],
            user['sname'],
            user['remarks']
        )
            try:
                os.makedirs('static')
            except OSError as e:
                pass
            
            html = HTML(string=html_string)
            name = "{}-{}.pdf".format(
            str(user['email']), int(datetime.now().timestamp())
            )
            html.write_pdf("static/{}".format(name))
            return send_from_directory(directory="static", filename=name)

           
    return "Unable to find route"


if __name__ == "__main__":
    create_tables()
   
    wsgi_app = WSGIContainer(app)

    application = Application([
        (r'.*', FallbackHandler, dict(fallback=wsgi_app))
    ])
    application.listen(4000)
    IOLoop.instance().start()
    # app.run(host="0.0.0.0", debug=True)
