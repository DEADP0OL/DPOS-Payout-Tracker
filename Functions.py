import pandas as pd
import requests
import json
import numpy as np
import re
from bokeh.plotting import figure, show, ColumnDataSource
from bokeh.models import  HoverTool, WheelZoomTool, BoxZoomTool, ResetTool

def getpubkey(url,address):
    pubkey = requests.get(url+'accounts/getPublicKey?address='+address).json()['publicKey']
    return pubkey

def getbalance(url,address):
    balance = float(requests.get(url+'accounts/getBalance?address='+address).json()['balance'])/100000000
    return balance

def getvotes(url,address):
    votes = pd.DataFrame(requests.get(url+'accounts/delegates?address='+address).json()['delegates'])
    return votes

def getvoters(url,address):
    pubkey = getpubkey(url,address)
    voters = pd.DataFrame(requests.get(url+'delegates/voters?publicKey='+pubkey).json()['accounts'])
    return voters

def getdelegates(url):
    delegates = pd.DataFrame(requests.get(url+'delegates?orderBy=vote').json()['delegates'])
    delegates['vote']=pd.to_numeric(delegates['vote'])
    return delegates

def getincomingtxs(url,address,days=35):
    i=0
    incomingtxs = pd.DataFrame(requests.get(url+'transactions?recipientId='+address+'&offset='+str(i)+'&orderBy=timestamp:desc').json()['transactions'])
    incomingtxs.sort_values(by='timestamp',ascending=False)
    now = incomingtxs['timestamp'].iloc[0]
    incomingtxs['Days_Elapsed']=(now-incomingtxs['timestamp'])/(24*60*60)
    last = incomingtxs['Days_Elapsed'].iloc[-1]
    length = len(incomingtxs)
    while last <= days:
        i=i+length
        incomingtxs1 = pd.DataFrame(requests.get(url+'transactions?recipientId='+address+'&offset='+str(i)+'&orderBy=timestamp:desc').json()['transactions'])
        if not incomingtxs1.empty:
            incomingtxs1['Days_Elapsed']=(now-incomingtxs1['timestamp'])/(24*60*60)
            incomingtxs=incomingtxs.append(incomingtxs1,ignore_index=True)
            last = incomingtxs['Days_Elapsed'].iloc[-1]
        else:
            last = days+1
    incomingtxs=incomingtxs[incomingtxs['Days_Elapsed']<=days]
    return incomingtxs

def getcoindata(address):
    if address[-3:]=='LWF':
        url='https://wallet.lwf.io/api/'
        coin='LWF'
        payaccts=json.load(open('LWFPayoutAccts.json'))
        pools=getpools('LWFPools.txt')
    elif address[-1:]=='X':
        url='https://wallet.oxycoin.io/api/'
        coin='OXY'
        payaccts=json.load(open('OXYPayoutAccts.json'))
        pools=getpools('OXYPools.txt')
    else:
        url=None
        payaccts=None
        pools=None
        coin=None
    if payaccts is not None:
        payaccts={i['address']:i['payaddress'] for i in payaccts}
    return url,payaccts,pools,coin    
def getpools(file):
    pools = open(file, 'r').read()
    pools = pools.replace('`','').lower()
    pools = max(pools.split('*'), key=len).split(';')
    pools = pd.DataFrame(pools,columns=['string'])
    pools['string'].str.lower()
    pools = pools['string'].str.extractall(r'^[*]?\s*\-*\s*(?P<delegate>[\w.-]+)?\,*\s*(?P<delegate2>[\w]+)?\,*\s*(?P<delegate3>[\w]+)?\,*\s*(?P<delegate4>[\w]+)?\,*\s*(?P<delegate5>[\w]+)?\,*\s(?P<website>[\w./:-]+)*\s*\(\`*[0-9x]*?(?P<percentage>[0-9.]+)\%\-*(?P<listed_frequency>\w+)*\`*\,*\s*(?:min)?\.*\s*(?:payout)?\s*(?P<min_payout>[0-9.]+)*\s*(?P<coin>\w+)*?\s*(?:payout)?\`*[\w ]*\)$')
    dropcols=['coin']
    pools=pools.drop(dropcols,axis=1)
    pools.loc[pools['listed_frequency']=='w', ['listed_frequency']] = 7
    pools.loc[pools['listed_frequency']=='d', ['listed_frequency']] = 1
    pools.loc[pools['listed_frequency']=='2d', ['listed_frequency']] = 2
    pools['listed_frequency']=pd.to_numeric(pools['listed_frequency'])
    pools['min_payout']=pd.to_numeric(pools['min_payout'])
    pools.rename(columns={'percentage': 'listed % share'}, inplace=True)
    pools=pd.melt(pools, id_vars=['listed % share','listed_frequency','min_payout','website'], var_name='delegatenumber', value_name='delegate')
    del pools['delegatenumber']
    pools=pools.loc[pools['delegate'].notnull()]
    pools=pools.reset_index(drop=True)
    return pools

def getpayoutstats(address,days=35,numberofdelegates=201,blockrewards=5,blockspermin=4,orderby='rewards/day'):
    totalrewardsperday=blockrewards*blockspermin*60*24/numberofdelegates
    url,payaccts,pools,coin=getcoindata(address)
    if (url is None) or (payaccts is None):
        return None,None,None,None,None
    balance=getbalance(url,address)
    if balance==0:
        return None,None,None,None,None
    incomingtxs=getincomingtxs(url,address,days)
    votes=getvotes(url,address)
    votes['address']=votes['address'].replace(payaccts)
    txstats=incomingtxs.sort_values(by=['senderId','timestamp'],ascending=False)
    txstats['frequency']=txstats['Days_Elapsed'].diff()
    txstats.loc[txstats['frequency']<0, 'frequency'] = None
    txstats['count']=1
    txstats['payments']=txstats['amount']
    txstats=txstats.groupby('senderId').agg({'Days_Elapsed':'first','frequency':'mean','amount':'sum','payments':'mean','count':'count'}).reset_index()
    txstats=txstats[txstats['amount']>0]
    payoutstats=pd.merge(votes,txstats,how='left',left_on='address',right_on='senderId')
    payoutstats['vote count'] = payoutstats.groupby('senderId')['senderId'].transform('count')
    payoutstats['total approval'] = payoutstats.groupby('senderId')['approval'].transform('sum')
    payoutstats['amount']=pd.to_numeric(payoutstats['amount'])/100000000
    payoutstats['amount']=payoutstats['amount']*payoutstats['total approval']/(payoutstats['approval']*payoutstats['vote count'])/payoutstats['vote count']
    payoutstats['payments']=payoutstats['payments']*payoutstats['total approval']/(payoutstats['approval']*payoutstats['vote count'])/payoutstats['vote count']
    payoutstats['vote']=pd.to_numeric(payoutstats['vote'])/100000000
    payoutstats['payments']=pd.to_numeric(payoutstats['payments'])/100000000
    payoutstats['frequency']=pd.to_numeric(payoutstats['frequency'])
    payoutstats['portion']=((days*blockrewards*24*60*blockspermin/numberofdelegates)*(balance/payoutstats['vote']))
    payoutstats['% shared']=payoutstats['amount']/payoutstats['portion']
    payoutstats['paid x approval']=payoutstats['amount']*payoutstats['approval']/100
    payoutstats.loc[payoutstats['count']>1,'% shared'] = payoutstats['payments']/((payoutstats['frequency']*5*24*60*4/201)*(balance/payoutstats['vote']))
    payoutstats.loc[payoutstats['rank']>201, ['% shared','portion']] = None
    payoutstats.rename(columns={'username': 'delegate', 'Days_Elapsed': 'last paid (days)','amount':'total paid','count':'payouts','frequency':'pay freq (days)','% shared':'percent shared'}, inplace=True)
    payoutstats = pd.merge(payoutstats,pools,how='left',on='delegate')
    payoutstats=payoutstats.set_index('delegate')
    payoutstats.index.name = None
    payoutstats['listed % share']=pd.to_numeric(payoutstats['listed % share'])
    payoutstats['rewards/day']=((balance/payoutstats['vote'])*totalrewardsperday*(payoutstats['listed % share']/100))
    payoutstats['minpayused']=1
    payoutstats.loc[payoutstats['min_payout']>0, ['minpayused']] = payoutstats['min_payout']
    payoutstats.loc[payoutstats['rank']>201, ['rewards/day']] = np.nan
    payoutstats['comments']=''
    cols=['payouts','pay freq (days)','total paid','last paid (days)','paid x approval','rewards/day']
    for i in cols:
        payoutstats[i]=payoutstats[i].round(2)
    payoutstats.loc[(payoutstats['listed_frequency']*2<payoutstats['last paid (days)'])&(payoutstats['minpayused']/payoutstats['rewards/day']+payoutstats['listed_frequency']<payoutstats['last paid (days)'])&(payoutstats['listed_frequency']>0), ['comments']] = 'payout overdue'
    payoutstats.loc[(payoutstats['last paid (days)'].isnull()&(payoutstats['listed_frequency'])>0), ['comments']] = 'no payouts'
    payoutstats.loc[payoutstats['rank']>201, ['comments']] = 'not forging'
    payoutstats.loc[payoutstats['listed % share'].isnull(), ['comments']] = 'not listed pool'
    dropcols=['address','productivity','senderId','rate','publicKey','producedblocks','missedblocks','approval','vote','payments','portion','vote count','total approval','percent shared','payouts','paid x approval','minpayused','website']
    payoutstats=payoutstats.drop(dropcols,axis=1)
    payoutstats=payoutstats.sort_values(by=orderby,ascending=False)
    earnedperday = str((payoutstats['total paid'].sum()/days).round(2))+' '+coin
    expectedearnings = str((payoutstats['rewards/day'].sum()).round(2))+' '+coin
    balance=str(round(balance,2))+' '+coin
    payoutstats = payoutstats.replace(np.nan, '', regex=True)
    otherpools=pools.loc[~pools['delegate'].isin(list(payoutstats.index.values))]
    otherpools = otherpools.replace(np.nan, '', regex=True)
    otherpools = otherpools.set_index('delegate')
    otherpools.index.name = None
    return payoutstats,otherpools,earnedperday,expectedearnings,balance

def create_figure(df):
    df = df.reset_index()
    x=df['rank'].tolist()
    y=df['total paid'].tolist()
    desc=df['index'].tolist()
    data=dict(x=x,y=y,desc=desc)
    source = ColumnDataSource(data)
    hover = HoverTool(tooltips=[
            ("rank", "@x"),
            ("paid", "@y{0.0}"),
            ("delegate", "@desc"),
            ])
    plot=figure(title=None,x_axis_label='rank',y_axis_label='total paid', tools=[hover,'pan','box_zoom','reset'],plot_width=600, plot_height=300)
    plot.circle('x','y', size=10,source=source)
    plot.toolbar.active_scroll = plot.select_one(WheelZoomTool)
    plot.toolbar.active_drag = plot.select_one(BoxZoomTool)
    return plot
