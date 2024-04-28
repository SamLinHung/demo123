import pandas as pd
import quantstats as qs
import time
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('SVG')

class Report():
    def __init__(self) -> None:
        self.BackTestBalance = 100000
        self.Portfolio = []
        self.Report_time_list = []
        self.Report_profit_list = []
        self.BalanceDict = {}
        self.CloseData = {}

    def calculate_portfolio(self):
        PortfolioDict = {}

        # print(f"CloseData:{self.CloseData}")
        for portfolio_index, portfolio_value in enumerate(self.Portfolio):
            _action = portfolio_value.get('action')
            _totalQuantity = portfolio_value.get('totalQuantity')
            _price = portfolio_value.get('dealPrice')
            _time = portfolio_value.get('time')
            _symbol = portfolio_value.get('symbol')
            # print(f"--time = {_time}")

            if not _symbol in PortfolioDict:
                PortfolioDict[_symbol] = {
                    'totalQuantity': 0,
                    'action': None,
                    'price': None,
                    'lastDate': None,
                    'tempProfit': 0
                }

                self.BalanceDict[_symbol] = {
                    self.getDate(_time): {
                        'profit': 0,
                        'float': 0
                    }
                }

            if PortfolioDict[_symbol]['totalQuantity'] == 0:
                # PortfolioDict[symbol]['lastDate'] 小於 time 且不等於 time
                if PortfolioDict[_symbol]['tempProfit'] != 0:
                    while (self.thanDate(_time, PortfolioDict[_symbol]['lastDate']) and not self.equalDate(_time, PortfolioDict[_symbol]['lastDate'])):
                        # print(f"time:{_time}, PortfolioDict[{_symbol}]['lastDate']:{PortfolioDict[_symbol]['lastDate']}")

                        _settleDate = self.getDate(
                            PortfolioDict[_symbol]['lastDate'])
                        self.BalanceDict[_symbol][_settleDate] = {
                            'profit': PortfolioDict[_symbol]['tempProfit'],
                            'float': 0
                        }
                        # print(f'settleDate: {_settleDate} balance: {self.BalanceDict[_symbol][_settleDate]}')
                        PortfolioDict[_symbol]['tempProfit'] = 0

                        _nextDate = self.getDate(self.add_subtract_days(
                            PortfolioDict[_symbol]['lastDate'], 1))
                        PortfolioDict[_symbol]['lastDate'] = _nextDate + \
                            " 00:00:00"

                PortfolioDict[_symbol]['totalQuantity'] = _totalQuantity if _action == 'BUY' else _totalQuantity*-1
                PortfolioDict[_symbol]['action'] = _action
                PortfolioDict[_symbol]['price'] = _price
                PortfolioDict[_symbol]['lastDate'] = _time
                # print("buy in", PortfolioDict[_symbol]['price'], PortfolioDict[_symbol]['action'], PortfolioDict[_symbol]['totalQuantity'])

            else:
                # print("hold")
                Hold_totalQuantity = PortfolioDict[_symbol]['totalQuantity']
                Hold_action = PortfolioDict[_symbol]['action']
                Hold_price = PortfolioDict[_symbol]['price']
                # PortfolioDict[symbol]['lastDate'] 小於 time 且不等於 time
                while (self.thanDate(_time, PortfolioDict[_symbol]['lastDate']) and not self.equalDate(_time, PortfolioDict[_symbol]['lastDate'])):
                    # print(f"time:{_time}, PortfolioDict[{_symbol}]['lastDate']:{PortfolioDict[_symbol]['lastDate']}")
                    Hold_totalQuantity = PortfolioDict[_symbol]['totalQuantity']
                    Hold_action = PortfolioDict[_symbol]['action']
                    Hold_price = PortfolioDict[_symbol]['price']
                    
                    _LastDate = PortfolioDict[_symbol]['lastDate']
                    while True:
                        try:
                            CloseDate = self.getDate(_LastDate)
                            ClosePrice = self.CloseData[_symbol][CloseDate]
                            break
                        except:
                            _LastDate = self.add_subtract_days(_LastDate,-1)
                            pass

                    if Hold_action == 'BUY':
                        _floatProfit = (ClosePrice - Hold_price) * \
                            Hold_totalQuantity
                    else:
                        _floatProfit = (Hold_price - ClosePrice) * \
                            -1*(Hold_totalQuantity)
                    _settleDate = self.getDate(
                        PortfolioDict[_symbol]['lastDate'])
                    self.BalanceDict[_symbol][_settleDate] = {
                        'profit': PortfolioDict[_symbol]['tempProfit'],
                        'float': _floatProfit
                    }
                    # print(f'settleDate: {_settleDate} balance: {self.BalanceDict[_symbol][_settleDate]}')
                    PortfolioDict[_symbol]['tempProfit'] = 0

                    _nextDate = self.getDate(self.add_subtract_days(
                        PortfolioDict[_symbol]['lastDate'], 1))
                    PortfolioDict[_symbol]['lastDate'] = _nextDate+" 00:00:00"

                if _action == Hold_action:
                    PortfolioDict[_symbol]['totalQuantity'] = (
                        _totalQuantity if _action == 'BUY' else _totalQuantity*-1)+Hold_totalQuantity
                    PortfolioDict[_symbol]['price'] = (_price+Hold_price)/2
                    # print("hold add volum")
                else:
                    if int(Hold_totalQuantity) - int(_totalQuantity) < 0:
                        PortfolioDict[_symbol]['action'] = _action
                        PortfolioDict[_symbol]['price'] = _price
                    elif int(Hold_totalQuantity) - int(_totalQuantity) == 0:
                        PortfolioDict[_symbol]['action'] = None
                        PortfolioDict[_symbol]['price'] = None

                    PortfolioDict[_symbol]['totalQuantity'] = (
                        _totalQuantity if _action == 'BUY' else _totalQuantity*-1)+Hold_totalQuantity

                    if Hold_action == 'BUY':
                        _trade_profit = (_price - Hold_price) * _totalQuantity
                    else:
                        _trade_profit = (Hold_price - _price) * _totalQuantity

                    PortfolioDict[_symbol]['tempProfit'] = PortfolioDict[_symbol]['tempProfit']+_trade_profit

        self.__calculate_portfolio(PortfolioDict)
        temp_balance = self.__calculate_returns(
            self.__to_integrate_balance(self.BalanceDict))
        receive_portfolo = {
            "balance": temp_balance,
            "time": self.Report_time_list,
            "profit": self.Report_profit_list,
        }
        return receive_portfolo

    def __calculate_portfolio(self, portfolioDict):
        for symbol in portfolioDict:
            FloatProfit = 0

            Hold_totalQuantity = portfolioDict[symbol]['totalQuantity']
            Hold_action = portfolioDict[symbol]['action']
            Hold_price = portfolioDict[symbol]['price']
            CloseDate = self.getDate(portfolioDict[symbol]['lastDate'])
            # print(f"Close : {CloseDate} Hold_totalQuantity: {Hold_totalQuantity} Hold_action:{Hold_action} Hold_price:{Hold_price}")
            ClosePrice = self.CloseData[symbol][CloseDate]

            if Hold_totalQuantity != 0:
                if Hold_action == 'BUY':
                    FloatProfit = (ClosePrice - Hold_price) * \
                        Hold_totalQuantity
                else:
                    FloatProfit = (Hold_price - ClosePrice) * \
                        Hold_totalQuantity

            SettleDate = self.getDate(portfolioDict[symbol]['lastDate'])
            self.BalanceDict[symbol][SettleDate] = {
                'profit': portfolioDict[symbol]['tempProfit'],
                'float': FloatProfit
            }
            portfolioDict[symbol]['tempProfit'] = 0

    def __calculate_returns(self, TotalBalanceDict):
        self.Report_time_list.append(self.getDate(self.add_subtract_days(
            list(TotalBalanceDict.keys())[0]+' 00:00:00', -1)))
        self.Report_profit_list.append(0)
        Temp_balance = self.BackTestBalance
        for date in TotalBalanceDict:
            _float = TotalBalanceDict[date]['float']
            _profit = TotalBalanceDict[date]['profit']
            _totalbalance = _float+_profit
            self.Report_profit_list.append(_totalbalance/Temp_balance)
            self.Report_time_list.append(date)
            Temp_balance = Temp_balance+_totalbalance
        # print(self.Report_time_list)
        # print(self.Report_profit_list)
        return Temp_balance

    def __to_integrate_balance(self, balanceDict):
        TotalBalanceDict = {}
        for symbol in balanceDict:
            for date in balanceDict[symbol]:
                _data = balanceDict[symbol][date]
                _float = _data['float']
                _profit = _data['profit']
                if not date in TotalBalanceDict:
                    TotalBalanceDict[date] = {
                        'float': _float, 'profit': _profit}
                else:
                    _t_float = TotalBalanceDict[date]['float']
                    _t_profit = TotalBalanceDict[date]['profit']
                    TotalBalanceDict[date] = {
                        'float': _float+_t_float,
                        'profit': _profit+_t_profit}
        # print("TotalBalanceDict", TotalBalanceDict)
        return TotalBalanceDict

    def add_subtract_days(self, date_str, days):
        # 解析日期字符串
        datetime_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

        # 增加或减去指定天数
        modified_datetime = datetime_obj + timedelta(days=days)

        # 将结果格式化为日期字符串
        modified_date_str = modified_datetime.strftime("%Y-%m-%d %H:%M:%S")

        # 返回日期字符串
        return modified_date_str

    def __generate_report(self, data):
        time_list = data.get('time')
        time_list = pd.to_datetime(pd.Series(time_list))
        profit_list = data.get('profit')
        stock_return = pd.Series(profit_list, index=time_list).sort_index()
        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")

        filename = current_datetime+'.html'
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

    def addCloseData(self, symbol, price, time):
        if not symbol in self.CloseData:
            self.CloseData[symbol] = {}

        self.CloseData[symbol][self.getDate(time)] = price

    def __for_test_getCloseData(self):
        self.addCloseData('AAPL', 115, '2022-05-11 00:00:00')
        self.addCloseData('AAPL', 125, '2022-05-12 00:00:00')
        self.addCloseData('AAPL', 135, '2022-05-13 00:00:00')

        self.addCloseData('META', 115, '2022-05-11 00:00:00')
        self.addCloseData('META', 125, '2022-05-12 00:00:00')
        self.addCloseData('META', 135, '2022-05-13 00:00:00')
        self.addCloseData('META', 145, '2022-05-14 00:00:00')
        self.addCloseData('META', 115, '2022-05-15 00:00:00')
        self.addCloseData('META', 105, '2022-05-16 00:00:00')
        self.addCloseData('META', 125, '2022-05-17 00:00:00')

    def getDate(self, datatime):
        # 解析日期時間字串
        datetime_obj = datetime.strptime(datatime, "%Y-%m-%d %H:%M:%S")

        # 提取日期部分並轉換為字串
        return datetime_obj.strftime("%Y-%m-%d")

    def thanDate(self, datetime_str1, datetime_str2):
        datetime_str1 = self.getDate(datetime_str1)+" 00:00:00"
        datetime_str2 = self.getDate(datetime_str2)+" 00:00:00"
        # 解析日期時間字串
        datetime_obj1 = datetime.strptime(datetime_str1, "%Y-%m-%d %H:%M:%S")
        datetime_obj2 = datetime.strptime(datetime_str2, "%Y-%m-%d %H:%M:%S")

        # 比較日期時間大小
        return (True if datetime_obj1 > datetime_obj2 else False)

    def equalDate(self, datetime_str1, datetime_str2):
        datetime_str1 = self.getDate(datetime_str1)+" 00:00:00"
        datetime_str2 = self.getDate(datetime_str2)+" 00:00:00"
        # 解析日期時間字串
        datetime_obj1 = datetime.strptime(datetime_str1, "%Y-%m-%d %H:%M:%S")
        datetime_obj2 = datetime.strptime(datetime_str2, "%Y-%m-%d %H:%M:%S")

        return (True if datetime_obj1 == datetime_obj2 else False)

    def __for_Test_InitData(self):
        portfolio_value = {
            'symbol': 'AAPL',
            'action': 'BUY',
            'totalQuantity': 150,
            'time': '2022-05-11 21:00:00',
            'dealPrice': 140
        }
        self.addPortfolioData(portfolio_value)
        portfolio_value = {
            'symbol': 'AAPL',
            'action': 'SELL',
            'totalQuantity': 50,
            'time': '2022-05-11 21:00:00',
            'dealPrice': 110
        }
        self.addPortfolioData(portfolio_value)
        portfolio_value = {
            'symbol': 'AAPL',
            'action': 'SELL',
            'totalQuantity': 50,
            'time': '2022-05-13 21:00:00',
            'dealPrice': 120
        }
        self.addPortfolioData(portfolio_value)
        portfolio_value = {
            'symbol': 'AAPL',
            'action': 'SELL',
            'totalQuantity': 50,
            'time': '2022-05-13 22:00:00',
            'dealPrice': 130
        }
        self.addPortfolioData(portfolio_value)

        portfolio_value = {
            'symbol': 'META',
            'action': 'BUY',
            'totalQuantity': 150,
            'time': '2022-05-11 21:00:00',
            'dealPrice': 140
        }
        self.addPortfolioData(portfolio_value)
        portfolio_value = {
            'symbol': 'META',
            'action': 'SELL',
            'totalQuantity': 50,
            'time': '2022-05-11 21:00:00',
            'dealPrice': 110
        }
        self.addPortfolioData(portfolio_value)
        portfolio_value = {
            'symbol': 'META',
            'action': 'SELL',
            'totalQuantity': 50,
            'time': '2022-05-13 21:00:00',
            'dealPrice': 120
        }
        self.addPortfolioData(portfolio_value)
        portfolio_value = {
            'symbol': 'META',
            'action': 'SELL',
            'totalQuantity': 50,
            'time': '2022-05-13 22:00:00',
            'dealPrice': 130
        }
        self.addPortfolioData(portfolio_value)

        portfolio_value = {
            'symbol': 'META',
            'action': 'SELL',
            'totalQuantity': 50,
            'time': '2022-05-14 22:00:00',
            'dealPrice': 110
        }
        self.addPortfolioData(portfolio_value)

        portfolio_value = {
            'symbol': 'META',
            'action': 'BUY',
            'totalQuantity': 50,
            'time': '2022-05-17 22:00:00',
            'dealPrice': 130
        }
        self.addPortfolioData(portfolio_value)
        
    def initPortfolioData(self):
        self.Portfolio = []

    def addPortfolioData(self, data):
        self.Portfolio.append(data)

    def generate_report(self):
        data = self.calculate_portfolio()
        if len(data.get('time')) > 0:
            self.__generate_report({
                'time': data.get('time'),
                'profit': data.get('profit'),
                'title': self.TitleName
            })
        else:
            print("Generating the report failed because there are no transactions")
        return data

    def setTitleName(self, name):
        self.TitleName = name


# if __name__ == "__main__":
#     verify_result = {'balance': 83250, 'time': ['2022-05-10', '2022-05-11', '2022-05-12', '2022-05-13', '2022-05-14', '2022-05-15', '2022-05-16', '2022-05-17'], 'profit': [
#         0, -0.08, -0.03260869565217391, -0.033707865168539325, -0.020348837209302327, -0.002967359050445104, 0.002976190476190476, -0.011869436201780416]}

#     ReportContener = Report()
#     ReportContener.__for_Test_InitData()
#     ReportContener.__for_test_getCloseData()
#     ReportContener.setTitleName('portfolio')
#     Data = ReportContener.generate_report()
#     print("verify_result", verify_result == Data)
