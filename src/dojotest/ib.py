import sys
from datetime import datetime
from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.tag_value import TagValue
from threading import Thread
import queue
from ibapi.order import *
from ibapi.order_state import *
from dojotest.base.auth import Auth
from dojotest.base.report import Report
import socketio
import pandas as pd
from datetime import timedelta
from enum import Enum
import re
import quantstats as qs
import time


class RequestParams(Object):
    def __init__(self) -> None:
        self.startDateTime = ""
        self.endDateTime = ""
        self.barSize = ""


class Result:
    def __init__(self) -> None:
        self.Status = False
        self.Msg = None

    def true(self, msg):
        self.Status = True
        self.Msg = msg

    def false(self, msg):
        self.Status = False
        self.Msg = msg


class BarSizeType(Enum):
    S = 'sec'
    M = 'min'
    H = 'hour'
    D = 'day'
    W = 'week'
    MM = 'month'


class RealtimeBarData(object):
    def __init__(self):
        self.time = None
        self.open = None
        self.high = None
        self.low = None
        self.close = None
        self.volume = None
        self.wap = None
        self.count = None
        self.reqId = None


class OpenOrderData(object):
    def __init__(self):
        self.permId = None
        self.clientId = None
        self.orderId = None
        self.account = None
        self.symbol = None
        self.secType = None
        self.exchange = None
        self.action = None
        self.orderType = None
        self.totalQuantity = None
        self.cashQty = None
        self.lmtPrice = None
        self.auxPrice = None
        self.status = None


class ibWrapper(EWrapper):

    # error handling code
    def init_error(self):
        error_queue = queue.Queue()
        self._my_errors = error_queue

    def get_error(self, timeout=5):
        if self.is_error():
            try:
                return self._my_errors.get(timeout=timeout)
            except queue.Empty:
                return None

        return None

    def is_error(self):
        an_error_if = not self._my_errors.empty()
        return an_error_if

    def error(self, id, errorCode, errorString):
        # Overriden method
        errormsg = "IB error id %d errorcode %d string %s" % (
            id, errorCode, errorString)
        self._my_errors.put(errormsg)

    # Time telling code
    def init_time(self):
        time_queue = queue.Queue()
        self._time_queue = time_queue

        return time_queue

    def currentTime(self, time_from_server):
        # Overriden method
        self._time_queue.put(time_from_server)

    def tickSnapshotEnd(self, reqId: int):
        super().tickSnapshotEnd(reqId)
        print("TickSnapshotEnd. TickerId:", reqId)


class ibClinet(EClient):
    def __init__(self, wrapper):
        # Set up with a wrapper inside
        EClient.__init__(self, wrapper)

    @staticmethod
    def FillTwapParams(baseOrder: Order, strategyType: str, startTime: str, endTime: str, allowPastEndTime: bool, monetaryValue: float):
        baseOrder.algoStrategy = "Twap"
        baseOrder.algoParams = []
        baseOrder.algoParams.append(TagValue("strategyType", strategyType))
        baseOrder.algoParams.append(TagValue("startTime", startTime))
        baseOrder.algoParams.append(TagValue("endTime", endTime))
        baseOrder.algoParams.append(
            TagValue("allowPastEndTime", int(allowPastEndTime)))
        baseOrder.cashQty = monetaryValue

    @staticmethod
    def FillAdaptiveParams(baseOrder: Order, priority: str):
        baseOrder.algoStrategy = "Adaptive"
        baseOrder.algoParams = []
        baseOrder.algoParams.append(TagValue("adaptivePriority", priority))

    @staticmethod
    def FillVwapParams(baseOrder: Order, maxPctVol: float, startTime: str,
                       endTime: str, allowPastEndTime: bool, noTakeLiq: bool):
        baseOrder.algoStrategy = "Vwap"
        baseOrder.algoParams = []
        baseOrder.algoParams.append(TagValue("maxPctVol", maxPctVol))
        baseOrder.algoParams.append(TagValue("startTime", startTime))
        baseOrder.algoParams.append(TagValue("endTime", endTime))
        baseOrder.algoParams.append(TagValue("allowPastEndTime",
                                             int(allowPastEndTime)))
        baseOrder.algoParams.append(TagValue("noTakeLiq", int(noTakeLiq)))

    def speaking_clock(self):
        print("Getting the time from the server... ")

        # Make a place to store the time we're going to return
        # This is a queue
        time_storage = self.wrapper.init_time()

        # This is the native method in EClient, asks the server to send us the time please
        self.reqCurrentTime()

        # Try and get a valid time
        MAX_WAIT_SECONDS = 10

        try:
            current_time = time_storage.get(timeout=MAX_WAIT_SECONDS)
        except queue.Empty:
            print("Exceeded maximum wait for wrapper to respond")
            current_time = None

        while self.wrapper.is_error():
            print(self.get_error())

        return current_time


class Hsocket(socketio.Client):
    def __init__(self) -> None:
        # socketio.Client.__init__(self)
        # socketio.Client.__init__(self)
        # super(Hsocket, self).__init__()
        # self.ST = socketio.Client()
        # self.__localhost = 'http://localhost:3000'
        # self.__localhost = 'http://request.dojotest.com:8004'
        # self.__localhost = 'http://35.84.179.106:8004'
        self.SocketioDict = {}
        self.__localhost = 'http://request.dojotest.com:8004'
        # self.ST.on('responseData', self.__on_message)
        self.IsConnect = False
        self.__BarSize = 0
        self.__BarSizeType = 0
        self.TempData = []
        self.CancelCount = 0
        self.BackTestData = pd.DataFrame({
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
            "time": []
        })
        self.LastDataRow = {}
        self.MappingLastDataRow = {}
        self.IsLastStatus = {}
        self.TempHistoricalDataCollect = {}
        self.CloseData = {}

    def SendData(self, data: dict):
        reqId = data['reqId']
        symbol = data['symbol']
        if not reqId in self.IsLastStatus:
            self.IsLastStatus[reqId] = False
            self.MappingLastDataRow[symbol] = reqId

        self.TempHistoricalDataCollect[reqId] = {
            "data": {}, "isProcess": False, "isEnd": False}
        self.SocketioDict[reqId] = socketio.Client()
        self.SocketioDict[reqId].on('responseData', self.__on_message)
        self.__Connect(reqId)
        self.__BarSizeType = data['granulariy'][0:10]
        self.__BarSize = int(data.get('barSize'))

        self.__Emit(data, reqId)

    def __Connect(self, reqId):
        # print('__Connect(self):', 'defore')
        self.SocketioDict[reqId].connect(self.__localhost)

    def __Emit(self, data, reqId):
        self.SocketioDict[reqId].emit('getData', {'parameters': data})
        # pass

    def Cancel(self):
        self.__Disconnect()

    def __Disconnect(self, reqId):
        # print('__Disconnect')
        self.SocketioDict[reqId].disconnect()

    def receive_historical(self, reqId, data):
        pass

    def __AddDateTime(self, barSize, barType, timestamp):
        if BarSizeType.H.name == barType:
            return (timestamp + timedelta(hours=barSize))
        elif BarSizeType.M.name == barType:
            return timestamp + timedelta(minutes=barSize)
        elif BarSizeType.S.name == barType:
            return timestamp + timedelta(seconds=barSize)
        elif BarSizeType.D.name == barType:
            return timestamp + timedelta(days=barSize)

    def __Truncate(self, num, n):
        temp = str(num)
        for x in range(len(temp)):
            if temp[x] == '.':
                try:
                    return float(temp[:x+n+1])
                except:
                    return float(temp)
        return float(temp)

    def __transationData(self, allData, barSize, barSizeType):
        # print(allData)
        StartDateTime = allData[0]['timestamp'][0:10]
        EndDateTime = allData[-1]['timestamp'][0:10]
        TempOpenTime = '04:00:00'
        TempCloseTime = '20:00:00'
        DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
        DATE_FORMAT = "%Y-%m-%d"
        NUM = 3
        TempDateTime = datetime.strptime(StartDateTime, DATE_FORMAT)
        # print(TempDateTime, type(TempDateTime))
        DateList = []
        # print(StartDateTime, EndDateTime, TempDateTime, type(TempDateTime))
        while TempDateTime <= datetime.strptime(EndDateTime, DATE_FORMAT):
            DateList.append(TempDateTime.strftime(DATE_FORMAT))
            TempDateTime = self.__AddDateTime(
                1, BarSizeType.D.name, TempDateTime)

        ReceiveData_index = 0
        transationData = []

        for i, _Date in enumerate(DateList):
            # filter holiday data
            if ReceiveData_index == len(allData):
                continue
            if (datetime.strptime(allData[ReceiveData_index]['timestamp'][0:10], DATE_FORMAT) > datetime.strptime(_Date, DATE_FORMAT)):
                continue
            _StartDateTime = _Date+' '+TempOpenTime
            _EndDateTime = datetime.strptime(
                (_Date+' '+TempCloseTime), DATETIME_FORMAT)
            # print(_StartDateTime, _EndDateTime)
            _TempDateTime = datetime.strptime(_StartDateTime, DATETIME_FORMAT)
            while _TempDateTime < _EndDateTime:
                _RangeStartDateTime = _TempDateTime
                _TempDateTime = self.__AddDateTime(
                    barSize, barSizeType, _TempDateTime)
                _RangeEndDateTime = _TempDateTime

                if _TempDateTime > _EndDateTime:
                    _OverDateTime = _TempDateTime-_EndDateTime
                    # print(_OverDateTime)
                    if (i+1) >= len(DateList):
                        continue
                    else:
                        _RangeEndDateTime = datetime.strptime(
                            (DateList[i+1]+' '+TempOpenTime), DATETIME_FORMAT)+_OverDateTime

                _TempReciveData = []
                _ReceiveData_Timestamp = datetime.strptime(
                    allData[ReceiveData_index]['timestamp'], DATETIME_FORMAT)
                # filter First ReceiveData not in range
                if not (_ReceiveData_Timestamp >= _RangeStartDateTime and _ReceiveData_Timestamp <= _RangeEndDateTime):
                    continue

                while True:
                    _ReceiveData_Timestamp = datetime.strptime(
                        allData[ReceiveData_index]['timestamp'], DATETIME_FORMAT)

                    if _RangeStartDateTime <= _ReceiveData_Timestamp and _ReceiveData_Timestamp <= _RangeEndDateTime:
                        _TempReciveData.append(allData[ReceiveData_index])
                        if ReceiveData_index < len(allData)-1:
                            ReceiveData_index = ReceiveData_index+1

                    if _ReceiveData_Timestamp >= _RangeEndDateTime or ReceiveData_index == len(allData)-1:
                        _VolumeSum = 0
                        _TempHigh = -100000
                        _TempLow = 1000000
                        for rowData in _TempReciveData:
                            if float(rowData['low']) < _TempLow:
                                _TempLow = float(rowData['low'])
                            if float(rowData['high']) > _TempHigh:
                                _TempHigh = float(rowData['high'])
                            _VolumeSum = _VolumeSum+int(rowData['volume'])

                        _TransationData = {
                            "open": self.__Truncate(_TempReciveData[0]['open'], NUM),
                            "high": self.__Truncate(_TempHigh, NUM),
                            "low": self.__Truncate(_TempLow, NUM),
                            "close": self.__Truncate(_TempReciveData[-1]['close'], NUM),
                            "volume": _VolumeSum,
                            "time": _RangeEndDateTime.strftime(DATETIME_FORMAT)
                        }
                        transationData.append(_TransationData)
                        break
        return transationData

    def __transationData_D_UP(self, allData, barSize, barSizeType, last):
        if len(self.TempData) != 0:
            allData = self.TempData + allData
            # print('allData',len(allData))

        remainder = (len(allData) % barSize)
        # print('remainder',remainder,len(allData),barSize)
        if remainder == 0:
            remainder_index = 10000000
            self.TempData = []
        else:
            remainder_index = len(allData)-remainder
            # print('remainder_index',remainder_index)

        remainderData = []

        temp_index = 0
        temp_high = -1000000
        temp_low = 10000000
        temp_volume = 0
        openprice = 0
        highprice = 0
        closeprice = 0
        lowprice = 0
        newData = []
        for i in range(0, len(allData), 1):
            data = allData[i]
            if remainder != 0 and i >= remainder_index and (not last):
                remainderData.append(data)
            else:
                # print(last,remainder,remainder_index,i)
                if last and remainder != 0 and i >= remainder_index:
                    continue
                temp_index = temp_index+1
                open = float(data.get('open'))
                high = float(data.get('high'))
                low = float(data.get('low'))
                close = float(data.get('close'))
                volume = int(data.get('volume'))
                timestamp = data.get('timestamp')

                temp_volume = temp_volume+volume
                if high > temp_high:
                    temp_high = high
                if low < temp_low:
                    temp_low = low

                if temp_index == 1:
                    openprice = open

                if temp_index == barSize or i == (len(allData)-1):
                    closeprice = close
                    highprice = temp_high
                    lowprice = temp_low
                    newData.append({
                        'open': openprice,
                        'high': highprice,
                        'low': lowprice,
                        'close': closeprice,
                        'volume': temp_volume,
                        'time': timestamp,
                    })
                    # init
                    temp_index = 0
                    temp_high = -1000000
                    temp_low = 10000000
                    temp_volume = 0
        if len(remainderData) != 0:
            # print('TempData',len(self.TempData))
            self.TempData = remainderData
        return newData

    def __transationDataSort(self, allData):
        newData = []
        for i in range(0, len(allData), 1):
            data = allData[i]
            newData.append({
                'open': float(data.get('open')),
                'high': float(data.get('high')),
                'low': float(data.get('low')),
                'close': float(data.get('close')),
                'volume': int(data.get('volume')),
                'time': data.get('timestamp')
            })
        return newData

    def __check_historical_data(self, data):
        Data = data['data']
        isLast = data['last']
        reqId = data['reqId']
        key = Data["time"][0]
        # print("LV1 __check_historical_data = ", key,self.TempHistoricalDataCollect[reqId]['isProcess'])
        self.TempHistoricalDataCollect[reqId]['data'][key] = {
            'data': Data,
            'isLast': isLast
        }

        while True:
            # print("LV2 while wait", reqId)
            time.sleep(0.1)
            if reqId in self.TempHistoricalDataCollect:
                if self.TempHistoricalDataCollect[reqId]['isEnd']:
                    # print("LV3 last data break")
                    self.TempHistoricalDataCollect.pop(reqId)
                    break

                if len(self.TempHistoricalDataCollect[reqId]['data']) == 0:
                    # print("LV3 range data break")
                    break

                # if not self.__IsHistoricalDataProcess:
                if not self.TempHistoricalDataCollect[reqId]['isProcess']:
                    # print("LV3 not self.__IsSendHistoricalData")
                    self.__send_historical_data(Data, isLast, reqId)
            else:
                break

    def __send_historical_data(self, data, isLast, reqId):
        self.TempHistoricalDataCollect[reqId]['isProcess'] = True
        self.IsLastStatus[reqId] = False
        key = data["time"][0]
        # print("LV4 __send_historical_data start",key,"isLast=",isLast)
        for i in data.index:
            df_value = {"open": [data["open"][i]],
                        "high": [data["high"][i]],
                        "low": [data["low"][i]],
                        "close": [data["close"][i]],
                        "volume": [data["volume"][i]],
                        "time": [data["time"][i]],
                        "last": False
                        }

            df = pd.DataFrame(df_value)
            self.LastDataRow[reqId] = df

            if i == len(data.index)-1:
                # print(f"LV5 TempHistoricalDataCollect={self.TempHistoricalDataCollect}")
                if key in self.TempHistoricalDataCollect[reqId]['data']:
                    self.TempHistoricalDataCollect[reqId]['data'].pop(key)
                    self.TempHistoricalDataCollect[reqId]['isProcess'] = False

                if isLast:
                    # print("LV5 self.IsLastStatus = True")
                    self.IsLastStatus[reqId] = True
                    df_value['last'] = True
                    self.TempHistoricalDataCollect[reqId]['isEnd'] = True

            # print("LV5 __send_historical_data process index=",i,len(data["time"]))
            self.addCloseData(reqId, data["close"][i], data["time"][i])
            self.receive_historical(reqId, df)

    def __on_message(self, data):
        # print('socketio', data)
        trasationData = []

        if data['data'] != None:
            if self.__BarSizeType == BarSizeType.S.name or self.__BarSize == 1:
                trasationData = self.__transationDataSort(data['data'])
            else:
                if (self.__BarSizeType == BarSizeType.D.name or self.__BarSizeType == BarSizeType.W.name or self.__BarSizeType == BarSizeType.MM.name):
                    trasationData = self.__transationData_D_UP(
                        data['data'], self.__BarSize, self.__BarSizeType, data['last'])
                else:
                    trasationData = self.__transationData(
                        data['data'], self.__BarSize, self.__BarSizeType)

        newData = {
            'last': data['last'],
            'data': pd.DataFrame(trasationData),
            'reqId': data['reqId']
        }

        if data['last']:
            self.IsLastStatus[data['reqId']] = True
            print("End of data transfer")
        else:
            # self.IsLastStatus = False
            print("Data transfering...")
        if len(trasationData) != 0:
            self.__check_historical_data(newData)

        if(data['status'] == False):
            self.__Disconnect(data['reqId'])

    def addCloseData(self, symbol, price, time):
        if not symbol in self.CloseData:
            self.CloseData[symbol] = {}

        self.CloseData[symbol][self.getDate(time)] = price

    def getDate(self, datatime):
        # 解析日期時間字串
        datetime_obj = datetime.strptime(datatime, "%Y-%m-%d %H:%M:%S")

        # 提取日期部分並轉換為字串
        return datetime_obj.strftime("%Y-%m-%d")


class ib(ibWrapper, ibClinet, Auth, Hsocket):

    def __init__(self) -> None:
        super(ib, self).__init__()
        Hsocket.__init__(self)
        Auth.__init__(self)
        self.Report = Report()
        ibWrapper.__init__(self)
        ibClinet.__init__(self, wrapper=self)
        self.MarketDatas = {}
        self.permId2ord = {}
        self.openOrderDatas = {}
        self.orderStatusDatas = {}
        self.__broker = 'ib'
        self.__statusData = {}
        self.__beta_toggle = False
        self.__market_barsize = 0
        self.__marketBarDatas = []
        self.__marketData_reqId = {}
        self.__marketData_FirstTime = {}
        self.__FORMART_DATETIME = "%Y/%m/%d-%H:%M:%S"
        self.__connect_error_count = 0
        self.BackTestToggle = False
        self.BackTestBalance = 100000
        self.BT_Portfolio = {}
        self.BT_ReqId = 0
        self.ClientId = None
        self.Port = None
        self.IP = None
        self.__IsConnectBroker = False
        self.NextValidId = -99

    def receiveFA(self, faData, cxml: str):
        self.addNextValidId()
        self.replaceFA(self.NextValidId,faData,cxml)
        time.sleep(3)
        print("Set up FA account")

    def setFA(self, faType):
        self.requestFA(faType)

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        super().accountSummary(reqId, account, tag, value, currency)
        # print('call accountSummary:', 'reqId', reqId, 'account',
        #       account, 'tag', tag, 'value', value, 'currency', currency)

        data = {
            'reqId': reqId,
            'account': account,
            'tag': tag,
            'value': value,
            'currency': currency
        }
        self.receive_accounts_all(data)

    def receive_accounts_all(self, data):
        pass

    def updatePortfolio(self, contract: Contract, position: float, marketPrice: float, marketValue: float, averageCost: float, unrealizedPNL: float, realizedPNL: float, accountName: str):
        # print('call_updatePortfolio:', 'contract', contract, 'position', position, 'marketPrice', marketPrice, 'marketValue', marketValue,
        #       'averageCost', averageCost, 'unrealizedPNL', unrealizedPNL, 'realizedPNL', realizedPNL, 'accountName', accountName)

        data = {
            # 'contract': contract,
            'symbol': contract.localSymbol,
            'secType': contract.secType,
            'exchange': contract.primaryExchange,
            'currency': contract.currency,

            'position': position,
            'marketPrice': marketPrice,
            'marketValue': marketValue,
            'averageCost': averageCost,
            'unrealizedPNL': unrealizedPNL,
            'realizedPNL': realizedPNL,
            'accountName': accountName
        }
        self.receive_portfolo(data)

    def receive_portfolo(self, data):
        pass

    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str):
        # print('call_updateAccountValue:', 'key', key, 'val', val,
        #       'currency', currency, 'accountName', accountName)

        data = {
            'key': key,
            'val': val,
            'currency': currency,
            'accountName': accountName
        }
        self.receive_accounts(data)

    def receive_accounts(self, data):
        pass

    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.nextValidOrderId = orderId
        self.NextValidId = orderId
        print("NextValidId:", orderId)
        return orderId

    def addNextValidId(self):
        self.NextValidId += 1

        if not self.BackTestToggle:
            self.__check_all()
            self.nextValidId(self.NextValidId)

        return self.NextValidId

    def openOrder(self, orderId: int, contract: Contract, order: Order, orderState: OrderState):
        # print(orderId, contract, order, orderState)
        super().openOrder(orderId, contract, order, orderState)
        data = {
            'permId': order.permId,
            'clientId': order.clientId,
            'orderId': orderId,
            'account': order.account,
            'symbol': contract.symbol,
            'secType': contract.secType,
            'exchange': contract.exchange,
            'action': order.action,
            'orderType': order.orderType,
            'totalQty': order.totalQuantity,
            'cashQty': order.cashQty,
            'lmtPrice': order.lmtPrice,
            'auxPrice': order.auxPrice,
            'status': orderState.status
        }
        # print('ib_openOrder')
        self.receive_openOrder(data)

    def receive_openOrder(self, data):
        pass

    def orderStatus(self, orderId: int, status: str, filled: float,
                    remaining: float, avgFillPrice: float, permId: int,
                    parentId: int, lastFillPrice: float, clientId: int,
                    whyHeld: str, mktCapPrice: float):
        super().orderStatus(orderId, status, filled, remaining,
                            avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)
        # print("OrderStatus. Id:", orderId,
        #       "Status:", status,
        #       "Filled:", str(filled),
        #       "Remaining:", str(remaining),
        #       "AvgFillPrice:", str(avgFillPrice),
        #       "PermId:", str(permId),
        #       "ParentId:", str(parentId),
        #       "LastFillPrice:", str(lastFillPrice),
        #       "ClientId:", str(clientId),
        #       "WhyHeld:", whyHeld,
        #       "MktCapPrice:", str(mktCapPrice))

        data = {
            'orderId': orderId,
            'status': status,
            'filled': filled,
            'remaining': remaining,
            'avgFillPrice': avgFillPrice,
            'permId': permId,
            'parentId': parentId,
            'lastFillPrice': lastFillPrice,
            'clientId': clientId,
            'whyHeld': whyHeld,
            'mktCapPrice': mktCapPrice
        }
        self.orderStatusDatas[orderId] = data
        self.__process_order_status(data)
        self.receive_orderStatus(data)

    def receive_orderStatus(self, data):
        pass

    def __getFirstTimeSplite(self, spanTime, barType, barSize):
        DATE_FORMAT = "%Y/%m/%d"
        startDate = datetime.strptime(spanTime.split('-')[0], DATE_FORMAT)
        tempDate = startDate
        endDate = startDate+timedelta(days=+1)
        while tempDate < endDate:
            if barType == BarSizeType.S.value:
                tempDate = tempDate+timedelta(seconds=+barSize)
            elif barType == BarSizeType.M.value:
                tempDate = tempDate+timedelta(minutes=+barSize)
            elif barType == BarSizeType.H.value:
                tempDate = tempDate+timedelta(hours=+barSize)
            elif barType == BarSizeType.D.value:
                tempDate = tempDate+timedelta(days=+barSize)

            if tempDate > datetime.strptime(spanTime, self.__FORMART_DATETIME):
                break
        # print(tempDate)
        return tempDate

    def realtimeBar(self, reqId: int, time: int, open_: float, high: float, low: float, close: float, volume: int, wap: int, count: int):
        super().realtimeBar(reqId, time, open_, high, low, close, volume, wap, count)
        # print(reqId, time, open_, high, low, close, volume, wap, count)
        strTime = datetime.fromtimestamp(
            time).strftime(self.__FORMART_DATETIME)
        print('receive 5 sec data...')
        barSize = self.__market_barsize.split(' ')
        barSizeType = barSize[1]
        barSizeValue = int(barSize[0])
        firstBarComplete = self.__marketData_reqId[str(reqId)]
        if not firstBarComplete:
            self.__marketData_FirstTime = self.__getFirstTimeSplite(
                strTime, barSizeType, barSizeValue)
            self.__marketData_reqId[str(reqId)] = True

        data = {
            'reqId': reqId,
            'time': strTime,
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'wap': wap,
            'count': count,
        }

        sec5Number = 1
        if BarSizeType.S.value == barSizeType:
            sec5Number = barSizeValue/5
        elif BarSizeType.M.value == barSizeType:
            sec5Number = 12*barSizeValue
        elif BarSizeType.H.value == barSizeType:
            sec5Number = 12*60*barSizeValue
        # elif BarSizeType.D.value == barSizeType:
        #     sec5Number = 12*60*barSizeValue
        # elif BarSizeType.W.value == barSizeType:
        #     sec5Number = 12*barSizeValue
        # elif BarSizeType.MM.value == barSizeType:
        #     sec5Number = 12*barSizeValue

        if (barSizeType != BarSizeType.S.value) or ((barSizeType == BarSizeType.S.value) and barSizeValue > 5):
            self.__marketBarDatas.append(data)

        if len(self.__marketBarDatas) == sec5Number or self.__marketData_FirstTime == strTime:
            _tmpHigh = -1000
            _tmpLow = 1000
            _tmpVolume = 0
            _tmpCount = 0
            _tmpWap = 0
            for element in self.__marketBarDatas:
                if element['high'] > _tmpHigh:
                    _tmpHigh = element['high']
                if element['low'] < _tmpLow:
                    _tmpLow = element['low']
                _tmpVolume = _tmpVolume + element['volume']
                _tmpCount = _tmpCount + element['count']
                _tmpWap = _tmpWap + element['wap']
            _tmpWap = _tmpWap/len(self.__marketBarDatas)
            data = {
                'reqId': reqId,
                'time': self.__marketBarDatas[0]['time'],
                'open': self.__marketBarDatas[0]['open'],
                'high': _tmpHigh,
                'low': _tmpLow,
                'close': self.__marketBarDatas[0]['close'],
                'volume': _tmpVolume,
                'wap': _tmpWap,
                'count': _tmpCount,
            }
            # self.MarketDatas[reqId] = data
            self.__marketBarDatas = []
            self.receive_markets(reqId, pd.DataFrame([data]))
        else:
            self.receive_markets(reqId, pd.DataFrame([data]))

    def receive_markets(self, reqId, data):
        pass

    def ReqRealTimeBars(self, reqId, contract, requestParams):
        whatToShow = "MIDPOINT"
        barSize = 5

        if requestParams.get('whatToShow') != None:
            whatToShow = requestParams.get('whatToShow')

        useRTH = True
        if requestParams.get('useRTH') != None:
            useRTH = bool(requestParams.get('useRTH'))

        self.reqRealTimeBars(reqId, contract, barSize, whatToShow, useRTH, [])

    def cancel_markets(self, reqId):
        result = Result()
        strspan = 'send the cancel_markets'

        try:
            self.__check_all()
            self.cancelRealTimeBars(reqId)
            result.true(strspan)
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            result.false(f"{strspan} error: {ex}")

        return result

    def signout(self):
        result = Result()
        strspan = 'Connect sign out'

        try:
            self.__check_all()
            self.disconnect()
            self.__IsConnectBroker = False
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            result.false(f"{strspan} error: {ex}")

        return result

    def __Connenct(self):
        # print("Fun", "__Connenct")
        try:
            if not self.__IsConnectBroker:
                # print(self.IP, self.Port, self.ClientId)
                self.connect(self.IP, self.Port, self.ClientId)
                thread = Thread(target=self.run, daemon=True)
                thread.start()

                setattr(self, "_thread", thread)

                self.init_error()

                temp_sec = 0
                stop_sec = 10
                while True:
                    # if isinstance(self.NextValidId, int):
                    if self.NextValidId != -99:
                        print('Successful connection to Interactive Brokers.')
                        self.__IsConnectBroker = True
                        break
                    else:
                        temp_sec = temp_sec+1
                        time.sleep(1)
                        print(
                            "Please wait to connection to the Interactive Brokers software...")

                    if temp_sec > stop_sec:
                        print("timeout")
                        break
        except Exception as ex:
            print("Unsuccessful connection to Interactive Broker.")

    def __IsConnect(self):
        # print("Fun","__IsConnect")
        result = Result()
        strspan = 'Connect to Interactive Brokers'

        try:
            try:
                if not self.__IsConnectBroker:
                    # print(self.IP, self.Port, self.ClientId)
                    self.connect(self.IP, self.Port, self.ClientId)
                    thread = Thread(target=self.run, daemon=True)
                    thread.start()

                    setattr(self, "_thread", thread)

                    self.init_error()

                    self.__connect_error_count = 0

                    while True:
                        # if isinstance(self.NextValidId, int):
                        if self.NextValidId != -99:
                            print('Successful connection to Interactive Brokers')
                            self.__IsConnectBroker = True
                            result.true(strspan)
                            break
                        else:
                            time.sleep(1)
                            print(
                                "Please wait to connection to the Interactive Brokers software...")

            except Exception as ex:
                self.__connect_error_count = self.__connect_error_count+1
                raise ValueError("ib connent fail")
        except Exception as ex:
            if str(ex) == ("ib connent fail"):
                if self.__connect_error_count >= 3:
                    print(
                        f"Error connecting to Interactive Brokers at IP address {str(self.IP)}, port {str(self.Port)} with client ID {str(self.ClientId)}. Please verify that your settings are correct. ")
                    sys.exit(0)
                else:
                    Key = input(
                        f"Error connecting to Interactive Brokers at IP address {str(self.IP)}, port {str(self.Port)} with client ID {str(self.ClientId)}. Please check that the settings are correct, and that either IB Trader Workstation or IB Gateway is running. Press Enter to try again, or type *Q* to quit : ")
                    if str(Key) == ('Q') or str(Key) == ('q'):
                        sys.exit(0)
                    else:
                        self.__is_connect()
            else:
                print(f"{strspan} error: {ex}")
                result.false(f"{strspan} error: {ex}")
        return result

    def sign(self, settingParams):
        result = Result()
        strspan = 'Connect sign in'
        # print(strspan)

        try:
            try:
                self.sign_in(settingParams['token'], self.__broker)
                self.check_status()
                if not "ip" in settingParams:
                    raise ValueError(
                        "The ip key doesn't exist in the dictionary")
                if not "port" in settingParams:
                    raise ValueError(
                        "The port key doesn't exist in the dictionary")
                if not "clientId" in settingParams:
                    raise ValueError(
                        "The clientId key doesn't exist in the dictionary")
                self.IP = settingParams['ip']
                self.Port = int(settingParams['port'])
                self.ClientId = int(settingParams['clientId'])
                self.__Connenct()
            except Exception as ex:
                # print("ex", ex)
                raise ValueError(ex)
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            result.false(f"{strspan} error: {ex}")
        return result

    def fetch_account_all(self, reqId):
        result = Result()
        strspan = 'send the fetch_account_all'
        try:
            self.__check_all()
            # tag GrossPositionValue、AvailableFunds、NetLiquidation
            self.reqAccountSummary(reqId, "All", '$LEDGER:ALL')
            result.true(strspan)
        except Exception as ex:
            print('send the fetch_account error:', ex)
            result.false(f"{strspan} error: {ex}")
        return result

    def __process_order_status(self, data):
        key = data['permId']
        if len(self.__statusData) >= 1000:
            self.__statusData.popitem()

        if not key in self.__statusData:
            self.__statusData[key] = data
            postData = {
                'brokerOrderId': data['orderId'],
                'price': data['avgFillPrice'],
                'totalQuantity': data['filled'],
                'transmitType': 'deal',
            }
            self.post_order_data(postData)

    def __post_order_data(self, reqId, contract, order):
        # print('process:', '__post_order_data')
        data = self.__process_order_data(reqId, contract, order)
        data['transmitType'] = 'create'
        self.post_order_data(data)

    def __process_order_data(self, reqId, contract, order):
        # print('process:', '__process_order_data')
        data = {
            'brokerOrderId': reqId,
            'symbol': contract.get('symbol'),
            'secType': contract.get('secType'),
            'currency': contract.get('currency'),
            'action': 'buy' if order.get('action') == 'BUY' else 'sell',
            'totalQuantity': order.get('totalQuantity'),
            'orderType': 'limit' if order.get('orderType') == 'LMT' else 'market',
            'price': order.get('lmtPrice')
            # 'transmit': False
        }
        return data

    def __generate_report(self, data):
        time_list = data.get('time')
        time_list = pd.to_datetime(pd.Series(time_list))
        profit_list = data.get('profit')
        stock_return = pd.Series(profit_list, index=time_list).sort_index()
        current_datetime = datetime.now()

        current_date_time = current_datetime.strftime("%Y%m%d%H%M%S")
        filename = current_date_time+'.html'
        if "title" in data:
            qs.reports.html(stock_return, download_filename=filename,
                            title=data.get('title'), output=True)
        else:
            qs.reports.html(
                stock_return, download_filename=filename, output=True)

        time.sleep(2)

        remove_text = 'http://quantstats.io'
        replace_text = 'https://www.dojotest.com/'

        with open(filename, 'r') as file:
            file_content = file.read()

        new_content = file_content.replace(remove_text, replace_text)
        new_content = new_content.replace('QuantStats', 'dojotest')
        new_content = new_content.replace('(v. 0.0.59)', '')

        with open(filename, 'w') as file:
            file.write(new_content)

        print("Ended, the report was successfully generated")

    def generate_report(self, title):
        isGenerate = True
        for isLastStatus in self.IsLastStatus:
            if not isLastStatus:
                isGenerate = False

        if isGenerate:
            data = self.__BT_calculate_portfolio()
            if len(data.get('profit')) > 1:
                self.Report.TitleName = title
                self.Report.BackTestBalance = self.BackTestBalance
                self.Report.generate_report()

    def update_market_price(self):
        if self.BackTestToggle:
            self.__BT_limit_order_process()
            allDone = True
            # print(f"self.IsLastStatus:{self.IsLastStatus}")
            for value in self.IsLastStatus.values():
                # print(f"value:{value}")
                if not value:
                    allDone = False
            return allDone
        else:
            pass

    def __BT_limit_order_process(self):
        for reqId in self.BT_Portfolio.keys():
            market_price = self.LastDataRow[reqId].close.iloc[-1]

            for index, order in enumerate(self.BT_Portfolio[reqId]):
                orderType = order.get('orderType')
                status = order.get('status')
                if (not orderType == 'MKT') and (not status):
                    lmtPrice = order['lmtPrice']
                    action = order['action']
                    if action == 'BUY' and lmtPrice <= market_price:
                        self.BT_Portfolio[reqId][index]['dealPrice'] = market_price
                        # print("action == 'BUY' and lmtPrice <= market_price")
                    if action == 'SELL' and lmtPrice >= market_price:
                        self.BT_Portfolio[reqId][index]['dealPrice'] = market_price
                        # print("action == 'SELL' and lmtPrice >= market_price")

    def __BT_create_order(self, reqId, contract, order):
        action = order.get('action')
        totalQuantity = order.get('totalQuantity')
        orderType = order.get('orderType')
        symbol = contract.get('symbol')

        symbol_reqId = self.MappingLastDataRow[symbol]
        market_price = self.LastDataRow[symbol_reqId].close.iloc[-1]
        time = self.LastDataRow[symbol_reqId].time.iloc[-1]

        portfolio_value = {
            'symbol': symbol,
            'action': action,
            'totalQuantity': totalQuantity,
            'orderType': orderType,
            'time': time
        }

        if orderType == 'MKT':
            portfolio_value['dealPrice'] = market_price
            portfolio_value['status'] = True
        else:
            lmtPrice = order.get('lmtPrice')
            portfolio_value['lmtPrice'] = lmtPrice
            portfolio_value['status'] = False

        if not symbol_reqId in self.BT_Portfolio:
            self.BT_Portfolio[symbol_reqId] = []
        # print(f"portfolio_value:{portfolio_value}")
        self.BT_Portfolio[symbol_reqId].append(portfolio_value)
        data = {
            'orderId': reqId,
            'status': "Filled",
            'filled': totalQuantity,
            'remaining': 0,
            'avgFillPrice': market_price,
            'permId': 0,
            'parentId': 0,
            'lastFillPrice': market_price,
            'clientId': 0,
            'whyHeld': 0,
            'mktCapPrice': market_price
        }
        self.receive_orderStatus(data)

        self.__BT_limit_order_process()

    def __BT_calculate_portfolio(self):
        self.Report.initPortfolioData()
        # print(f"self.BT_Portfolio:{self.BT_Portfolio}")
        for reqId in self.BT_Portfolio.keys():
            for portfolio_index, portfolio_value in enumerate(self.BT_Portfolio[reqId]):
                action = portfolio_value.get('action')
                totalQuantity = portfolio_value.get('totalQuantity')
                price = portfolio_value.get('dealPrice')
                time = portfolio_value.get('time')
                symbol = portfolio_value.get('symbol')
                portfolio_value = {
                    'symbol': reqId,
                    'action': action,
                    'totalQuantity': totalQuantity,
                    'time': time,
                    'dealPrice': price
                }
                self.Report.addPortfolioData(portfolio_value)

        self.Report.CloseData = self.CloseData
        # print(f"self.CloseData:{self.Report.CloseData}")
        # print(f"self.Report:{self.Report.Portfolio}")
        data = self.Report.calculate_portfolio()

        receive_portfolo_data = {
            # 'symbol': 'AAPL',
            # 'secType': 'STK',
            # 'exchange': 'NASDAQ',
            # 'currency': 'USD',
            # 'position': -10000.0,
            # 'marketPrice': 174.8500061,
            # 'marketValue': -1748500.06,
            # 'averageCost': 177.67396385,
            # 'unrealizedPNL': temp_balance,
            'realizedPNL': data.get('temp_balance')
            # 'accountName': 'DU2878211'
        }

        receive_portfolo = {
            "balance": data.get('temp_balance'),
            "time": data.get('time'),
            "profit": data.get('profit'),
            "receive_portfolo_data": receive_portfolo_data
        }
        return receive_portfolo

    def create_order(self, reqId, contractParams, orderParams):
        result = Result()
        strspan = 'send the create_order'

        # try:
        self.__check_all()
        if self.BackTestToggle:
            self.__BT_create_order(reqId, contractParams, orderParams)
        else:
            # Contract
            contract = Contract()

            for key in contractParams:
                if hasattr(contract, key):
                    setattr(contract, key, contractParams[key])
                else:
                    raise ValueError(
                        'The contract attribute not exist!! key:{key}'.format(key=key))
            # Order
            if "algorithms" in orderParams:
                algorithmsParams = orderParams['algorithms']
                del orderParams['algorithms']

            order = Order()

            for key in orderParams:
                if hasattr(order, key):
                    setattr(order, key, orderParams[key])
                else:
                    raise ValueError(
                        'The order attribute not exist!! key:{key}'.format(key=key))
            if 'algorithmsParams' in locals():
                if algorithmsParams.get('type') == 'ALGO':
                    self.FillAdaptiveParams(
                        order, algorithmsParams.get('priority'))
                elif algorithmsParams.get('type') == 'MIDPRICE':
                    order.orderType = 'MIDPRICE'
                elif algorithmsParams.get('type') == 'TWAP':
                    self.FillTwapParams(order,
                                        algorithmsParams.get(
                                            'strategyType'),
                                        algorithmsParams.get('startTime'),
                                        algorithmsParams.get('endTime'),
                                        algorithmsParams.get(
                                            'allowPastEndTime'),
                                        algorithmsParams.get(
                                            'monetaryValue')
                                        )
                elif algorithmsParams.get('type') == 'VWAP':
                    self.FillVwapParams(order,
                                        algorithmsParams.get('maxPctVol'),
                                        algorithmsParams.get('startTime'),
                                        algorithmsParams.get('endTime'),
                                        algorithmsParams.get(
                                            'allowPastEndTime'),
                                        algorithmsParams.get('noTakeLiq')
                                        )

            ib_return = self.placeOrder(reqId, contract, order)

            self.__post_order_data(reqId, contractParams, orderParams)
        result.true(strspan)
        # except Exception as ex:
        #     print('create_order error', ex)
        #     result.false(f"{strspan} error: {ex}")

        return result

    def cancel_order(self, orderId):
        try:
            self.__check_all()
            self.cancelOrder(orderId)
            data = {
                "brokerOrderId": orderId,
                "transmitType": 'cancel'

            }
            self.post_order_data(data)
        except Exception as ex:
            print('cancel_order error :', ex)

    def __IsMatch(self, patten, content):
        pattern = re.match(patten, content)
        if pattern != None:
            return True
        else:
            return False

    def __check_barSize(self, requestParams):

        barSize = requestParams.get('barSize')
        # print(barSize)
        if not self.__IsMatch(r'\d+ \D', barSize):
            raise ValueError('barSize value format is wrong!!')

        if not barSize.split(' ')[1] in BarSizeType._value2member_map_:
            raise ValueError('barType value format is wrong!!')

        barSize = requestParams.get('barSize').split(' ')
        barSizeType = barSize[1]
        barSizeValue = barSize[0]
        valueList_sec = ['5', '10', '15', '30']
        valueList_min = ['1', '2', '3', '5', '10', '15', '20', '30']
        valueList_hour = ['1', '2', '3', '4', '8']
        valueList_day = ['1']
        valueList_week = ['1']
        valueList_month = ['1']

        if (barSizeType == BarSizeType.S.value) and (not barSizeValue in valueList_sec):
            raise ValueError("barSize only supports 5,10,15,30 sec")
        if (barSizeType == BarSizeType.M.value) and (not barSizeValue in valueList_min):
            raise ValueError("barSize only supports 1,2,3,5,10,15,20,30 min")
        if (barSizeType == BarSizeType.H.value) and (not barSizeValue in valueList_hour):
            raise ValueError("barSize only supports 1,2,3,4,8 hour")
        if (barSizeType == BarSizeType.D.value) and (not barSizeValue in valueList_day):
            raise ValueError("barSize only supports 1 day")
        if (barSizeType == BarSizeType.W.value) and (not barSizeValue in valueList_week):
            raise ValueError("barSize only supports 1 week")
        if (barSizeType == BarSizeType.W.value) and (not barSizeValue in valueList_month):
            raise ValueError("barSize only supports 1 month")

    def __check_requestParams(self, requestParams):
        # print(requestParams)
        _RequestParams = RequestParams()
        for key in requestParams:
            if not hasattr(_RequestParams, key):
                raise ValueError(
                    'The requestParams attribute not exist!! key:{key}'.format(key=key))

        for key in _RequestParams.__dict__:
            if not key in requestParams:
                raise ValueError(
                    'The requestParams missing required arguments!! key:{key}'.format(key=key))

        endDateTime = requestParams['endDateTime']
        startDateTime = requestParams['startDateTime']
        DateFormat = r'\d\d\d\d-\d\d-\d\d'

        if not self.__IsMatch(DateFormat, endDateTime):
            raise ValueError('endDateTime value format is wrong!!')

        if not self.__IsMatch(DateFormat, startDateTime):
            raise ValueError('startDateTime value format is wrong!!')

        if datetime.strptime(startDateTime, "%Y-%m-%d") > datetime.strptime(endDateTime, "%Y-%m-%d"):
            raise ValueError(
                'StartDateTime cannot be greater than endDateTime!!')

    def __check_request_limit(self):
        result = False
        limit_thread = self.requestCount
        thread_count = len(self.TempHistoricalDataCollect)
        if thread_count >= limit_thread:
            result = True
        return result

    def fetch_history(self, reqId, contractParams, requestParams):
        print('Start of data transfer, Please wait...')
        result = Result()
        strspan = 'send the fetch_history'
        # print(strspan)
        try:
            if self.__check_request_limit():
                print("The number of data retrievals has exceeded the limit. Please log in to your dojotest account and upgrade your data subscription to continue accessing data. https://www.dojotest.com/login")
                pass

            self.__check_requestParams(requestParams)
            customerData = self.check_status()
            self.check_symbol(contractParams.get('symbol'))
            self.__check_barSize(requestParams)

            process_data = self.process_history(contractParams, requestParams)
            parameters = {
                'startDate': process_data.get('startDateTime'),
                'endDate': process_data.get('endDateTime'),
                'symbol': process_data.get('symbol'),
                'barSize': process_data.get('barSize'),
                'granulariy': process_data.get('barSizeType'),
                'reqId': reqId
            }
            process_data['reqId'] = reqId
            parameters['customerData'] = customerData
            # print('self.SendData(parameters)', 'before')
            self.SendData(parameters)
            self.post_historydata(process_data)
            result.true(strspan)
        except Exception as err:
            print(f"{strspan} error: {err}")
            result.false(f"{strspan} error: {err}")

        return result

    def fetch_markets(self, reqId, contractParams, requestParams):
        strspan = 'send the fetch_markets'
        # print(strspan)
        isBarDataExist = True
        breakCount = 0
        stopWaitCount = 100 * 10  # sec
        try:
            self.__check_all()
            self.__check_barSize(requestParams)
            contract = Contract()
            for key in contractParams:
                if hasattr(contract, key):
                    setattr(contract, key, contractParams[key])
                else:
                    raise ValueError(
                        'The contract attribute not exist!! key:{key}'.format(key=key))
            self.__market_barsize = requestParams.get('barSize')
            self.ReqRealTimeBars(reqId, contract, requestParams)
            self.process_market(contractParams, requestParams)
            self.__marketData_reqId[str(reqId)] = False
            # while isBarDataExist:
            #     time.sleep(0.01)
            #     breakCount += 1

            #     if breakCount >= stopWaitCount:
            #         break

            #     if len(self.MarketDatas) > 0:
            #         if reqId in self.MarketDatas:
            #             isBarDataExist = False

            if breakCount >= stopWaitCount:
                raise Exception('fetch_markets not response')
            # result.true(strspan)
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            # result.false(f"{strspan} error: {ex}")

        return self.MarketDatas

    def cancel_account_all(self, reqId):
        result = Result()
        strspan = 'send the cancel_account'

        try:
            self.__check_all()
            self.cancelAccountSummary(reqId)
            result.true(strspan)
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            result.false(f"{strspan} error: {ex}")

        return result

    def fetch_portfolio(self, acctCode: str):
        result = Result()
        strspan = 'send the fetch_account'

        try:
            self.__check_all()
            if self.BackTestToggle:
                data = self.__BT_calculate_portfolio()
                self.receive_portfolo(data.get("receive_portfolo_data"))
            else:
                self.reqAccountUpdates(True, acctCode)
                result.true(strspan)
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            result.false(f"{strspan} error: {ex}")

        return result

    def cancel_portfolio(self, acctCode: str):
        result = Result()
        strspan = 'send the cancel_account'

        try:
            self.__check_all()
            self.reqAccountUpdates(False, acctCode)
            result.true(strspan)
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            result.false(f"{strspan} error: {ex}")

        return result

    def __check_all(self):
        # print("Fun","__check_all")
        self.check_status()
        # self.check_bata()
        if not self.BackTestToggle:
            self.__IsConnect()
