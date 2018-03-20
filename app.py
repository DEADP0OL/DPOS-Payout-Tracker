from flask import Flask, render_template, flash, request
from wtforms import Form, TextField, TextAreaField, validators, StringField, SubmitField
from Functions import *
from socket import gethostname
 
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
    payoutstats=None#pd.DataFrame(columns=[])#address', 'productivity', 'days between payouts', 'total paid','payout count', '% shared'])
    if request.method == 'POST':
        address=request.form['address']
        dayspan=request.form['dayspan']
        print (address,dayspan)
        payoutstats=getpayoutstats(address)
        if form.validate():
            # Save the comment here.
            flash("Success")
        else:
            flash('Error: All the form fields are required. ')
    if payoutstats is None:
        table=""
    else:
        table=payoutstats.to_html(formatters={'percent shared': '{:,.1%}'.format})
    return render_template('tracker.html', form=form,show=table)
 
if __name__ == "__main__":
    if 'liveconsole' not in gethostname():
        app.run()
