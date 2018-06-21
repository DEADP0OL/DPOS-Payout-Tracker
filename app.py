from flask import Flask, render_template, flash, request
from wtforms import Form, TextField, TextAreaField, validators, StringField, SubmitField
from bokeh.embed import components
from socket import gethostname
from Functions import *
import re

# App config.
DEBUG = True
app = Flask(__name__)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = '7d441f27d441f27567d441f2b6176a'
 
class ReusableForm(Form):
    address = TextField('address:', validators=[validators.required()])
    dayspan = TextField('dayspan:', validators=[validators.required()])
 
@app.route("/", methods=['GET', 'POST'])
def tracker():
    form = ReusableForm(request.form) 
    print (form.errors)
    payoutstats=None
    address=None
    if request.method == 'POST':
        address=request.form['address']
        dayspan=request.form['dayspan']
        if address=='':
            address=None
        if dayspan=='':
            dayspan=None
        if address is not None and dayspan is not None:
            payoutstats,otherpools,payperday,expectedpayperday,balance=getpayoutstats(address,int(dayspan))
        if form.validate():
            flash("Success")
        else:
            flash('Error: All the form fields are required. ')
    if (address is None):
        table=""
        return render_template('form.html', form=form)
    else:
        if (payoutstats is None):
            table=""
            flash('Error: Invalid Address.')
            return render_template('form.html', form=form)
        else:
            table=payoutstats.to_html(border = 0,classes=["display"])
            table2=otherpools.to_html(border = 0,classes=["display"])
            pscript,pdiv=components(create_figure(payoutstats))
            return render_template('tracker.html', form=form,show=table,show2=table2,dayspan=dayspan,address=address,script=pscript,div=pdiv,earnings=payperday,expectedearnings=expectedpayperday,balance=balance)

if __name__ == "__main__":
    if 'liveconsole' not in gethostname():
        app.run()
