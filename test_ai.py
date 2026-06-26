from data import get_history
from indicators import add_indicators
from ai_engine import analyze

df = get_history("AAPL", "USA")
df = add_indicators(df)

result = analyze(df)

print(result)