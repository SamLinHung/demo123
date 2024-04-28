import time
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.common import BarData
import datetime as dt

class TestApp(EWrapper, EClient):
    
    def __init__(self):
        EClient.__init__(self, self)
        self.data = []
    
    def error(self, reqId, errorCode, errorString):
        print("Error. Id: ", reqId, " Code: ", errorCode, " Msg: ", errorString)
    
    def historicalData(self, reqId, bar):
        print("HistoricalData. ReqId:", reqId, "BarData.", bar)
    
    def historicalDataEnd(self, reqId, start, end):
        print("HistoricalDataEnd. ReqId:", reqId, "from", start, "to", end)
        self.disconnect()
    
    def realTimeBar(self, reqId: int, time: int, open_: float, high: float, low: float, close: float, volume: int, wap: float, count: int):
        print("RealTimeBar. ReqId:", reqId, "Time:", dt.datetime.fromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S'), "Open:", open_, "High:", high, "Low:", low, "Close:", close, "Volume:", volume, "WAP:", wap, "Count:", count)
    
    def tickPrice(self, reqId, tickType, price: float, attrib):
        print(reqId, tickType, price, attrib)
    
    def updateMktDepth(self, reqId, position: int, operation: int, side: int, price: float, size: int):
        print(reqId, position, operation, side, price, size)
def main():
    app = TestApp()
    app.connect("127.0.0.1", 7497, 0)
    
    if not app.isConnected():
        print("未連接")
    else:
        print("已連接")
    
    contract = Contract()
    contract.symbol = "EUR"
    contract.secType = "CASH"
    # contract.exchange = "IDEALPRO"
    contract.exchange = "IDEALPRO"
    contract.currency = "USD"
    time.sleep(5)
    print("reqRealTimeBars before")
    app.reqRealTimeBars(3001, contract, 5, "MIDPOINT", True, [])
    # app.reqMktData(1003, contract, "", False, False, [])

    # app.reqMktDepth(2001, contract, 5, False, [])

    print("reqRealTimeBars after")
    
    app.run()

if __name__ == "__main__":
    main()
