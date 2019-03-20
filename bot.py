import bin
from sys import argv
from random import randint
from datetime import timedelta
from time import time

############################################

# SETTINGS
ACTIVE = False
TRADE_AMOUNT = 300
DEFAULT_OFFSET = 0.00000005
CANCEL_SELL_TIME = 25
COURAGEOUS_MULTIPLIER = 1
USE_HISTORICAL_DIRECTION = False
TRADE_PREFIX = 'GDAOUHD9989'

# BINANCE INFORMATION
API_KEY = ""
SECRET = ""

############################################

deci = lambda x: '{0:.8f}'.format(x)

FILENAME = argv[0]
if len(argv) < 2:
	print('Usage: python3', FILENAME, '[currency] [OPTIONAL:offset]')
	print('Default offset:', deci(DEFAULT_OFFSET))
	exit()

if API_KEY == "" or SECRET == "":
	print("Warning: API Key/Secret not set in", FILENAME)
	ACTIVE = False
else:
	bin.set(API_KEY, SECRET)

if not ACTIVE:
	print("Warning: ACTIVE set to False in", FILENAME, "(demo mode, not real trades)\n")

inputCurrency = argv[1].upper()
currency = inputCurrency+'BTC' if inputCurrency != 'BTC' else 'BTCUSDT'
offset = float(argv[2]) if len(argv) > 2 else DEFAULT_OFFSET

getPrice = lambda x: bin.prices()[x]
count = 0
sellCompleted = False
randNum = 'randNum'
successfulTrades = []

def sellAtLocalMaximum():
	p = [float(d['close']) for d in bin.klines(currency, '1m')[-35:-3]]
	currentP, pastH = getPrice(currency), deci(max(p))
	return float(currentP)-0.00000003 > float(pastH), currentP, pastH

def sgn(x):
        if x > 0:
                return 'UP'
        elif x < 0:
                return 'DOWN'
        else:
                return 'FLAT'

def getDirection():
	p = [float(d['close']) for d in bin.klines(currency, '1m')[-5:-1]]
	direction = sgn(p[-1]-p[-2])
	direction2 = sgn(p[-2]-p[-3])
	if direction == direction2:
		return direction
	elif (direction == 'UP' and direction2 == 'FLAT') or (direction2 == 'UP' and direction == 'FLAT'):
		return 'UP'
	elif (direction == 'DOWN' and direction == 'FLAT') or (direction2 == 'DOWN' and direction == 'FLAT'):
		return 'DOWN'
	else:
		return 'FLAT'

def historicalDirection():
	"""
	Prevent: Scenario where sells at local minimum & then price immediately starts going up
	By: If price from one minute ago is lower than price from 5 minutes ago, do not trade.
	This function returns 'DOWN' if this is the case.
	"""
	if not USE_HISTORICAL_DIRECTION:
		return 'OFF'
	p = [float(d['close']) for d in bin.klines(currency, '1m')[-6:-1]]
	direction = sgn(p[-1]-p[-5]-0.00000002)
	return direction

def instantPriceDirection():
	instantPrice = float(getPrice(currency))
	p = [float(d['close']) for d in bin.klines(currency, '1m')[-6:-1]]
	oneMinuteAgoClosingPrice = p[-1]
	direction = sgn(instantPrice - oneMinuteAgoClosingPrice + 0.00000002)
	return direction

print('Amount:', TRADE_AMOUNT, '| Currency:', currency, '| Offset:', deci(offset))
print('Strategy: If (Relative:DOWN, Instant:DOWN, History: NOT DOWN) OR isAtLocalMaximum')
print('                 => Sell High, Buy Low')

start_time = time()

while True:
	try:
		while not sellCompleted:
			count = 0
			if count <= CANCEL_SELL_TIME:
				currentDirection = getDirection()
				pastDirection = historicalDirection()
				instantDirection = instantPriceDirection()
				isAtLocalMaximum, currentP, pastH = sellAtLocalMaximum()
				shouldSellAt = float(currentP)+0.00000003
				while not isAtLocalMaximum and (currentDirection != 'DOWN' or pastDirection == 'DOWN' or instantDirection != 'DOWN'):
					timeItTook = str(timedelta(seconds=int(time() - start_time)))
					print('Relative:', currentDirection, '| Instant:', instantDirection, '| History:', pastDirection, '| Trades:', len(successfulTrades), '| Time:', timeItTook)
					print('Current Price:', currentP, '| LocalMax:', pastH, '| isAtLocalMaximum:', isAtLocalMaximum)
					currentDirection = getDirection()
					instantDirection = instantPriceDirection()
					pastDirection = historicalDirection()
					shouldSellAt = float(currentP)+0.00000003
					isAtLocalMaximum, currentP, pastH = sellAtLocalMaximum()

				if isAtLocalMaximum and not (currentDirection == 'DOWN' and instantDirection == 'DOWN'):
					print('Proceeding... [Local maximum price]')
					shouldSellAt += 0.00000005
				else:
					print('Proceeding... [Relative:', currentDirection, '| Instant:', instantDirection, '| History:', pastDirection, ']')

				tradePrice = float(getPrice(currency))
				soldAt = max(tradePrice, shouldSellAt)
				randNum = str(randint(0, 99999))
				if ACTIVE:
					bin.order(currency, bin.SELL, TRADE_AMOUNT, soldAt, newClientOrderId=TRADE_PREFIX+"SELL"+randNum)
				currentPrice = float(getPrice(currency))
				while currentPrice < soldAt and count <= CANCEL_SELL_TIME:
					count += 1
					print(count, '| Selling: Waiting for price', deci(soldAt), '[', deci(currentPrice), ']')
					currentPrice = float(getPrice(currency))
				if count <= CANCEL_SELL_TIME:
					print('Selling: Completed at price', deci(soldAt))
					sellCompleted = True
					count = 0
				else:
					print('Canceled sell order at', deci(soldAt))
					if ACTIVE:
						bin.cancel(currency, origClientOrderId=TRADE_PREFIX+"SELL"+randNum)
					count = 0

		courageousPrice = soldAt-(offset*COURAGEOUS_MULTIPLIER)
		if isAtLocalMaximum:
			tradePrice = float(min(float(getPrice(currency)), soldAt-offset, courageousPrice))
		else:
			tradePrice = float(min(float(getPrice(currency)), soldAt-offset))
		randNum = str(randint(0, 99999))
		if ACTIVE:
			bin.order(currency, bin.BUY, TRADE_AMOUNT, tradePrice, newClientOrderId=TRADE_PREFIX+"BUY"+randNum)
		currentPrice = float(getPrice(currency))
		while currentPrice > tradePrice:
			count += 1
			print(count, '| Buying: Waiting for price', deci(tradePrice), '[', deci(currentPrice), ']')
			currentPrice = float(getPrice(currency))
		print('Buying: Completed at price', deci(tradePrice))
		successfulTrades.append((deci(soldAt), deci(tradePrice)))
		sellCompleted = False
	except (KeyboardInterrupt, ValueError) as e:
		print()
		print('Canceled last open sell order (if any)')
		if ACTIVE:
			bin.cancel(currency, origClientOrderId=TRADE_PREFIX+"SELL"+randNum)
		if successfulTrades == []:
			successfulTrades = None
		print('Trade History:', successfulTrades)

		timeItTook = int(time() - start_time)
		print('Time:', str(timedelta(seconds=timeItTook)))
		exit()
