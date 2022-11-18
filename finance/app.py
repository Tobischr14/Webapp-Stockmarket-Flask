import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
# from flask_mail import Mail, Message

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# # configure email service
# app.config["MAIL_DEFAULT_SENDER"] = os.environ["MAIL_DEFAULT_SENDER"]
# app.config["MAIL_PASSWORD"] = os.environ["MAIL_PASSWORD"]
# app.config["MAIL_PORT"] = 465
# app.config["MAIL_SERVER"] = "mail.gmx.net"
# app.config["MAIL_USE_SSL"] = True
# app.config["MAIL_USERNAME"] = os.environ["MAIL_USERNAME"]
# mail = Mail(app)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # return redirect("/quote")

    # get portfolio infos and the users cash
    userPortfolio = db.execute("select symbol, shares from portfolio where user_id=?", session.get("user_id"))
    userCash = db.execute("select cash from users where id=?", session.get("user_id"))

    # get actual stock prices

    for element in userPortfolio:
        element["price"] = (lookup(element["symbol"]))["price"]
        element["total"] = element["price"]*element["shares"]
        element["price"] = element["price"]

    # user
    userTotal = 0
    for element in userPortfolio:
        userTotal = userTotal + element["total"]
    userTotal = userTotal + userCash[0]["cash"]

    return render_template("index.html", userPortfolio=userPortfolio, userCash=userCash[0]["cash"], userTotal=userTotal)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # check if a symbol is provided
        if request.form.get("symbol") == None:
            return apology("must provide stock symbol", 400)

        # get input from form
        numberOfSharesBought = request.form.get("shares")

        # check if the amount is positive integer
        # if not int(request.form.get("shares")) or int(request.form.get("shares")) < 0 or (not request.form.get("shares")):
        if not numberOfSharesBought.isnumeric():
            return apology("must provide the a positive and whole number of stocks you want to buy!", 400)

        # get actual price of stocks:
        currentStock = lookup(request.form.get("symbol"))
        if currentStock == None:
            return apology("Stock not found. Please try again with other symbol!")

    # check if cash of user is enough
        # get cash balance from user
        cashOfUser = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))

        # get input from form
        numberOfSharesBought = request.form.get("shares")

        # check cost vs cash balance and in case there is enough -> execute buy and save in db transactions
        if (currentStock["price"] * float(numberOfSharesBought)) <= float(cashOfUser[0]["cash"]):
            db.execute("INSERT INTO transactions (type, name, symbol, shares, price, date, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       "buy", currentStock["name"], currentStock["symbol"], int(numberOfSharesBought), currentStock["price"], datetime.now(), session.get("user_id"))

            # calculate totalCost of the buy order
            totalPrice = currentStock["price"] * float(numberOfSharesBought)

            # update cash balance of user
            newBalance = cashOfUser[0]["cash"] - totalPrice
            db.execute("UPDATE users SET cash = ? WHERE id = ?", newBalance, session.get("user_id"))

            # check portfolio for existing stocks of this kind and update it
            sharesBeforeTransaction = db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?",
                                                 session.get("user_id"), currentStock["symbol"])
            if len(sharesBeforeTransaction) > 0:
                sharesAfterTransaction = sharesBeforeTransaction[0]["shares"] + int(numberOfSharesBought)
                # update portfolio with shares
                db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?",
                           sharesAfterTransaction, session.get("user_id"), currentStock["symbol"])
            else:
                sharesAfterTransaction = numberOfSharesBought
                # create portfolio entry with shares
                db.execute("INSERT INTO portfolio (user_id, symbol, shares) VALUES (?, ?, ?)",
                           session.get("user_id"),  currentStock["symbol"], sharesAfterTransaction)
        else:
            return apology("Not enough cash!")

        # show currentStock information in
        return render_template("buyConfirmation.html", numberOfShares=numberOfSharesBought, name=currentStock["name"],
                               symbol=currentStock["symbol"], price=currentStock["price"], newBalance=newBalance, totalPrice=totalPrice)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("/buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # get portfolio infos and the users cash
    userTransactions = db.execute("select * from transactions where user_id=?", session.get("user_id"))

    return render_template("/history.html", userTransactions=userTransactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User comes from login
    if request.method == "POST":

        # with imput from quote form, look up this symbol
        # lookup saves stockinformation in separate table in db
        currentStock = lookup(request.form.get("symbol"))
        if currentStock == None:
            return apology("Stock not found. Please try again with other symbol!")

        # show currentStock information in
        return render_template("quoted.html", name=currentStock["name"], symbol=currentStock["symbol"], price=currentStock["price"])

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # render quote to get input
        return render_template("quote.html")
    # return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure a username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure a password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must provide password (again)", 400)

        # elif not request.form.get("email"):
        #     return apology("must provide email", 403)

        # check if passwords are similar
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords are not similar", 400)

        # Check if Username alsready existing
            # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 0:
            return apology("Username already in use. Please select another username.", 400)

        # Insert new registration in database
        # with created password hash
        db.execute("INSERT INTO users (username,  hash) VALUES(?, ?)", request.form.get("username"),
                   generate_password_hash(request.form.get("password")))

        # # send confirmation email
        # email = request.form.get("email")
        # message = Message("Thanks for your registration!", recipients=[email])
        # mail.send(message)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # # check if a symbol is provided
        # if request.form.get("symbol") == None:
        #     return apology("must provide stock symbol", 403)

        # check if the amount is positive integer
        if (request.form.get("shares") == ""):
            return apology("must provide the positive number of stocks you want to buy!", 403)

        if (int(request.form.get("shares")) < 0):
            return apology("must provide the positive number of stocks you want to buy!", 403)

        # get actual price of stocks:
        currentStock = lookup(request.form.get("symbol"))
        if currentStock == None:
            return apology("Stock not found. Please try again with other symbol!")

        # check if cash of user is enough
        # get cash balance from user
        cashOfUser = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))
        stocksInPortfolio = db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND symbol == ?",
                                       session.get("user_id"), request.form.get("symbol"))

        # get input from form
        numberOfSharesSold = int(request.form.get("shares"))

        # check if enough shares of stock are in the portfolio -> execute sell and save in db transactions
        if (len(stocksInPortfolio) == 0) or (numberOfSharesSold > int(stocksInPortfolio[0]["shares"])):

            return apology("Not enough stocks in Portfolio!")

        db.execute("INSERT INTO transactions (type, name, symbol, shares, price, date, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   "sell", currentStock["name"], currentStock["symbol"], numberOfSharesSold, currentStock["price"], datetime.now(), session.get("user_id"))

        # calculate totalCost of the buy order
        totalPrice = currentStock["price"] * float(numberOfSharesSold)

        # update cash balance of user
        newBalance = cashOfUser[0]["cash"] + totalPrice
        db.execute("UPDATE users SET cash = ? WHERE id = ?", newBalance, session.get("user_id"))

        # check portfolio for existing stocks of this kind and update it
        # sharesBeforeTransaction = db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?", session.get("user_id"), currentStock["symbol"])

        stocksInPortfolio = stocksInPortfolio[0]["shares"] - int(numberOfSharesSold)
        # update portfolio with shares
        if stocksInPortfolio > 0:
            db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?",
                       stocksInPortfolio, session.get("user_id"), currentStock["symbol"])
        # if stocks are 0, then delete from usersPortfolio db
        else:
            # delete portfolio entry with shares
            db.execute("DELETE FROM portfolio WHERE user_id = ? AND symbol = ?", session.get("user_id"),  currentStock["symbol"])

        # show currentStock information in
        return render_template("sold.html", numberOfShares=numberOfSharesSold, name=currentStock["name"],
                               symbol=currentStock["symbol"], price=usd(currentStock["price"]), newBalance=usd(newBalance), totalPrice=totalPrice)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # get infos about existing stocks in portfolio of the user
        userPortfolio = db.execute("select symbol, shares from portfolio where user_id=?", session.get("user_id"))
        return render_template("/sell.html", userPortfolio=userPortfolio)
