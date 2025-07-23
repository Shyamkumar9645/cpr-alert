import mplfinance as mpf
import pandas as pd
from PIL import Image
import io
import logging

class ChartGenerator:
    """
    Generates and saves candlestick charts with CPR and pivot levels.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_cpr_chart(self, symbol: str, candle_data: list, cpr_levels: dict, current_price: float) -> str:
        """
        Generates a candlestick chart and saves it as a PNG image.
        """
        try:
            df = pd.DataFrame(candle_data)
            df['date'] = pd.to_datetime(df['timestamp'], unit='s')
            df.set_index('date', inplace=True)
            df = df[['open', 'high', 'low', 'close']]

            # Prepare horizontal lines for CPR and pivots
            hlines_data = {
                'price': [],
                'color': [],
                'linestyle': []
            }
            # CPR Lines
            hlines_data['price'].extend([cpr_levels['tc'], cpr_levels['pivot'], cpr_levels['bc']])
            hlines_data['color'].extend(['blue', 'blue', 'blue'])
            hlines_data['linestyle'].extend(['-.', '-', '-.'])
            # Pivot Lines
            hlines_data['price'].extend([cpr_levels['r1'], cpr_levels['s1']])
            hlines_data['color'].extend(['g', 'r'])
            hlines_data['linestyle'].extend(['--', '--'])

            # Chart style
            mc = mpf.make_marketcolors(up='green', down='red', inherit=True)
            s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':')

            # Title
            title = f"{symbol.split(':')[-1].replace('-EQ', '')} | LTP: {current_price:.2f}"

            # Plot
            fig, axes = mpf.plot(
                df,
                type='candle',
                style=s,
                title=title,
                ylabel='Price',
                hlines=dict(hlines=hlines_data['price'], colors=hlines_data['color'], linestyle=hlines_data['linestyle']),
                returnfig=True,
                figsize=(15, 7)
            )

            # Save the figure to a file
            chart_filename = f"{symbol.replace(':', '_')}_chart.png"
            fig.savefig(chart_filename)
            self.logger.info(f"Chart saved as {chart_filename}")
            return chart_filename

        except Exception as e:
            self.logger.exception(f"Error generating chart for {symbol}: {e}")
            return ""