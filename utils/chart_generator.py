import mplfinance as mpf
import pandas as pd
from PIL import Image
import io
import logging
import matplotlib.pyplot as plt
from core.data_classes import CandleData
from typing import Optional, List
from datetime import date

class ChartGenerator:
    """
    Generates and saves candlestick charts with CPR and pivot levels.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_cpr_chart(self, symbol: str, asset_name: str, candle_data: list, cpr_levels: dict, current_level: str, current_price: float) -> str:
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
                'linestyle': [],
                'linewidth': []
            }
            # CPR Lines (Pivot, TC, BC)
            hlines_data['price'].extend([cpr_levels['pivot'], cpr_levels['tc'], cpr_levels['bc']])
            hlines_data['color'].extend(['blue', 'blue', 'blue'])
            hlines_data['linestyle'].extend(['-', '-.', '-.'])
            hlines_data['linewidth'].extend([1.5, 1, 1])

            # Resistance Lines (R1, R2, R3, R4)
            hlines_data['price'].extend([cpr_levels['r1'], cpr_levels['r2'], cpr_levels['r3'], cpr_levels['r4']])
            hlines_data['color'].extend(['green', 'green', 'green', 'green'])
            hlines_data['linestyle'].extend(['--', '--', '--', '--'])
            hlines_data['linewidth'].extend([1, 1, 1, 1])

            # Support Lines (S1, S2, S3, S4)
            hlines_data['price'].extend([cpr_levels['s1'], cpr_levels['s2'], cpr_levels['s3'], cpr_levels['s4']])
            hlines_data['color'].extend(['red', 'red', 'red', 'red'])
            hlines_data['linestyle'].extend(['--', '--', '--', '--'])
            hlines_data['linewidth'].extend([1, 1, 1, 1])

            # Chart style (White theme, similar to Kite/TradingView)
            mc = mpf.make_marketcolors(
                up='green', down='red',
                edge='inherit',
                wick='inherit',
                ohlc='inherit',
                volume='inherit'
            )
            s = mpf.make_mpf_style(
                base_mpf_style='yahoo', # Start with a base style
                marketcolors=mc,
                gridstyle=':',
                gridcolor='#e0e0e0', # Light grey grid
                facecolor='white', # White background
                figcolor='white', # White figure background
                rc={'axes.edgecolor': 'black', 'axes.linewidth': 1.5, 'ytick.color': 'black', 'axes.labelcolor': 'black'} # Black axes, ticks, and labels
            )

            # Title
            title = f"{asset_name} ({symbol.split(':')[-1].replace('-EQ', '')}) | LTP: {current_price:.2f} | Alert: {current_level}"

            # Highlight the current level
            self._highlight_level(hlines_data, cpr_levels, current_level)

            # Plot
            fig, axes = mpf.plot(
                df,
                type='candle',
                style=s,
                title=title,
                ylabel='Price',
                hlines=dict(hlines=hlines_data['price'],
                            colors=hlines_data['color'],
                            linestyle=hlines_data['linestyle'],
                            linewidths=hlines_data['linewidth']),
                returnfig=True,
                figsize=(15, 7),
                show_nontrading_days=False,
                tight_layout=True,
                y_on_right=True # Move y-axis to the right
            )

            # Add a legend for the hlines
            from matplotlib.lines import Line2D
            legend_elements = [
                Line2D([0], [0], color='blue', lw=1.5, label='CPR', linestyle='-'),
                Line2D([0], [0], color='green', lw=1, label='Resistance', linestyle='--'),
                Line2D([0], [0], color='red', lw=1, label='Support', linestyle='--'),
                Line2D([0], [0], color='magenta', lw=2.5, label='Triggered Level', linestyle='-')
            ]
            axes[0].legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.02, 1), borderaxespad=0.)

            # Adjust the layout to prevent labels from overlapping
            fig.tight_layout(rect=[0, 0, 0.98, 1]) # Adjust rect to make space for legend

            # Save the figure to a file
            chart_filename = f"{symbol.replace(':', '_')}_chart.png"
            fig.savefig(chart_filename)
            self.logger.info(f"Chart saved as {chart_filename}")
            plt.close(fig)
            return chart_filename

        except Exception as e:
            self.logger.exception(f"Error generating chart for {symbol}: {e}")
            return ""

    def _highlight_level(self, hlines_data: dict, cpr_levels: dict, current_level: str):
        """
        Highlights the current triggered level on the chart.
        """
        level_map = {
            'R1': cpr_levels['r1'],
            'TC': cpr_levels['tc'],
            'Pivot': cpr_levels['pivot'],
            'BC': cpr_levels['bc'],
            'S1': cpr_levels['s1'],
            'Resistance': cpr_levels['r1'], # Assuming Resistance is R1 for highlighting
            'Support': cpr_levels['s1'],    # Assuming Support is S1 for highlighting
            'CPR Bottom': cpr_levels['bc'], # Add support for "CPR Bottom"
            'CPR Top': cpr_levels['tc'],    # Add support for "CPR Top"
        }

        if current_level in level_map:
            highlight_price = level_map[current_level]
            try:
                idx = hlines_data['price'].index(highlight_price)
                hlines_data['color'][idx] = 'magenta'  # Highlight color
                hlines_data['linewidth'][idx] = 2.5  # Thicker line
            except ValueError:
                # This can happen if the level is not exactly in hlines_data (e.g., due to float precision)
                # Find the closest level to highlight
                closest_idx = -1
                min_diff = float('inf')
                for i, price in enumerate(hlines_data['price']):
                    diff = abs(price - highlight_price)
                    if diff < min_diff:
                        min_diff = diff
                        closest_idx = i
                if closest_idx != -1 and min_diff < 0.1: # Tolerance for float comparison
                    hlines_data['color'][closest_idx] = 'magenta'
                    hlines_data['linewidth'][closest_idx] = 2.5
                else:
                    self.logger.warning(f"Could not find exact or close match for highlighting level {current_level} at price {highlight_price}")
        else:
            self.logger.warning(f"Unknown level type for highlighting: {current_level}")

    def get_chart_data(self, fyers_service, symbol: str, candle_count: int = 50, for_date: Optional[date] = None) -> List[CandleData]:
        """
        Fetches historical candle data for chart generation.
        """
        try:
            if for_date:
                # Fetch data for a specific date (used by test_alert)
                data = fyers_service.get_historical_data(symbol, "5", for_date, for_date)
            else:
                # Fetch latest data (used by live bot)
                data = fyers_service.get_historical_data(symbol, "5", None, None, candle_count)

            if data:
                return [CandleData(**candle) for candle in data]
            return []
        except Exception as e:
            self.logger.error(f"Error fetching chart data for {symbol}: {e}")
            return []

            # Save the figure to a file
            chart_filename = f"{symbol.replace(':', '_')}_chart.png"
            fig.savefig(chart_filename)
            self.logger.info(f"Chart saved as {chart_filename}")
            plt.close(fig)
            return chart_filename

        except Exception as e:
            self.logger.exception(f"Error generating chart for {symbol}: {e}")
            return ""

    def _highlight_level(self, hlines_data: dict, cpr_levels: dict, current_level: str):
        """
        Highlights the current triggered level on the chart.
        """
        level_map = {
            'R1': cpr_levels['r1'],
            'TC': cpr_levels['tc'],
            'Pivot': cpr_levels['pivot'],
            'BC': cpr_levels['bc'],
            'S1': cpr_levels['s1'],
            'Resistance': cpr_levels['r1'], # Assuming Resistance is R1 for highlighting
            'Support': cpr_levels['s1'],    # Assuming Support is S1 for highlighting
            'CPR Bottom': cpr_levels['bc'], # Add support for "CPR Bottom"
            'CPR Top': cpr_levels['tc'],    # Add support for "CPR Top"
        }

        if current_level in level_map:
            highlight_price = level_map[current_level]
            try:
                idx = hlines_data['price'].index(highlight_price)
                hlines_data['color'][idx] = 'magenta'  # Highlight color
                hlines_data['linewidth'][idx] = 2.5  # Thicker line
            except ValueError:
                # This can happen if the level is not exactly in hlines_data (e.g., due to float precision)
                # Find the closest level to highlight
                closest_idx = -1
                min_diff = float('inf')
                for i, price in enumerate(hlines_data['price']):
                    diff = abs(price - highlight_price)
                    if diff < min_diff:
                        min_diff = diff
                        closest_idx = i
                if closest_idx != -1 and min_diff < 0.1: # Tolerance for float comparison
                    hlines_data['color'][closest_idx] = 'magenta'
                    hlines_data['linewidth'][closest_idx] = 2.5
                else:
                    self.logger.warning(f"Could not find exact or close match for highlighting level {current_level} at price {highlight_price}")
        else:
            self.logger.warning(f"Unknown level type for highlighting: {current_level}")

    def get_chart_data(self, fyers_service, symbol: str, candle_count: int = 50, for_date: Optional[date] = None) -> List[CandleData]:
        """
        Fetches historical candle data for chart generation.
        """
        try:
            if for_date:
                # Fetch data for a specific date (used by test_alert)
                data = fyers_service.get_historical_data(symbol, "5", for_date, for_date)
            else:
                # Fetch latest data (used by live bot)
                data = fyers_service.get_historical_data(symbol, "5", None, None, candle_count)

            if data:
                return [CandleData(**candle) for candle in data]
            return []
        except Exception as e:
            self.logger.error(f"Error fetching chart data for {symbol}: {e}")
            return []
