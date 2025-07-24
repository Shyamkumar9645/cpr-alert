from core.data_classes import OHLCData, CPRLevels

class CPRCalculator:
    @staticmethod
    def calculate_levels(ohlc: OHLCData) -> CPRLevels:
        pivot = (ohlc.high + ohlc.low + ohlc.close) / 3
        bc = (ohlc.high + ohlc.low) / 2
        tc = (pivot - bc) + pivot
        r1 = (2 * pivot) - ohlc.low
        s1 = (2 * pivot) - ohlc.high
        return CPRLevels(pivot=pivot, bc=bc, tc=tc, r1=r1, s1=s1)