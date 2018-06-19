import pandas as pd
import requests
import json
import numpy as np
import re
from bokeh.plotting import figure, show, ColumnDataSource
from bokeh.models import  HoverTool, WheelZoomTool, BoxZoomTool, ResetTool
from bokeh.transform import linear_cmap

def getpubkey(url,address):
    pubkey = requests.get(url+'accounts/getPublicKey?address='+address).json()['publicKey']
    return pubkey

def getbalance(url,address,multiplier=100000000):
    balance = requests.get(url+'accounts/getBalance?address='+address).json()['balance']
    try:
        balance = float(balance)/multiplier
    except:
        pass
    return balance

def getvotes(url,address):
    votes = pd.DataFrame(requests.get(url+'accounts/delegates?address='+address).json()['delegates'])
    return votes

def getvoters(url,address):
    pubkey = getpubkey(url,address)
    voters = pd.DataFrame(requests.get(url+'delegates/voters?publicKey='+pubkey).json()['accounts'])
    return voters

def getdelegates(url,minapproval=1,multiplier=100000000):
    i=0
    delegates = pd.DataFrame(requests.get(url+'delegates?offset='+str(i)+'&orderBy=vote').json()['delegates'])
    delegates['vote']=pd.to_numeric(delegates['vote'])/multiplier
    delegates['approval']=pd.to_numeric(delegates['approval'])
    approval = delegates['approval'].iloc[-1]
    length = len(delegates)
    while approval>=minapproval:
        i=i+length
        delegates1 = pd.DataFrame(requests.get(url+'delegates?offset='+str(i)+'&orderBy=vote').json()['delegates'])
        if not delegates1.empty:
            delegates1['vote']=pd.to_numeric(delegates1['vote'])/multiplier
            delegates1['approval']=pd.to_numeric(delegates1['approval'])
            approval = delegates1['approval'].iloc[-1]
            delegates=delegates.append(delegates1,ignore_index=True)
        else:
            approval = 0
    delegates=delegates.loc[delegates['approval']>=minapproval]
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

def getvotetxs(url,days=35):
    i=0
    votetxs = pd.DataFrame(requests.get(url+'transactions?type=3&offset='+str(i)+'&orderBy=timestamp:desc').json()['transactions'])
    votetxs.sort_values(by='timestamp',ascending=False)
    now = votetxs['timestamp'].iloc[0]
    votetxs['Days_Elapsed']=(now-votetxs['timestamp'])/(24*60*60)
    last = votetxs['Days_Elapsed'].iloc[-1]
    length = len(votetxs)
    while last <= days:
        i=i+length
        votetxs1 = pd.DataFrame(requests.get(url+'transactions?type=3&offset='+str(i)+'&orderBy=timestamp:desc').json()['transactions'])
        if not votetxs1.empty:
            votetxs1['Days_Elapsed']=(now-votetxs1['timestamp'])/(24*60*60)
            votetxs=votetxs.append(votetxs1,ignore_index=True)
            last = votetxs['Days_Elapsed'].iloc[-1]
        else:
            last = days+1
    votetxs=votetxs.loc[votetxs['Days_Elapsed']<=days]
    return votetxs

def getoutgoingvotes(url,address,days=35):
    votetxs=getvotetxs(url,days)
    votes=getvotes(url,address)
    outgoingvotes=votetxs.loc[votetxs['senderId']==address]
    outgoingvotes['added']=""
    outgoingvotes['removed']=""
    votes['days_voted']=days
    for index,row in outgoingvotes.iterrows():
        id=row['id']
        vote=pd.DataFrame(requests.get(url+'transactions/get?id='+str(id)).json())['transaction']['votes']
        votes.loc[votes['publicKey'].isin(vote.get("added")),['days_voted']]=np.minimum(votes['days_voted'],row['Days_Elapsed'])
    return votes

def getcoindata(address):
    if address[-3:]=='LWF':
        url='https://wallet.lwf.io/api/'
        coin='LWF'
        payaccts=json.load(open('LWFPayoutAccts.json'))
        pools=getpools('LWFPools.txt')
        numdelegates=201
        blockrewards=5
        blockspermin=4
        multiplier=100000000
    elif address[-1:]=='X':
        url='https://wallet.oxycoin.io/api/'
        coin='OXY'
        payaccts=json.load(open('OXYPayoutAccts.json'))
        pools=getpools('OXYPools.txt')
        numdelegates=201
        blockrewards=5
        blockspermin=4
        multiplier=100000000
    elif address[:3]=='ONZ':
        url='https://node06.onzcoin.com/api/'
        coin='ONZ'
        payaccts=json.load(open('ONZPayoutAccts.json'))
        pools=getpools('ONZPools.txt')
        numdelegates=101
        blockrewards=50
        blockspermin=4
        multiplier=100000000
    else:
        url=None
        payaccts=None
        pools=None
        coin=None
    if payaccts is not None:
        payaccts={i['address']:i['payaddress'] for i in payaccts}
    return url,payaccts,pools,coin,numdelegates,blockrewards,blockspermin,multiplier

def getpools(file):
    pools = open(file, 'r').read()
    pools = pools.replace('`','').lower()
    pools = max(pools.split('*'), key=len).split(';')
    pools = pd.DataFrame(pools,columns=['string'])
    pools['string'].str.lower()
    pools = pools['string'].str.extractall(r'^[*]?\s*\-*\s*(?P<delegate>[\w.-]+)?\,*\s*(?P<delegate2>[\w]+)?\,*\s*(?P<delegate3>[\w]+)?\,*\s*(?P<delegate4>[\w]+)?\,*\s*(?P<delegate5>[\w]+)?\,*\s(?P<website>[\w./:-]+)*\s*\(\`*[0-9x]*?(?P<percentage>[0-9.]+)\%\s*\-*(?P<listed_frequency>\w+)*\`*\,*\s*(?:min)?\.*\s*(?:payout)?\s*(?P<min_payout>[0-9.]+)*\s*(?P<coin>\w+)*?\s*(?:payout)?\`*[\w ]*\).*?$')
    dropcols=['coin']
    pools=pools.drop(dropcols,axis=1)
    pools.loc[pools['listed_frequency']=='c', ['listed_frequency']] = np.nan
    pools.loc[pools['listed_frequency']=='2d', ['listed_frequency']] = 2
    pools.loc[pools['listed_frequency']=='w', ['listed_frequency']] = 7
    pools.loc[pools['listed_frequency']=='d', ['listed_frequency']] = 1
    pools['listed_frequency']=pd.to_numeric(pools['listed_frequency'])
    pools['min_payout']=pd.to_numeric(pools['min_payout'])
    pools.rename(columns={'percentage': 'listed % share'}, inplace=True)
    pools=pd.melt(pools, id_vars=['listed % share','listed_frequency','min_payout','website'], var_name='delegatenumber', value_name='delegate')
    del pools['delegatenumber']
    pools=pools.loc[pools['delegate'].notnull()]
    pools=pools.reset_index(drop=True)
    pools['listed % share']=pd.to_numeric(pools['listed % share'])
    pools=pools.sort_values(by='listed % share',ascending=False)
    return pools

def getpoolstats(pools,delegates,numdelegates,blockrewards,blockspermin,balance=10000):
    delegates=delegates[['username','rank','vote']]
    if balance>80000:
        rnd=2
    else:
        rnd=3
    totalrewardsperday=blockrewards*blockspermin*60*24/numdelegates
    poolstats=pd.merge(pools,delegates,how='left',left_on='delegate',right_on='username')
    poolstats['rewards/day']=((balance/poolstats['vote'])*totalrewardsperday*(poolstats['listed % share']/100)).round(rnd)
    poolstats=poolstats.sort_values(by='rewards/day',ascending=False)
    del poolstats['username']
    poolstats=poolstats[poolstats['vote']>=0]
    poolstats['rank']=poolstats['rank'].astype('int64')
    poolstats['listed % share']=poolstats['listed % share'].astype('int64')
    del poolstats['vote']
    cols = list(poolstats)
    cols.insert(0, cols.pop(cols.index('rank')))
    poolstats = poolstats.ix[:, cols]
    poolstats['comments']=''
    poolstats.loc[poolstats['rank']>numdelegates, ['rewards/day']] = np.nan
    poolstats.loc[poolstats['rank']>numdelegates, ['comments']] = 'not forging'
    return poolstats

def getpayoutstats(address,days=35,orderby='rewards/day'):
    try:
        url,payaccts,pools,coin,numberofdelegates,blockrewards,blockspermin,multiplier=getcoindata(address)
        balance=getbalance(url,address)
        if balance>80000:
            rnd=2
        else:
            rnd=3
        totalrewardsperday=blockrewards*blockspermin*60*24/numberofdelegates
        incomingtxs=getincomingtxs(url,address,days)
        votes=getoutgoingvotes(url,address,days)
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
        payoutstats['amount']=pd.to_numeric(payoutstats['amount'])/multiplier
        payoutstats['amount']=payoutstats['amount']*payoutstats['total approval']/(payoutstats['approval']*payoutstats['vote count'])/payoutstats['vote count']
        payoutstats['payments']=payoutstats['payments']*payoutstats['total approval']/(payoutstats['approval']*payoutstats['vote count'])/payoutstats['vote count']
        payoutstats['vote']=pd.to_numeric(payoutstats['vote'])/multiplier
        payoutstats['payments']=pd.to_numeric(payoutstats['payments'])/multiplier
        payoutstats['frequency']=pd.to_numeric(payoutstats['frequency'])
        payoutstats['portion']=((days*blockrewards*24*60*blockspermin/numberofdelegates)*(balance/payoutstats['vote']))
        payoutstats['% shared']=payoutstats['amount']/payoutstats['portion']
        payoutstats['paid x approval']=payoutstats['amount']*payoutstats['approval']/100
        payoutstats.loc[payoutstats['count']>1,'% shared'] = payoutstats['payments']/((payoutstats['frequency']*5*24*60*4/numberofdelegates)*(balance/payoutstats['vote']))
        payoutstats.loc[payoutstats['rank']>numberofdelegates, ['% shared','portion']] = None
        payoutstats.rename(columns={'username': 'delegate', 'Days_Elapsed': 'last paid (days)','amount':'total paid','count':'payouts','frequency':'pay freq (days)','% shared':'percent shared'}, inplace=True)
        payoutstats = pd.merge(payoutstats,pools,how='left',on='delegate')
        payoutstats=payoutstats.set_index('delegate')
        payoutstats.index.name = None
        payoutstats['listed % share']=pd.to_numeric(payoutstats['listed % share'])
        payoutstats['rewards/day']=((balance/payoutstats['vote'])*totalrewardsperday*(payoutstats['listed % share']/100))
        payoutstats['minpayused']=payoutstats['min_payout']
        payoutstats.loc[payoutstats['minpayused'].isnull(), ['minpayused']] = 1
        payoutstats.loc[payoutstats['rank']>numberofdelegates, ['rewards/day']] = np.nan
        payoutstats['comments']=''
        cols=['payouts','pay freq (days)','last paid (days)','paid x approval']
        for i in cols:
            payoutstats[i]=payoutstats[i].round(0)
        cols=['total paid','rewards/day']
        for i in cols:
            payoutstats[i]=payoutstats[i].round(rnd)
        payoutstats.loc[(payoutstats['listed_frequency']*2<payoutstats['last paid (days)'])&(payoutstats['minpayused']/payoutstats['rewards/day']+payoutstats['listed_frequency']<payoutstats['last paid (days)'])&(payoutstats['listed_frequency']>0), ['comments']] = 'payout overdue'
        payoutstats.loc[(payoutstats['last paid (days)'].isnull())&((payoutstats['listed_frequency'])>0), ['comments']] = 'no payouts'
        payoutstats.loc[(payoutstats['last paid (days)'].isnull())&((payoutstats['minpayused']/payoutstats['rewards/day']>np.maximum(payoutstats['listed_frequency'],payoutstats['days_voted']))), ['comments']] = 'min pay not met'
        payoutstats.loc[(payoutstats['comments']=='no payouts')&(payoutstats['listed_frequency']>payoutstats['days_voted']), ['comments']] = 'recently voted'
        payoutstats.loc[payoutstats['rank']>numberofdelegates, ['comments']] = 'not forging'
        payoutstats.loc[payoutstats['listed % share'].isnull(), ['comments']] = 'not listed pool'
        payoutstats['total paid']=(payoutstats['total paid']/payoutstats['days_voted']).round(rnd)
        dropcols=['address','productivity','senderId','rate','publicKey','producedblocks','missedblocks','approval','vote','payments','portion','vote count','total approval','percent shared','payouts','paid x approval','minpayused','website','days_voted']
        dropcols = [c for c in dropcols if c in payoutstats.index]
        payoutstats=payoutstats.drop(dropcols,axis=1)
        payoutstats=payoutstats.sort_values(by=orderby,ascending=False)
        delegates=getdelegates(url,.1,multiplier)
        poolstats=getpoolstats(pools,delegates,numberofdelegates,blockrewards,blockspermin,balance)
        earnedperday = "{:,}".format(round(payoutstats['total paid'].sum(),2))+" "+coin       
        expectedearnings = "{:,}".format(round(payoutstats['rewards/day'].sum(),2))+' '+coin
        if (balance>0)and(round(payoutstats['total paid'].sum(),2)>0)and(round(payoutstats['rewards/day'].sum(),2)>0):
            earnedperday = earnedperday+" ("+str(round(payoutstats['total paid'].sum()*365*100/balance,2))+"%/yr)"
            expectedearnings = expectedearnings+" ("+str(round(payoutstats['rewards/day'].sum()*365*100/balance,2))+"%/yr)"
        balance="{:,}".format(round(balance,2))+" "+coin
        payoutstats = payoutstats.replace(np.nan, '', regex=True)
        payoutstats.rename(columns={'total paid': 'act pay/day', 'rewards/day': 'exp pay/day'}, inplace=True)
        otherpools=poolstats.loc[~poolstats['delegate'].isin(list(payoutstats.index.values))]
        otherpools = otherpools.replace(np.nan, '', regex=True)
        otherpools = otherpools.set_index('delegate')
        otherpools.rename(columns={'rewards/day': 'exp pay/day'}, inplace=True)
        otherpools.index.name = None
        otherpools = otherpools[~otherpools.index.duplicated(keep='first')]
        poolstats = poolstats[~poolstats.index.duplicated(keep='first')]
    except:
        return None,None,None,None,None
    return payoutstats,otherpools,earnedperday,expectedearnings,balance

def create_figure(df):
    df = df.reset_index()
    factor=1
    bias=.15
    x=df['rank'].tolist()
    y=df['act pay/day'].tolist()
    avg=pd.to_numeric(df['exp pay/day']).mean()
    y2=((pd.to_numeric(df['exp pay/day'])-pd.to_numeric(df['act pay/day']).fillna(0))).tolist()
    exppay=df['exp pay/day'].tolist()
    sharing=df['listed % share'].tolist()
    desc=df['index'].tolist()
    data=dict(x=x,y=y,desc=desc,y2=y2,exppay=exppay,sharing=sharing)
    source = ColumnDataSource(data)
    hover = HoverTool(tooltips=[
            ("rank", "@x"),
            ("act pay/day", "@y{0.00}"),
            ("exp pay/day", "@exppay{0.00}"),
            ("sharing %", "@sharing"),
            ("delegate", "@desc"),
            ])
    plot=figure(title=None,x_axis_label='rank',y_axis_label='actual pay per day',tools=[hover,'pan','box_zoom','reset'],plot_width=700, plot_height=300)
    plot.circle('x','y', size=12,source=source,fill_color=linear_cmap('y2', ['darkgreen','green','blue','red','darkred' ], -avg*factor-bias, avg*factor+bias),fill_alpha=0.6,line_color=None)
    plot.toolbar.active_scroll = plot.select_one(WheelZoomTool)
    plot.toolbar.active_drag = plot.select_one(BoxZoomTool)
    return plot
