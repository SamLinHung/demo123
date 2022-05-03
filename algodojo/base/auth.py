

import json

class Auth(object):
    def __init__(self) -> None:
        self.__login = False
        self.__customer_symbols = []
        # self.__development_toggle = True
        self.__development_toggle = False
        

    def sign_in(self, token):
        print('call in: sign_in')

        self.__post_authentication(token)

    def check_status(self):
        print('call in: check_status')

        if self.__development_toggle:
            return

        if not self.__login:
            span = 'Token is fail, before useing the algodojo api, you must first register it! Please go the http://algodojo.com'
            raise NameError(span)

    def check_symbol(self, symbol):
        print('call in: check_symbol')

        if self.__development_toggle:
            return

        if not symbol in self.__customer_symbols:
            span = 'Get Data is fail, before useing the symbol, you must first register it! Please go the http://algodojo.com'
            raise NameError(span)

    # real post to web server
    def __post_authentication(self, token):
        print('token',token)

        if token == 'algodojo_basic':
            response = '{"result": true, "customer_symbols": ["APPL","TSLA"]}'
        elif token == 'algodojo_silver':
            response = '{"result": true, "customer_symbols": ["APPL","TSLA","MCD"]}'
        elif token == 'algodojo_gold':
            response = '{"result": true, "customer_symbols": ["ALL"]}'
        else:
            response = '{"result": false, "customer_symbols": []}'

        response = json.loads(response)
        self.__login = response["result"]
        self.__customer_symbols = response["customer_symbols"]


# if __name__ == "__main__":

