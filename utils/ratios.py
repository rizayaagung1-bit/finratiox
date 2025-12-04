# utils/ratios.py
"""
Fungsi-fungsi sederhana untuk menghitung rasio keuangan.
Pastikan file ini berada di folder 'utils' pada root repo.
"""

def safe_divide(numerator, denominator):
    try:
        if denominator is None or denominator == 0:
            return None
        return numerator / denominator
    except Exception:
        return None

def current_ratio(current_assets, current_liabilities):
    """Current Ratio = Current Assets / Current Liabilities"""
    return safe_divide(current_assets, current_liabilities)

def debt_to_equity(total_liabilities, total_equity):
    """Debt to Equity Ratio = Total Liabilities / Total Equity"""
    return safe_divide(total_liabilities, total_equity)

def roa(net_income, total_assets):
    """Return on Assets = Net Income / Total Assets"""
    return safe_divide(net_income, total_assets)

def roe(net_income, total_equity):
    """Return on Equity = Net Income / Total Equity"""
    return safe_divide(net_income, total_equity)
