import MetaTrader5 as mt5
accounts = [
    ("Order Block Gold",5050872303,"XlCeWb*0","MetaQuotes-Demo",r"C:\\MT5-OrderBlock\\terminal64.exe"),
    ("Breakout Gold",5050872272,"RmY-5vFf","MetaQuotes-Demo",r"C:\\MT5-Breakout\\terminal64.exe"),
    ("Confluence Demo",107024114,"-6KpAxAh","MetaQuotes-Demo",r"C:\\MT5-Confluence\\terminal64.exe"),
    ("The5ers Funded",26259636,"wfbyCDPR--96","FivePercentOnline-Real",r"C:\\MT5-The5ers\\terminal64.exe"),
    ("Order block demo",5050461504,"@0LrLwAt","MetaQuotes-Demo",r"C:\\Program Files\\MetaTrader 5\\terminal64.exe"),
    ("MultiTF Rejection Demo",5050608377,"OrS@Os7b","MetaQuotes-Demo",r"C:\\MT5-MTF\\terminal64.exe"),
]
for label,login,pwd,server,path in accounts:
    mt5.shutdown()
    ok = mt5.initialize(login=login,password=pwd,server=server,path=path,timeout=15000)
    if ok:
        info = mt5.account_info()
        print(f"OK | {label} | login={login} | balance={getattr(info,'balance',None)}")
    else:
        print(f"FAIL | {label} | login={login} | err={mt5.last_error()}")
mt5.shutdown()
