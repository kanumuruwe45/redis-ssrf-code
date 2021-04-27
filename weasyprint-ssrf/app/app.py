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

DATABASE = "salesapp.db"
SECRET_KEY = token_urlsafe(32)

app = Flask(__name__, static_folder="static")
app.config.from_object(__name__)
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
    session["user_id"] = user.id
    session["email"] = user.email
    session.permanent = True
    flash("You are logged in as {}".format(user.email))


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
        ref_user = User.get_or_none(User.email == request.form.get("email"))
        if ref_user:
            match_pass = bcrypt.checkpw(
                str(request.form.get("password")).encode(),
                str(ref_user.password).encode(),
            )
            if match_pass:
                auth_user(ref_user)
                return redirect(url_for("go_home"))
            else:
                return redirect(url_for("pre_login"))

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
        if request.form.get("email") and request.form.get("password"):
            user = User(
                email=request.form.get("email"),
                password=bcrypt.hashpw(
                    str(request.form.get("password")).encode(), bcrypt.gensalt()
                ),
                remarks=request.form.get("remarks"),
                first_name=request.form.get("first_name"),
                last_name=request.form.get("last_name"),
            )
            user.save()
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
    ref_user = User.get_or_none(User.email == email)
    if ref_user:
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
            ref_user.email,
            ref_user.email,
            ref_user.first_name,
            ref_user.last_name,
            ref_user.remarks,
        )
        try:
            os.makedirs('static')
        except OSError as e:
           pass

        html = HTML(string=html_string)
        name = "{}-{}.pdf".format(
            str(email).replace("@", "-"), int(datetime.now().timestamp())
        )
        html.write_pdf("static/{}".format(name))
        return send_from_directory(directory="static", filename=name)

    return "Unable to find route"


if __name__ == "__main__":
    create_tables()
    app.run(host="0.0.0.0", debug=True)
