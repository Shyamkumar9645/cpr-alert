import io
import logging
import pandas as pd
import mplfinance as mpf
import matplotlib
matplotlib.use('Agg') # Use a non-interactive backend
import matplotlib.pyplot as plt
from typing import List, Optional
import pytz  # Add this import for timezone handling

from core.data_classes import CandleData, CPRLevels, LevelType

class ChartGenerator:
    """Generates candlestick charts with a clean, professional style."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_cpr_chart(self, asset_name: str, candle_data: List[CandleData],
                         cpr_levels: CPRLevels, current_level: LevelType,
                         current_price: float) -> Optional[io.BytesIO]:
        if not candle_data:
            return None

        try:
            df = pd.DataFrame([cd.__dict__ for cd in candle_data])

            # Convert timestamp to datetime with proper timezone handling
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)  # First convert to UTC
            ist_tz = pytz.timezone('Asia/Kolkata')  # IST timezone
            df['datetime'] = df['datetime'].dt.tz_convert(ist_tz)  # Convert UTC to IST

            df.set_index('datetime', inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume']]

            hlines = {
                'hlines': [cpr_levels.s1, cpr_levels.pivot, cpr_levels.r1],
                'colors': ['#FF5252', '#367dfb', '#00E676'],
                'linestyle': '--',
                'linewidths': 1.5,
                'alpha': 0.9
            }

            mc = mpf.make_marketcolors(up='#26a69a', down='#ef5350', edge='inherit', wick={'up': '#26a69a', 'down': '#ef5350'})
            style = mpf.make_mpf_style(base_mpf_style='yahoo', marketcolors=mc, gridstyle='-', gridcolor='#E0E0E0')

            # Set volume=False to remove the volume panel from the chart.
            fig, axes = mpf.plot(
                df.tail(80), type='candle', style=style, title='', volume=False,
                hlines=hlines, figsize=(12, 6), returnfig=True, # Reduced height since volume is gone
                datetime_format='%H:%M', xrotation=0
            )

            ax = axes[0]
            ax.set_title(f'{asset_name} - 5min CPR (IST)', loc='left', fontdict={'fontsize': 14, 'fontweight': 'bold'})
            ax.text(0.98, 0.98, f'R1: {cpr_levels.r1:.2f} | P: {cpr_levels.pivot:.2f} | S1: {cpr_levels.s1:.2f}',
                    transform=ax.transAxes, ha='right', va='top', fontsize=10)
            ax.text(0.98, 0.90, f'{current_level.value} Alert @ {current_price:.2f}', # Adjusted y-position slightly
                    transform=ax.transAxes, ha='right', va='top', fontsize=10, color='#FF5722', fontweight='bold')

            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            return buf
        except Exception as e:
            self.logger.error(f"Error generating chart for {asset_name}: {e}")
            return None