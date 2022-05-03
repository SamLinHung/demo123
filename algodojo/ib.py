from datetime import datetime
from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.contract import Contract
from threading import Thread
import queue
from ibapi.order import *
from ibapi.order_state import *
from algodojo.base.auth import Auth


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


class ibAuth(Auth):
    def __init__(self) -> None:
        super().__init__()


class ib(ibWrapper, ibClinet, Auth):

    def __init__(self) -> None:
        Auth.__init__(self)
        ibWrapper.__init__(self)
        ibClinet.__init__(self, wrapper=self)
        self.MarketDatas = {}
        self.permId2ord = {}
        self.NextValidId = 0
        self.openOrderDatas = {}
        self.orderStatusDatas = {}

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        # super().historicalDataEnd(reqId, start, end)
        # print('call historicalDataEnd: ', 'reqId',
        #       reqId, 'start', start, 'end', end)
        data = {
            'reqId': reqId,
            'start': start,
            'end': end
        }
        self.receive_historical_end(data)

    def receive_historical_end(self, data):
        pass

    def historicalData(self, reqId: int, bar):
        # print('call historicalData: ', 'reqId', reqId, 'bar', bar)
        self.receive_historical(bar.__dict__)

    def receive_historical(self, data):
        pass

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
        self.receive_orderStatus(data)

    def receive_orderStatus(self, data):
        pass

    def realtimeBar(self, reqId: int, time: int, open_: float, high: float, low: float, close: float, volume: int, wap: int, count: int):
        super().realtimeBar(reqId, time, open_, high, low, close, volume, wap, count)
        data = {
            'reqId': reqId,
            'time': datetime.fromtimestamp(time).strftime("%Y/%m/%d-%H:%M:%S"),
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'wap': wap,
            'count': count,
        }
        self.MarketDatas[reqId] = data
        self.receive_markets(data)

    def receive_markets(self, data):
        pass

    def ReqRealTimeBars(self, reqId, contract, barSize):
        self.reqRealTimeBars(reqId, contract, barSize, "MIDPOINT", True, [])

    def cancel_markets(self, reqId):
        result = Result()
        strspan = 'send the cancel_markets'

        try:
            self.check_status()
            self.cancelRealTimeBars(reqId)
            result.true(strspan)
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            result.false(f"{strspan} error: {ex}")

        return result

    def signout(self):
        self.disconnect()

    def sign(self, settingParams):
        result = Result()
        strspan = 'Connect sign in'

        try:
            self.sign_in(settingParams['token'])
            self.check_status()

            self.connect(settingParams['ip'], int(
                settingParams['port']), int(settingParams['clientId']))

            thread = Thread(target=self.run)
            thread.start()

            setattr(self, "_thread", thread)

            self.init_error()
            result.true(strspan)
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            result.false(f"{strspan} error: {ex}")
        return result

    def fetch_account_all(self, reqId):
        result = Result()
        strspan = 'send the fetch_account_all'
        try:
            self.check_status()
            # tag GrossPositionValue、AvailableFunds、NetLiquidation
            self.reqAccountSummary(reqId, "All", '$LEDGER:ALL')
            result.true(strspan)
        except Exception as ex:
            print('send the fetch_account error:', ex)
            result.false(f"{strspan} error: {ex}")
        return result

    def create_order(self, reqId, contractParams, orderParams):
        result = Result()
        strspan = 'send the create_order'

        try:
            self.check_status()
            contract = Contract()

            for key in contractParams:
                if hasattr(contract, key):
                    setattr(contract, key, contractParams[key])
                else:
                    raise ValueError(
                        'The contract attribute not exist!! key:{key}'.format(key=key))

            order = Order()

            for key in orderParams:
                if hasattr(order, key):
                    setattr(order, key, orderParams[key])
                else:
                    raise ValueError(
                        'The order attribute not exist!! key:{key}'.format(key=key))

            self.placeOrder(reqId, contract, order)
            result.true(strspan)
        except Exception as ex:
            print('create_order error', ex)
            result.false(f"{strspan} error: {ex}")

        return result

    def cancel_order(self, orderId):
        try:
            self.check_status()
            self.cancelOrder(orderId)
        except Exception as ex:
            print('cancel_order error :', ex)

    def fetch_history(self, reqId, contractParams, requestParams):
        result = Result()
        strspan = 'send the fetch_history'

        try:
            self.check_status()
            self.check_symbol(contractParams.get('symbol'))
            
            contract = Contract()

            for key in contractParams:
                if hasattr(contract, key):
                    setattr(contract, key, contractParams[key])
                else:
                    raise ValueError(
                        'The contract attribute not exist!! key:{key}'.format(key=key))

            self.reqHistoricalData(reqId,
                                   contract,
                                   requestParams.get('endDateTime'),
                                   requestParams.get('durationType'),
                                   requestParams.get('barSize'),
                                   requestParams.get('dataType'),
                                   1,
                                   1,
                                   False,
                                   [])
            result.true(strspan)
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            result.false(f"{strspan} error: {ex}")

        return result

    def fetch_markets(self, reqId, contractParams, barSize):
        strspan = 'send the create_order'
        # print(strspan)
        isBarDataExist = True
        breakCount = 0
        stopWaitCount = 100 * 10  # sec

        try:
            self.check_status()
            contract = Contract()

            for key in contractParams:
                if hasattr(contract, key):
                    setattr(contract, key, contractParams[key])
                else:
                    raise ValueError(
                        'The contract attribute not exist!! key:{key}'.format(key=key))

            self.ReqRealTimeBars(reqId, contract, barSize)

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
            self.check_status()
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
            self.check_status()
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
            self.check_status()
            self.reqAccountUpdates(False, acctCode)
            result.true(strspan)
        except Exception as ex:
            print(f"{strspan} error: {ex}")
            result.false(f"{strspan} error: {ex}")

        return result
