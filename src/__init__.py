"""src パッケージの初期化ファイル"""

from .econ_analysis import EconAnalyzer, robust_regression_summary, simulate_wage_data

__version__ = "0.1.0"
__all__ = ["EconAnalyzer", "simulate_wage_data", "robust_regression_summary"]
