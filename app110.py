
from app48 import app

def formato_pesos(valor):
    try:
        v = float(valor or 0)
        # Formato: 1,234.56 -> 1.234,56
        return "$" + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "$0,00"

app.jinja_env.filters['pesos'] = formato_pesos
