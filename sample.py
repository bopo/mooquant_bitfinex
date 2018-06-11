from mooquant import strategy
from mooquant.bar import Frequency
from mooquant.technical import cross, ma
from mooquant_bitfinex import broker, livefeed


class MyStrategy(strategy.BaseStrategy):
    def __init__(self, feed, brk):
        strategy.BaseStrategy.__init__(self, feed, brk)
        smaPeriod = 20

        self.__instrument = "btcusd"
        self.__prices = feed[self.__instrument].getCloseDataSeries()
        self.__sma = ma.SMA(self.__prices, smaPeriod)
        self.__bid = None
        self.__ask = None
        self.__position = None
        self.__posSize = 0.05

        # Subscribe to order book update events to get bid/ask prices to trade.
        feed.getOrderBookUpdateEvent().subscribe(self.__onOrderBookUpdate)

    def __onOrderBookUpdate(self, orderBookUpdate):
        bid = orderBookUpdate['bid']
        ask = orderBookUpdate['ask']

        if bid != self.__bid or ask != self.__ask:
            self.__bid = bid
            self.__ask = ask
            self.info("订单更新. Best bid: {}. Best ask: {}".format(self.__bid, self.__ask))

    def onEnterOk(self, position):
        self.info("头寸开仓 {}".format(position.getEntryOrder().getExecutionInfo().getPrice()))

    def onEnterCanceled(self, position):
        self.info("头寸取消点")
        self.__position = None

    def onExitOk(self, position):
        self.__position = None
        self.info("Position closed at {}".format(position.getExitOrder().getExecutionInfo().getPrice()))

    def onExitCanceled(self, position):
        # If the exit was canceled, re-submit it.
        self.__position.exitLimit(self.__bid)

    def onBars(self, bars):
        bar = bars[self.__instrument]
        self.info("价格: {}. 交易量: {}.".format(bar.getClose(), bar.getVolume()))

        # Wait until we get the current bid/ask prices.
        if self.__ask is None:
            return

        # If a position was not opened, check if we should enter a long
        # position.
        if self.__position is None:
            if cross.cross_above(self.__prices, self.__sma) > 0:
                self.info("Entry signal. Buy at {}".format(self.__ask))
                self.__position = self.enterLongLimit(
                    self.__instrument, self.__ask, self.__posSize, True)
        # Check if we have to close the position.
        elif not self.__position.exitActive() and cross.cross_below(self.__prices, self.__sma) > 0:
            self.info("Exit signal. Sell at {}".format(self.__bid))
            self.__position.exitLimit(self.__bid)


def main():
    barFeed = livefeed.LiveFeed(['btcusd'], 2)
    brk = broker.PaperTradingBroker(1000, barFeed)
    strat = MyStrategy(barFeed, brk)
    strat.run()


if __name__ == "__main__":
    main()
